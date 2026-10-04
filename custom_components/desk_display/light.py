"""Display backlight, available only on firmware with PWM control."""
from homeassistant.components.light import LightEntity,ColorMode,ATTR_BRIGHTNESS
from .entity import DeskDisplayEntity
from .const import DOMAIN

async def async_setup_entry(hass,entry,async_add_entities):
    async_add_entities([Backlight(hass.data[DOMAIN][entry.entry_id])])

class Backlight(DeskDisplayEntity,LightEntity):
    _attr_name='Hintergrundbeleuchtung'
    _attr_supported_color_modes={ColorMode.BRIGHTNESS}
    _attr_color_mode=ColorMode.BRIGHTNESS
    def __init__(self,coordinator):
        super().__init__(coordinator);self._attr_unique_id=f'{coordinator.entry.unique_id}_backlight'
    @property
    def available(self):return self.coordinator.last_update_success and bool((self.coordinator.data or {}).get('brightness_control'))
    @property
    def brightness(self):return round((self.coordinator.data or {}).get('brightness',100)*255/100)
    @property
    def is_on(self):return self.brightness>0
    async def async_turn_on(self,**kwargs):
        await self.coordinator.async_set_brightness(round(kwargs.get(ATTR_BRIGHTNESS,255)*100/255))
    async def async_turn_off(self,**kwargs):await self.coordinator.async_set_brightness(0)
