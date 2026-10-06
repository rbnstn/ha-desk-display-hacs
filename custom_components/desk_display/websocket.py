"""Authenticated editor API; device keys never reach the editor."""

import base64
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import callback

from .const import DOMAIN
from .coordinator import snapshot_states
from .models import get_layout, validate_layout
from .render import render_preview
from .doorbell import get_doorbell, validate_doorbell, overlay_layout


@callback
def register_commands(hass):
    for handler in (list_displays, preview, save, media_browse, doorbell_test, doorbell_status, diagnostics, ringing_history, inspect, updates):
        websocket_api.async_register_command(hass, handler)


@websocket_api.websocket_command({"type": "desk_display/list"})
@websocket_api.require_admin
@callback
def list_displays(hass, connection, msg):
    connection.send_result(msg["id"], [
        {"id": entry.entry_id, "name": entry.title, "host": entry.data["host"],
         "connected": bool((coordinator := hass.data[DOMAIN].get(entry.entry_id))
                           and coordinator.last_update_success),
         "touch": bool(coordinator and (coordinator.data or {}).get("touch")),
         "debug_overlay": bool(coordinator and (coordinator.data or {}).get("debug_overlay")),
         "jpeg_regions": bool(coordinator and (coordinator.data or {}).get("jpeg_regions")),
         "layout": get_layout(entry.options), "doorbell":get_doorbell(entry.options),
         "backups":entry.options.get('backups',[]),
         "firmware":(coordinator.data or {}).get('version','unbekannt') if coordinator else 'unbekannt',
         "brightness_control":bool(coordinator and (coordinator.data or {}).get('brightness_control')),
         "ota_update":bool(coordinator and (coordinator.data or {}).get('ota_update')),
         "confirmed_at":getattr(coordinator,'last_confirmed_time',None).isoformat() if coordinator and getattr(coordinator,'last_confirmed_time',None) else None,
         "doorbell_active":bool(coordinator and coordinator.doorbell_active)}
        for entry in hass.config_entries.async_entries(DOMAIN)
    ])


@websocket_api.websocket_command({"type": "desk_display/preview", vol.Required("layout"): dict,
                                  vol.Optional('doorbell'):dict, vol.Optional('overlay',default=False):bool,
                                  vol.Optional('simulation'):dict,vol.Optional('entry_id'):str,vol.Optional('page',default=0):vol.All(int,vol.Range(min=0,max=3))})
@websocket_api.require_admin
@websocket_api.async_response
async def preview(hass, connection, msg):
    try:
        layout = validate_layout(msg["layout"])
        from .pages import page_layout
        layout=page_layout(layout,msg.get('page',0))
        if msg.get('overlay'):
            config=validate_doorbell(msg.get('doorbell',{}))
            layout['overlay']=overlay_layout(config, layout.get('theme', 'classic'))
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_layout", str(err))
        return
    states = snapshot_states(hass, layout)
    selected=hass.data.get(DOMAIN,{}).get(msg.get('entry_id',''))
    if selected and hasattr(selected,'ring_history'):states['__ring_history__']=selected.ring_history.snapshot(hass.config.time_zone)
    from .history import augment_states
    await augment_states(hass,layout,states)
    try:
        from .simulation import apply_simulation
        simulated=apply_simulation(states,layout,msg.get('simulation',{}))
    except ValueError as error:
        connection.send_error(msg['id'],'invalid_simulation',str(error));return
    frames = {}
    states["__media_age__"]={}
    statuses = []
    for coordinator in hass.data.get(DOMAIN, {}).values():
        if (worker := getattr(coordinator, 'media', None)):
            frames.update(worker.frames)
            from .media import MESSAGES
            for session in (worker,getattr(worker,'preloader',None)):
                if session is None:
                    continue
                if session.signature:
                    stamp=max(session.updated_at or 0,session.snapshot_at or 0)
                    if stamp:states["__media_age__"][session.signature[:3]]=__import__("time").monotonic()-stamp
                for index, widget in enumerate(layout.get('overlay',layout)['widgets']):
                    if widget['kind'] == 'media' and session.signature and session.signature[:3] == (
                        widget['source'], widget['width'], widget['height']
                    ) and not any(item['index']==index for item in statuses):
                        statuses.append({'index':index, 'state':session.status,
                                         'message':MESSAGES.get(session.error_code, '')})
    image = await hass.async_add_executor_job(render_preview, layout, states, frames)
    connection.send_result(msg["id"], {"png": base64.b64encode(image).decode("ascii"),
                                      "media_status":statuses,"simulated":simulated})


@websocket_api.websocket_command({"type": "desk_display/save", vol.Required("entry_id"): str,
                                  vol.Required("layout"): dict,vol.Optional('doorbell'):dict,
                                  vol.Optional('page',default=0):vol.All(int,vol.Range(min=0,max=3))})
@websocket_api.require_admin
@websocket_api.async_response
async def save(hass, connection, msg):
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "Display nicht gefunden")
        return
    try:
        layout = validate_layout(msg["layout"])
        doorbell=validate_doorbell(msg['doorbell']) if 'doorbell' in msg else get_doorbell(entry.options)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_layout", str(err))
        return
    from homeassistant.util import dt as dt_util
    backups=list(entry.options.get('backups',[]))
    previous={'layout':get_layout(entry.options),'doorbell':get_doorbell(entry.options)}
    if previous!={'layout':layout,'doorbell':doorbell}:
        backups=([{'at':dt_util.utcnow().isoformat(),**previous}]+backups)[:3]
    hass.config_entries.async_update_entry(entry, options={**entry.options, "layout": layout,'doorbell':doorbell,'backups':backups})
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    sent = False
    if coordinator is not None:
        await coordinator.ring_history.configure(doorbell)
        coordinator.stop_doorbell()
        coordinator.page_index=min(msg.get('page',0),len(layout.get('pages',[])))
        coordinator.page_deadline=0
        await coordinator.async_refresh()
        sent = coordinator.last_update_success
    connection.send_result(msg["id"], {"saved": True, "sent": sent,"backups":backups})


@websocket_api.websocket_command({'type':'desk_display/doorbell_test',vol.Required('entry_id'):str,
                                  vol.Required('active'):bool})
@websocket_api.require_admin
@websocket_api.async_response
async def doorbell_test(hass,connection,msg):
    entry=hass.config_entries.async_get_entry(msg['entry_id'])
    coordinator=hass.data.get(DOMAIN,{}).get(msg['entry_id'])
    if entry is None or entry.domain!=DOMAIN or coordinator is None:
        connection.send_error(msg['id'],'not_found','Display nicht gefunden')
        return
    if msg['active']:
        if not coordinator.show_doorbell():
            connection.send_error(msg['id'],'disabled','Bitte Klingel-Overlay aktivieren und speichern')
            return
    else:
        coordinator.stop_doorbell()
    await coordinator.async_refresh()
    connection.send_result(msg['id'],{'active':coordinator.doorbell_active,'sent':coordinator.last_update_success})


@websocket_api.websocket_command({'type':'desk_display/doorbell_status',vol.Required('entry_id'):str})
@websocket_api.require_admin
@callback
def doorbell_status(hass,connection,msg):
    coordinator=hass.data.get(DOMAIN,{}).get(msg['entry_id'])
    if coordinator is None:
        connection.send_error(msg['id'],'not_found','Display nicht gefunden')
        return
    worker=getattr(getattr(coordinator,'media',None),'preloader',None)
    connection.send_result(msg['id'],worker.readiness() if worker else {'state':'disabled'})


@websocket_api.websocket_command({"type": "desk_display/media_browse",
                                  vol.Optional("media_content_id", default=None): vol.Any(None, str)})
@websocket_api.require_admin
@websocket_api.async_response
async def media_browse(hass, connection, msg):
    from homeassistant.components.media_source import async_browse_media
    try:
        item = await async_browse_media(hass, msg["media_content_id"],
                                      content_filter=lambda item: item.media_class == "video")
        connection.send_result(msg["id"], item.as_dict())
    except Exception:
        connection.send_error(msg["id"], "media_unavailable", "Medienquelle nicht verfuegbar")


@websocket_api.websocket_command({'type':'desk_display/diagnostics',vol.Required('entry_id'):str})
@websocket_api.require_admin
@callback
def diagnostics(hass,connection,msg):
    coordinator=hass.data.get(DOMAIN,{}).get(msg['entry_id'])
    if coordinator is None:
        connection.send_error(msg['id'],'not_found','Display nicht gefunden');return
    data=coordinator.data or {}
    connection.send_result(msg['id'],{'connected':coordinator.last_update_success,'firmware':data.get('version','unbekannt'),
        'brightness_control':bool(data.get('brightness_control')),'ota_update':bool(data.get('ota_update')),
        'age':round(__import__('time').monotonic()-coordinator.last_confirmed_at) if coordinator.last_confirmed_at else None,
        **{key:data.get(key) for key in ('rssi','free_heap','min_free_heap','uptime','reset_reason','boot_id','sleeping')},
        'render_ms':getattr(coordinator,'last_render_ms',None),'transfer_ms':getattr(coordinator,'last_transfer_ms',None),
        'transfer_bytes':getattr(coordinator,'last_transfer_bytes',0),
        'camera_age':getattr(getattr(coordinator,'media',None),'readiness',lambda:{})().get('age'),
        'update':getattr(coordinator,'firmware_status',None)})


@websocket_api.websocket_command({'type':'desk_display/ringing_history',vol.Required('entry_id'):str,vol.Optional('clear',default=False):bool})
@websocket_api.require_admin
@websocket_api.async_response
async def ringing_history(hass,connection,msg):
    coordinator=hass.data.get(DOMAIN,{}).get(msg['entry_id'])
    if coordinator is None:
        connection.send_error(msg['id'],'not_found','Display nicht gefunden');return
    if msg.get('clear'):await coordinator.ring_history.clear();await coordinator.async_refresh()
    connection.send_result(msg['id'],{'records':coordinator.ring_history.snapshot(hass.config.time_zone)})



@websocket_api.websocket_command({'type':'desk_display/inspect',vol.Required('layout'):dict})
@websocket_api.require_admin
@websocket_api.async_response
async def inspect(hass,connection,msg):
    try:
        layout=validate_layout(msg['layout'])
        from .inspection import inspect_text
        from .pages import page_layout
        states=[snapshot_states(hass,page_layout(layout,i)) for i in range(1+len(layout.get('pages',[])))]
        result=await hass.async_add_executor_job(inspect_text,layout,states)
    except ValueError as error:
        connection.send_error(msg['id'],'invalid_layout',str(error));return
    connection.send_result(msg['id'],result)


@websocket_api.websocket_command({'type':'desk_display/updates'})
@websocket_api.require_admin
@websocket_api.async_response
async def updates(hass,connection,msg):
    import json,re
    from pathlib import Path
    from time import monotonic
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    import aiohttp
    cached=hass.data.get('desk_display_release_cache')
    if cached and monotonic()-cached[0]<900:
        connection.send_result(msg['id'],cached[1]);return
    try:
        async with async_get_clientsession(hass).get('https://api.github.com/repos/rbnstn/ha-desk-display-hacs/releases/latest',timeout=aiohttp.ClientTimeout(total=10)) as response:
            response.raise_for_status();release=await response.json()
        installed=await hass.async_add_executor_job(lambda:json.loads(Path(__file__).with_name('manifest.json').read_text())['version'])
        result={'installed':installed,'latest':release['tag_name'].removeprefix('v'),'title':release['name'],'url':release['html_url']}
        for asset in release.get('assets',[]):
            version=re.fullmatch(r'desk-display-e32r35t-([0-9]+\.[0-9]+\.[0-9]+)\.bin',asset['name'])
            if version:result.update(firmware=version.group(1),firmware_url=asset['browser_download_url'])
        hass.data['desk_display_release_cache']=(monotonic(),result)
        connection.send_result(msg['id'],result)
    except (aiohttp.ClientError,TimeoutError,ValueError,KeyError):
        connection.send_error(msg['id'],'update_check_failed','Updates derzeit nicht abrufbar. Bitte später erneut versuchen.')
