"""Force refresh control in HA; this is not a touchscreen button."""

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN
from .entity import DeskDisplayEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([RefreshButton(hass.data[DOMAIN][entry.entry_id])])


class RefreshButton(DeskDisplayEntity, ButtonEntity):
    _attr_name = "Anzeige aktualisieren"
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_refresh"

    async def async_press(self):
        self.coordinator.last_frame = None
        await self.coordinator.async_refresh()
        if not self.coordinator.last_update_success:
            raise HomeAssistantError("Display konnte nicht aktualisiert werden")
