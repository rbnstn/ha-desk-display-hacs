"""Diagnostic confirmation timestamp remains visible during outages."""
from homeassistant.components.sensor import SensorEntity,SensorDeviceClass
from homeassistant.const import EntityCategory
from .entity import DeskDisplayEntity
from .const import DOMAIN

async def async_setup_entry(hass,entry,async_add_entities):
    async_add_entities([ConfirmedAt(hass.data[DOMAIN][entry.entry_id])])

class ConfirmedAt(DeskDisplayEntity,SensorEntity):
    _attr_name='Letzte Datenbestätigung'
    _attr_device_class=SensorDeviceClass.TIMESTAMP
    _attr_entity_category=EntityCategory.DIAGNOSTIC
    def __init__(self,coordinator):
        super().__init__(coordinator);self._attr_unique_id=f'{coordinator.entry.unique_id}_confirmed_at'
    @property
    def available(self):return True
    @property
    def native_value(self):return getattr(self.coordinator,'last_confirmed_time',None)

