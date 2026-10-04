"""Authenticated editor API; device keys never reach the editor."""

import base64
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import callback

from .const import DOMAIN
from .coordinator import snapshot_states
from .models import get_layout, validate_layout
from .render import render_preview


@callback
def register_commands(hass):
    for handler in (list_displays, preview, save):
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
         "layout": get_layout(entry.options)}
        for entry in hass.config_entries.async_entries(DOMAIN)
    ])


@websocket_api.websocket_command({"type": "desk_display/preview", vol.Required("layout"): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def preview(hass, connection, msg):
    try:
        layout = validate_layout(msg["layout"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_layout", str(err))
        return
    states = snapshot_states(hass, layout)
    image = await hass.async_add_executor_job(render_preview, layout, states)
    connection.send_result(msg["id"], {"png": base64.b64encode(image).decode("ascii")})


@websocket_api.websocket_command({"type": "desk_display/save", vol.Required("entry_id"): str,
                                  vol.Required("layout"): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def save(hass, connection, msg):
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "Display nicht gefunden")
        return
    try:
        layout = validate_layout(msg["layout"])
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_layout", str(err))
        return
    hass.config_entries.async_update_entry(entry, options={**entry.options, "layout": layout})
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    sent = False
    if coordinator is not None:
        await coordinator.async_refresh()
        sent = coordinator.last_update_success
    connection.send_result(msg["id"], {"saved": True, "sent": sent})
