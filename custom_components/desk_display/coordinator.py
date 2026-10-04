"""Refresh the display every ten seconds, serializing all device transfers."""

import logging
import asyncio
import uuid
from datetime import timedelta
import aiohttp
from homeassistant.core import callback
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.components.lock import LockEntityFeature
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_time_interval, async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_LAYOUT, DOMAIN
from .models import get_layout
from .render import render_frame, render_jpeg
from .actions import action_at
from .transport import regions
from .doorbell import current_layout, get_doorbell, is_ring, video_widget

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
    result = {}
    for widget in layout["widgets"]+layout.get('overlay',{}).get('widgets',[]):
        if widget["kind"] in ("text", "media"):
            continue
        state = hass.states.get(widget["entity_id"])
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

    @callback
    def stop_doorbell(self):
        if self.doorbell_timer:
            self.doorbell_timer()
        self.doorbell_timer=None
        self.doorbell_active=False

    @callback
    def show_doorbell(self):
        config=get_doorbell(self.entry.options)
        if not config['enabled'] or self.touch_stopped:
            return False
        self.stop_doorbell()
        self.doorbell_active=True
        self.doorbell_timer=async_call_later(self.hass,config['duration'],self.hide_doorbell)
        self.hass.async_create_task(self.async_refresh())
        return True

    @callback
    def hide_doorbell(self,_now=None):
        self.stop_doorbell()
        if not self.touch_stopped:
            self.hass.async_create_task(self.async_refresh())

    async def _poll_touch(self, _now=None):
        """Acknowledge before calling HA: uncertain network results never replay an action."""
        if self.touch_stopped or self.touch_busy or not (self.data or {}).get("touch"):
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
                    action = action_at(self.last_layout, event["x"], event["y"])
                    if (self.data or {}).get('debug_overlay') and self.last_layout.get('debug') and (
                        event['x'] >= 256 and event['y'] >= 300
                    ):
                        action = None
                await self.client.acknowledge_touch(event["id"])
                self.last_touch_id = event["id"]
            if action is not None and not self.touch_stopped:
                domain, service, entity_id = action
                state = self.hass.states.get(entity_id)
                if action_available(state, domain):
                    await self.hass.services.async_call(
                        domain, service, {"entity_id": entity_id}, blocking=True)
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
        widgets=layout['widgets']+layout.get('overlay',{}).get('widgets',[])
        if not any(widget["kind"] not in ("text", "media") and widget["entity_id"] == entity_id
                   for widget in widgets):
            return
        before = event.data.get("old_state")
        after = event.data.get("new_state")
        if before is not None and after is not None and (
            before.state == after.state and
            before.attributes.get("unit_of_measurement") == after.attributes.get("unit_of_measurement") and
            before.attributes.get('supported_features') == after.attributes.get('supported_features') and
            before.attributes.get('code_format') == after.attributes.get('code_format')
        ):
            return
        self.hass.async_create_task(self.async_request_refresh())

    async def _async_update_data(self):
        async with self.io_lock:
            return await self._update_frame()

    async def async_video_frame(self, signature):
        """Fast video path: no heartbeat, RGB565 conversion or touch GET per frame."""
        async with self.io_lock:
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
            if video_widget(layout) and not info.get('buffered_regions'):
                raise ValueError("Video benoetigt Display-Firmware 0.3.0")
            if info.get('debug_overlay') and info.get('debug_enabled') != layout['debug']:
                await self.client.set_debug(layout['debug'])
                info['debug_enabled'] = layout['debug']
            states = snapshot_states(self.hass, layout)
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
            return info
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise UpdateFailed("Display nicht erreichbar oder Uebertragung fehlgeschlagen") from err
