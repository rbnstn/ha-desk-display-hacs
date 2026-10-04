"""Refresh the display every ten seconds, serializing all device transfers."""

import logging
import asyncio
import uuid
from time import monotonic
from datetime import timedelta
import aiohttp
from homeassistant.core import callback
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.components.lock import LockEntityFeature
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DEFAULT_LAYOUT, DOMAIN
from .models import get_layout
from .render import render_frame, render_jpeg
from .actions import action_at,widget_at,command_data
from .transport import regions
from .doorbell import current_layout, get_doorbell, is_ring, video_widget
from .rules import entities
from .pages import all_widgets

LOGGER = logging.getLogger(__name__)


def action_available(state, domain):
    if state is None or state.state in ('unknown', 'unavailable'):
        return False
    if domain == 'lock':
        features = state.attributes.get('supported_features', 0)
        return (isinstance(features, int) and not isinstance(features, bool)
                and bool(features & LockEntityFeature.OPEN)
                and not state.attributes.get('code_format'))
    return True


def snapshot_states(hass, layout):
    now=dt_util.now()
    result = {'__now__':now.timestamp(),'__timezone__':hass.config.time_zone if hasattr(hass,'config') else 'UTC','__attributes__':{},'__raw__':{}, '__clock__':{'time':now.strftime('%H:%M'), 'date':now.strftime('%d.%m.%Y'), 'datetime':now.strftime('%d.%m. %H:%M')}}
    for widget in layout["widgets"]+layout.get('overlay',{}).get('widgets',[]):
        for entity in entities(widget):
            raw=hass.states.get(entity)
            result['__raw__'][entity]=(raw.state,'') if raw else ('unavailable','')
        if widget["kind"] in ("text", "media", "image", "clock"):
            continue
        if widget['kind'] in ('sensor','progress','gauge','chip','chart','cost','weather','countdown'):
            for entity in (widget['entity_id'],widget.get('value',{}).get('fallback_entity_id','')):
                if entity:
                    raw=hass.states.get(entity)
                    result['__raw__'][entity]=(raw.state,raw.attributes.get('unit_of_measurement','')) if raw else ('unavailable','')
        state = hass.states.get(widget["entity_id"])
        if state:result["__attributes__"][widget["entity_id"]]=dict(state.attributes)
        if state is None or state.state in ('unknown','unavailable') or (
            widget['kind']=='button' and not action_available(state,widget['entity_id'].split('.')[0])
        ):
            result[widget["entity_id"]] = "Nicht verfuegbar"
        else:
            unit = state.attributes.get("unit_of_measurement", "") if widget["kind"] == "sensor" else ""
            result[widget["entity_id"]] = f"{state.state} {unit}".strip()[:120]
    return result


class DeskDisplayCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client):
        super().__init__(hass, LOGGER, config_entry=entry, name=DOMAIN,
                         update_interval=timedelta(seconds=10),
                         request_refresh_debouncer=Debouncer(
                             hass, LOGGER, cooldown=1, immediate=True))
        self.entry = entry
        self.client = client
        self.last_frame = None
        self.last_layout = None
        self.revision = None
        self.last_touch_id = None
        self.io_lock = asyncio.Lock()
        self.touch_busy = False
        self.touch_stopped = False
        self.doorbell_active=False
        self.doorbell_timer=None
        self.doorbell_deadline=0
        self.doorbell_generation=0
        self.doorbell_session=0
        self.doorbell_feedback=''
        self.doorbell_last_press=0
        self.page_index=0
        self.page_deadline=0
        self.last_confirmed_at=0
        self.firmware_updating=False
        self.action_feedback={}
        self.confirm_action=None
        self.notifications=[]
        self.temporary_page=None

    @callback
    def async_start(self):
        """The display is a consumer even when HA's diagnostic entities are disabled."""
        from .media import MediaWorker
        self.media = MediaWorker(self)
        self.media.start()
        self.entry.async_on_unload(self.async_add_listener(self._keep_polling))
        self.entry.async_on_unload(
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._state_changed))
        stop_timer = async_track_time_interval(self.hass, self._poll_touch, timedelta(seconds=.2))
        @callback
        def stop_touch():
            self.touch_stopped = True
            stop_timer()
        self.entry.async_on_unload(stop_touch)
        self.entry.async_on_unload(self.stop_doorbell)
        self.entry.async_on_unload(async_track_time_interval(self.hass,self._rotate_page,timedelta(seconds=1)))

    def notify(self,message,duration=15,priority=0):
        now=monotonic();self.notifications=[n for n in self.notifications if n[2]>now]
        self.notifications.append((message,priority,now+duration));self.notifications.sort(key=lambda n:n[1],reverse=True);self.notifications=self.notifications[:5]
        async_call_later(self.hass,duration,lambda _:self.hass.async_create_task(self.async_refresh()) if not self.touch_stopped else None)

    def show_page(self,index,duration=30):
        layout=get_layout(self.entry.options)
        if index>len(layout.get('pages',[])):raise ValueError('Seite existiert nicht')
        previous=self.temporary_page[0] if self.temporary_page else self.page_index
        self.temporary_page=(previous,monotonic()+duration);self.page_index=index;self.page_deadline=0

    @callback
    def _rotate_page(self,_now=None):
        layout=get_layout(self.entry.options);seconds=layout.get('rotation',0)
        if any(w['kind']=='countdown' for w in current_layout(self).get('widgets',[])) and not self.touch_stopped:self.hass.async_create_task(self.async_request_refresh())
        if self.temporary_page:
            if self.doorbell_active:return
            if monotonic()<self.temporary_page[1]:return
            self.page_index=min(self.temporary_page[0],len(layout.get('pages',[])));self.temporary_page=None;self.page_deadline=0;self.hass.async_create_task(self.async_refresh())
        if not seconds or not layout.get('pages') or self.doorbell_active:
            self.page_deadline=0;return
        if not self.page_deadline:self.page_deadline=monotonic()+seconds
        elif monotonic()>=self.page_deadline:
            self.page_index=(self.page_index+1)%(1+len(layout['pages']))
            self.page_deadline=monotonic()+seconds
            self.hass.async_create_task(self.async_refresh())

    @callback
    def stop_doorbell(self):
        if self.doorbell_timer:
            self.doorbell_timer()
        self.doorbell_timer=None
        self.doorbell_active=False
        self.doorbell_deadline=0
        self.doorbell_generation+=1
        self.doorbell_session+=1
        self.doorbell_feedback=''

    @callback
    def _arm_doorbell(self,seconds):
        if self.doorbell_timer:
            self.doorbell_timer()
        self.doorbell_generation+=1
        generation=self.doorbell_generation
        self.doorbell_deadline=monotonic()+seconds
        @callback
        def expire(_now):
            if generation==self.doorbell_generation:
                self.hide_doorbell()
        self.doorbell_timer=async_call_later(self.hass,seconds,expire)

    @callback
    def extend_doorbell(self):
        seconds=get_doorbell(self.entry.options)['post_open_duration']
        self._arm_doorbell(max(seconds,self.doorbell_deadline-monotonic()))

    @callback
    def show_doorbell(self):
        config=get_doorbell(self.entry.options)
        if not config['enabled'] or self.touch_stopped:
            return False
        self.stop_doorbell()
        self.doorbell_active=True
        self._arm_doorbell(config['duration'])
        self.hass.async_create_task(self.async_refresh())
        return True

    @callback
    def hide_doorbell(self,_now=None):
        self.stop_doorbell()
        if not self.touch_stopped:
            self.hass.async_create_task(self.async_refresh())

    async def _poll_touch(self, _now=None):
        """Acknowledge before calling HA: uncertain network results never replay an action."""
        if self.touch_stopped or self.touch_busy or self.firmware_updating or not (self.data or {}).get("touch"):
            return
        self.touch_busy = True
        try:
            async with self.io_lock:
                event = await self.client.touch()
                if event is None or self.touch_stopped:
                    return
                action = None
                if event["id"] != self.last_touch_id and event["revision"] == self.revision and (
                    self.last_layout == current_layout(self)
                ):
                    action = action_at(self.last_layout, event["x"], event["y"],event.get("gesture","tap"))
                    if (self.data or {}).get('debug_overlay') and self.last_layout.get('debug') and (
                        event['x'] >= 256 and event['y'] >= 300
                    ):
                        action = None
                if event["y"]<32 and any(n[2]>monotonic() for n in self.notifications) and not self.doorbell_active:action=None
                await self.client.acknowledge_touch(event["id"])
                self.last_touch_id = event["id"]
            if action is not None and not self.touch_stopped:
                domain, service, entity_id = action
                if domain=='desk_display' and service=='page':
                    self.page_index=int(entity_id);self.page_deadline=0;self.temporary_page=None
                    await self.async_refresh();return
                widget=widget_at(self.last_layout,event["x"],event["y"])
                feedback_entity=widget.get('entity_id') or entity_id
                state = self.hass.states.get(entity_id)
                if action_available(state, domain):
                    key=(entity_id,service)
                    if widget.get('config',{}).get('confirm') and (not self.confirm_action or self.confirm_action[0]!=key or monotonic()>self.confirm_action[1]):
                        self.confirm_action=(key,monotonic()+5);self.action_feedback[feedback_entity]=('Erneut tippen zum Bestätigen',monotonic()+5);await self.async_refresh();return
                    self.confirm_action=None
                    self.action_feedback[feedback_entity]=('Wird ausgeführt …',monotonic()+15)
                    if not self.doorbell_active:await self.async_refresh()
                    config=get_doorbell(self.entry.options)
                    overlay_action=self.doorbell_active and entity_id==config['open_entity_id']
                    if overlay_action:
                        contact=self.hass.states.get(config['door_state_entity_id']) if config['door_state_entity_id'] else None
                        if monotonic()-self.doorbell_last_press<3 or (contact and contact.state=='on'):
                            return
                        self.doorbell_last_press=monotonic()
                        session=self.doorbell_session
                        self.doorbell_feedback='pending'
                        self.extend_doorbell()
                        await self.async_refresh()
                    try:
                        async with asyncio.timeout(10):
                            await self.hass.services.async_call(
                                domain, service, command_data({**widget,"entity_id":entity_id},event.get("value_x",event["x"]),state.attributes,service), blocking=True)
                    except TimeoutError:
                        result='uncertain'
                    except Exception:
                        result='error'
                        LOGGER.warning('Display door/button action failed')
                    else:
                        result='sent'
                    self.action_feedback[feedback_entity]=({'sent':'Ausgeführt','error':'Fehlgeschlagen','uncertain':'Ergebnis unklar'}[result],monotonic()+3)
                    async_call_later(self.hass,3,lambda _:self.hass.async_create_task(self.async_refresh()) if not self.touch_stopped else None)
                    if not self.doorbell_active:await self.async_refresh()
                    if overlay_action and self.doorbell_active and self.doorbell_session==session:
                        self.doorbell_feedback=result
                        self.extend_doorbell()
                        await self.async_refresh()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            LOGGER.debug("Touch request failed", exc_info=True)
        except Exception:
            # An action that failed or timed out must not be automatically repeated.
            LOGGER.warning("Display action failed", exc_info=True)
        finally:
            self.touch_busy = False

    @callback
    def _keep_polling(self):
        """Keep interval updates alive independently of optional HA entities."""

    @callback
    def _state_changed(self, event):
        """Push changes for the current saved layout, coalescing bursts of updates."""
        entity_id = event.data.get("entity_id")
        before = event.data.get("old_state")
        after = event.data.get("new_state")
        if is_ring(get_doorbell(self.entry.options),entity_id,before,after):
            self.show_doorbell()
            return
        layout=current_layout(self)
        saved=get_layout(self.entry.options)
        from .rules import matches
        raw={'__raw__':{entity_id:(after.state if after else 'unavailable','')}}
        old={'__raw__':{entity_id:(before.state if before else 'unavailable','')}}
        for rule in saved.get('page_rules',[]):
            if rule['when']['entity_id']==entity_id and matches(rule['when'],raw) and not matches(rule['when'],old):
                self.show_page(rule['page'],rule['duration']);self.hass.async_create_task(self.async_refresh());return
        widgets=all_widgets(saved)+layout.get('overlay',{}).get('widgets',[])
        contact_changed=self.doorbell_active and entity_id==get_doorbell(self.entry.options)['door_state_entity_id']
        if not contact_changed and not any(entity_id in entities(widget) or (widget["kind"] not in ("text", "media", "image", "clock") and entity_id in (widget["entity_id"], widget.get('value',{}).get('fallback_entity_id','')))
                   for widget in widgets):
            return
        before = event.data.get("old_state")
        after = event.data.get("new_state")
        if before is not None and after is not None and (
            before.state == after.state and
            before.attributes.get("unit_of_measurement") == after.attributes.get("unit_of_measurement") and
            before.attributes.get('supported_features') == after.attributes.get('supported_features') and
            before.attributes == after.attributes
        ):
            return
        self.hass.async_create_task(self.async_request_refresh())

    async def _async_update_data(self):
        async with self.io_lock:
            if self.firmware_updating:return self.data
            return await self._update_frame()

    async def async_set_brightness(self,value):
        if not (self.data or {}).get('brightness_control'):raise ValueError('Helligkeit benoetigt Firmware 0.6.0')
        layout=get_layout(self.entry.options)
        from .device_settings import validate_settings
        layout['device']=validate_settings({**layout.get('device',{}),'brightness':value,'night_enabled':False})
        self.hass.config_entries.async_update_entry(self.entry,options={**self.entry.options,'layout':layout})
        await self.async_refresh()

    async def async_video_frame(self, signature):
        """Fast video path: no heartbeat, RGB565 conversion or touch GET per frame."""
        async with self.io_lock:
            if self.firmware_updating:return
            layout = current_layout(self)
            widget = video_widget(layout)
            if (not widget or signature != (widget['source'],widget['width'],widget['height'],widget['fps'])
                or layout != self.last_layout or not self.revision or not self.last_update_success):
                return
            media = dict(self.media.frames)
            box = (widget['x'],widget['y'],widget['x']+widget['width'],widget['y']+widget['height'])
            data = await self.hass.async_add_executor_job(render_jpeg,layout,snapshot_states(self.hass,layout),media,box)
            try:
                await self.client.push_jpeg(data,widget['x'],widget['y'],widget['width'],widget['height'],self.revision)
            except (aiohttp.ClientError, TimeoutError, ValueError):
                # Repair a reboot or rejected/stale frame through the normal heartbeat.
                self.last_frame = None
                raise

    async def _update_frame(self):
        try:
            layout = current_layout(self)
            media = getattr(self, 'media', None)
            if media:
                media.sync(layout)
            info = await self.client.info()
            if info["id"] != self.entry.unique_id:
                raise ValueError("Unter dieser Adresse antwortet ein anderes Display")
            if info.get('brightness_control'):
                from .device_settings import brightness
                value=brightness(get_layout(self.entry.options).get('device',{}),dt_util.now(),self.doorbell_active)
                if info.get('brightness')!=value:
                    await self.client.set_brightness(value);info['brightness']=value
            if video_widget(layout) and not info.get('buffered_regions'):
                raise ValueError("Video benoetigt Display-Firmware 0.3.0")
            if info.get('debug_overlay') and info.get('debug_enabled') != layout['debug']:
                await self.client.set_debug(layout['debug'])
                info['debug_enabled'] = layout['debug']
            states = snapshot_states(self.hass, layout)
            states["__media_age__"]={}
            if media:
                for session in (media,getattr(media,"preloader",None)):
                    if session and getattr(session,"signature",None):
                        stamp=max(session.updated_at or 0,session.snapshot_at or 0)
                        if stamp:states["__media_age__"][session.signature[:3]]=monotonic()-stamp
            active=[n for n in getattr(self,"notifications",[]) if n[2]>monotonic()]
            if active and not self.doorbell_active:states["__notification__"]=active[0][0]
            states["__feedback__"]={entity:value[0] for entity,value in getattr(self,"action_feedback",{}).items() if monotonic()<value[1]}
            from .history import augment_states
            await augment_states(self.hass,layout,states)
            jpeg_video = info.get('jpeg_regions') and video_widget(layout) is not None
            frame = await self.hass.async_add_executor_job(render_frame, layout, states,
                                                         dict(media.frames) if media and not jpeg_video else {})
            # Resend after a reboot even when the layout and states did not change.
            if frame != self.last_frame or layout != self.last_layout or not info.get("has_frame", False):
                # Video motion leaves the action mapping unchanged.
                revision = self.revision if layout == self.last_layout and info.get('has_frame') else uuid.uuid4().hex
                if jpeg_video:
                    data = await self.hass.async_add_executor_job(render_jpeg,layout,states,dict(media.frames) if media else {})
                    await self.client.push_jpeg(data,0,0,480,320,revision,True)
                elif info.get('buffered_regions'):
                    previous = self.last_frame if info.get('has_frame') else None
                    updates = await self.hass.async_add_executor_job(regions,frame,previous)
                    await self.client.push_regions(updates,revision)
                else:
                    await self.client.push(frame, revision)
                self.last_frame = frame
                self.last_layout = layout
                self.revision = revision
            if info.get('status_heartbeat'):await self.client.confirm_data(self.revision)
            self.last_confirmed_at=monotonic()
            self.last_confirmed_time=dt_util.utcnow()
            return info
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise UpdateFailed("Display nicht erreichbar oder Uebertragung fehlgeschlagen") from err
