"""Admin-only firmware upload, with device identity and size checks."""
import aiohttp
import asyncio
import re
from time import monotonic
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
        if coordinator.firmware_updating:return self.json({'message':'Update läuft bereits'},status_code=409)
        try:payload=validate_firmware(bytes(data))
        except ValueError as error:return self.json({'message':str(error)},status_code=400)
        try:
            expected=await install_payload(hass,coordinator,payload)
            return self.json({'message':'Übertragung bestätigt. Neustart und Version werden geprüft.','expected':expected})
        except (ValueError,aiohttp.ClientError,TimeoutError) as error:
            return self.json({'message':str(error)},status_code=502)


async def install_payload(hass,coordinator,payload):
    if coordinator.firmware_updating:raise ValueError('Update läuft bereits')
    payload=validate_firmware(payload)
    marker=re.search(rb'desk_display_version:([0-9]+\.[0-9]+\.[0-9]+)',payload)
    expected=marker.group(1).decode() if marker else None
    coordinator.firmware_status={'phase':'transferring','expected':expected}
    coordinator.firmware_updating=True
    monitor_started=False
    try:
        async with coordinator.io_lock:
            info=await coordinator.client.info()
            if info['id']!=coordinator.entry.unique_id:raise ValueError('Unter dieser Adresse antwortet ein anderes Display')
            if not info.get('ota_update'):raise ValueError('Zuerst Firmware 0.6.0 per USB installieren')
            await coordinator.client.update_firmware(payload)
        coordinator.last_frame=None;coordinator.revision=None
        coordinator.firmware_status={'phase':'restarting','expected':expected,'previous':info.get('version')}
        coordinator.entry.async_create_background_task(hass,monitor_restart(coordinator,info,expected),'Desk Display firmware restart')
        monitor_started=True
        return expected
    except (ValueError,aiohttp.ClientError,TimeoutError):
        coordinator.firmware_status={'phase':'failed','message':'Übertragung nicht bestätigt'}
        raise ValueError('Update nicht bestätigt. Firmware und Verbindung prüfen; bei Abbruch per USB wiederherstellen.')
    finally:
        if not monitor_started:coordinator.firmware_updating=False


async def monitor_restart(coordinator,before,expected):
    deadline=monotonic()+90
    disconnected=False
    try:
        await asyncio.sleep(3)
        while monotonic()<deadline:
            try:
                async with coordinator.io_lock:info=await coordinator.client.info()
                if info['id']!=coordinator.entry.unique_id:
                    coordinator.firmware_status={'phase':'failed','message':'Unter dieser Adresse antwortet ein anderes Display'};return
                if before.get('boot_id') and info.get('boot_id'):
                    restarted=info['boot_id']!=before['boot_id']
                elif isinstance(before.get('uptime'),(int,float)) and isinstance(info.get('uptime'),(int,float)):
                    restarted=info['uptime']<before['uptime'] or info.get('version')!=before.get('version')
                else:
                    restarted=disconnected or info.get('version')!=before.get('version')
                if restarted:
                    if expected and info.get('version')!=expected:
                        coordinator.firmware_status={'phase':'failed','message':'Installierte Version stimmt nicht mit der Datei überein','installed':info.get('version'),'expected':expected};return
                    coordinator.firmware_status={'phase':'verified' if expected else 'connected_unverified','installed':info.get('version'),'expected':expected}
                    coordinator.last_frame=None;coordinator.revision=None;return
            except (aiohttp.ClientError,TimeoutError,ValueError):disconnected=True
            await asyncio.sleep(2)
        coordinator.firmware_status={'phase':'failed','message':'Neustart innerhalb von 90 Sekunden nicht bestätigt','expected':expected}
    finally:
        coordinator.firmware_updating=False
        if not coordinator.touch_stopped:await coordinator.async_request_refresh()
