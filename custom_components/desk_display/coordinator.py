"""Refresh the display every ten seconds, serializing all device transfers."""

import logging
import asyncio
import uuid
from datetime import timedelta
import aiohttp
from homeassistant.core import callback
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_LAYOUT, DOMAIN
from .models import get_layout
from .render import render_frame
from .actions import action_at
from .transport import regions

LOGGER = logging.getLogger(__name__)


def snapshot_states(hass, layout):
    result = {}
    for widget in layout["widgets"]:
        if widget["kind"] == "text":
            continue
        state = hass.states.get(widget["entity_id"])
        if state is None or state.state in ("unknown", "unavailable"):
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

    @callback
    def async_start(self):
        """The display is a consumer even when HA's diagnostic entities are disabled."""
        self.entry.async_on_unload(self.async_add_listener(self._keep_polling))
        self.entry.async_on_unload(
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._state_changed))
        stop_timer = async_track_time_interval(self.hass, self._poll_touch, timedelta(seconds=1))
        @callback
        def stop_touch():
            self.touch_stopped = True
            stop_timer()
        self.entry.async_on_unload(stop_touch)

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
                    self.last_layout == get_layout(self.entry.options)
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
                if state is not None and state.state not in ("unknown", "unavailable"):
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
        widgets = self.entry.options.get("layout", DEFAULT_LAYOUT)["widgets"]
        if not any(widget["kind"] != "text" and widget["entity_id"] == entity_id
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
        async with self.io_lock:
            return await self._update_frame()

    async def _update_frame(self):
        try:
            info = await self.client.info()
            if info["id"] != self.entry.unique_id:
                raise ValueError("Unter dieser Adresse antwortet ein anderes Display")
            layout = get_layout(self.entry.options)
            if info.get('debug_overlay') and info.get('debug_enabled') != layout['debug']:
                await self.client.set_debug(layout['debug'])
                info['debug_enabled'] = layout['debug']
            states = snapshot_states(self.hass, layout)
            frame = await self.hass.async_add_executor_job(render_frame, layout, states)
            # Resend after a reboot even when the layout and states did not change.
            if frame != self.last_frame or layout != self.last_layout or not info.get("has_frame", False):
                revision = uuid.uuid4().hex
                if info.get('buffered_regions'):
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
