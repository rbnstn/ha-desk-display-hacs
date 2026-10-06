"""Native version notices; firmware installation uses the verified OTA path."""
import aiohttp
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.exceptions import HomeAssistantError
from .entity import DeskDisplayEntity
from .const import DOMAIN
from .releases import latest_release


async def async_setup_entry(hass,entry,async_add_entities):
    coordinator=hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DisplayUpdate(coordinator,False),DisplayUpdate(coordinator,True)],True)


class DisplayUpdate(DeskDisplayEntity,UpdateEntity):
    _attr_should_poll=True
    def __init__(self,coordinator,firmware):
        super().__init__(coordinator);self.firmware=firmware;self.release={}
        self._attr_name='Firmware' if firmware else 'Integration'
        self._attr_unique_id=f'{coordinator.entry.unique_id}_update_'+('firmware' if firmware else 'integration')
        self._attr_supported_features=UpdateEntityFeature.INSTALL if firmware else UpdateEntityFeature(0)
    @property
    def available(self):return bool(self.release) and (not self.firmware or self.coordinator.last_update_success)
    @property
    def installed_version(self):return (self.coordinator.data or {}).get('version') if self.firmware else self.release.get('installed')
    @property
    def latest_version(self):return self.release.get('firmware' if self.firmware else 'latest')
    @property
    def release_url(self):return self.release.get('url')
    @property
    def in_progress(self):return bool(self.firmware and self.coordinator.firmware_updating)
    async def async_update(self):
        try:self.release=await latest_release(self.hass)
        except (aiohttp.ClientError,TimeoutError,ValueError,KeyError):return
    async def async_install(self,version,backup,**kwargs):
        from .firmware import install_payload
        from .device_settings import validate_firmware
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        if not self.firmware:raise HomeAssistantError('Integration bitte über HACS aktualisieren')
        if self.coordinator.firmware_updating:raise HomeAssistantError('Update läuft bereits')
        try:
            release=await latest_release(self.hass)
            if version and version!=release.get('firmware'):raise ValueError('Nur aktuelles Release unterstützt')
            async with async_get_clientsession(self.hass).get(release['firmware_url'],timeout=aiohttp.ClientTimeout(total=90)) as response:
                response.raise_for_status();data=bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    data.extend(chunk)
                    if len(data)>1310720:raise ValueError('Firmware zu groß')
            payload=validate_firmware(bytes(data))
            if f"desk_display_version:{release['firmware']}".encode() not in payload:raise ValueError('Firmwareversion stimmt nicht überein')
            await install_payload(self.hass,self.coordinator,payload)
        except (aiohttp.ClientError,TimeoutError,ValueError,KeyError) as error:raise HomeAssistantError(str(error)) from error
