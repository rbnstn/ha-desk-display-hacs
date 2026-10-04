"""Device registration shared by display entities."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


class DeskDisplayEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.unique_id)},
            name=coordinator.entry.title, manufacturer="LCDWIKI",
            model="E32R35T", sw_version=(coordinator.data or {}).get("version", "unbekannt"),
        )
