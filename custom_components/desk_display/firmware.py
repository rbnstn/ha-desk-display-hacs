"""Admin-only firmware upload, with device identity and size checks."""
import aiohttp
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.http import KEY_HASS
from .const import DOMAIN
from .device_settings import validate_firmware

class FirmwareUpload(HomeAssistantView):
    url='/api/desk_display/{entry_id}/firmware'
    name='api:desk_display:firmware'
    requires_auth=True

    async def post(self,request,entry_id):
        if not request['hass_user'].is_admin:return self.json({'message':'Administrator erforderlich'},status_code=403)
        hass=request.app[KEY_HASS];coordinator=hass.data.get(DOMAIN,{}).get(entry_id)
        if not coordinator:return self.json({'message':'Display nicht gefunden'},status_code=404)
        if coordinator.firmware_updating:return self.json({'message':'Update läuft bereits'},status_code=409)
        data=bytearray()
        async for chunk in request.content.iter_chunked(65536):
            data.extend(chunk)
            if len(data)>1310720:return self.json({'message':'Firmware zu groß'},status_code=413)
        try:payload=validate_firmware(bytes(data))
        except ValueError as error:return self.json({'message':str(error)},status_code=400)
        coordinator.firmware_updating=True
        try:
            async with coordinator.io_lock:
                info=await coordinator.client.info()
                if info['id']!=coordinator.entry.unique_id:raise ValueError('Unter dieser Adresse antwortet ein anderes Display')
                if not info.get('ota_update'):raise ValueError('Zuerst Firmware 0.6.0 per USB installieren')
                await coordinator.client.update_firmware(payload)
            coordinator.last_frame=None;coordinator.revision=None
            return self.json({'message':'Firmware bestätigt. Display startet neu.'})
        except (ValueError,aiohttp.ClientError,TimeoutError):
            return self.json({'message':'Update nicht bestätigt. Firmware und Verbindung prüfen; bei Abbruch gegebenenfalls per USB wiederherstellen.'},status_code=502)
        finally:coordinator.firmware_updating=False
