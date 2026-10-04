"""Refresh the display every ten seconds, serializing all device transfers."""

import logging
from datetime import timedelta
import aiohttp
from homeassistant.core import callback
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_LAYOUT, DOMAIN
from .models import get_layout
from .render import render_frame

LOGGER = logging.getLogger(__name__)


def snapshot_states(hass, layout):
    result = {}
    for widget in layout["widgets"]:
        if widget["kind"] != "sensor":
            continue
        state = hass.states.get(widget["entity_id"])
        if state is None or state.state in ("unknown", "unavailable"):
            result[widget["entity_id"]] = "Nicht verfuegbar"
        else:
            unit = state.attributes.get("unit_of_measurement", "")
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

    @callback
    def async_start(self):
        """The display is a consumer even when HA's diagnostic entities are disabled."""
        self.entry.async_on_unload(self.async_add_listener(self._keep_polling))
        self.entry.async_on_unload(
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._state_changed))

    @callback
    def _keep_polling(self):
        """Keep interval updates alive independently of optional HA entities."""

    @callback
    def _state_changed(self, event):
        """Push changes for the current saved layout, coalescing bursts of updates."""
        entity_id = event.data.get("entity_id")
        widgets = self.entry.options.get("layout", DEFAULT_LAYOUT)["widgets"]
        if not any(widget["kind"] == "sensor" and widget["entity_id"] == entity_id
                   for widget in widgets):
            return
        before = event.data.get("old_state")
        after = event.data.get("new_state")
        if before is not None and after is not None and (
            before.state == after.state and
            before.attributes.get("unit_of_measurement") == after.attributes.get("unit_of_measurement")
        ):
            return
        self.hass.async_create_task(self.async_request_refresh())

    async def _async_update_data(self):
        try:
            info = await self.client.info()
            if info["id"] != self.entry.unique_id:
                raise ValueError("Unter dieser Adresse antwortet ein anderes Display")
            layout = get_layout(self.entry.options)
            states = snapshot_states(self.hass, layout)
            frame = await self.hass.async_add_executor_job(render_frame, layout, states)
            # Resend after a reboot even when the layout and states did not change.
            if frame != self.last_frame or not info.get("has_frame", False):
                await self.client.push(frame)
                self.last_frame = frame
            return info
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise UpdateFailed("Display nicht erreichbar oder Uebertragung fehlgeschlagen") from err
