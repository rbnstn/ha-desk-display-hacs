"""Connectivity entity keeps periodic coordinator updates active."""

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.const import EntityCategory
from .const import DOMAIN
from .entity import DeskDisplayEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ConnectionSensor(hass.data[DOMAIN][entry.entry_id])])


class ConnectionSensor(DeskDisplayEntity, BinarySensorEntity):
    _attr_name = "Verbindung"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.unique_id}_connection"

    @property
    def available(self):
        return True

    @property
    def is_on(self):
        return self.coordinator.last_update_success
