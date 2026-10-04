"""Desk Display integration entry point."""

from pathlib import Path
from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import DisplayClient
from .const import DOMAIN, PLATFORMS
from .coordinator import DeskDisplayCoordinator
from .websocket import register_commands


async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    register_commands(hass)
    await hass.http.async_register_static_paths([
        StaticPathConfig("/desk-display/panel.js",
                         str(Path(__file__).parent / "frontend" / "panel.js"), False)
    ])
    await panel_custom.async_register_panel(
        hass, frontend_url_path="desk-display", webcomponent_name="desk-display-panel",
        sidebar_title="Desk Display", sidebar_icon="mdi:monitor-dashboard",
        module_url="/desk-display/panel.js?v=0.4.1", require_admin=True,
    )
    return True


async def async_setup_entry(hass, entry):
    client = DisplayClient(async_get_clientsession(hass), entry.data["host"], entry.data["key"])
    coordinator = DeskDisplayCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True
    return False
