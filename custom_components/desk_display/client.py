"""Local authenticated HTTP connection to the firmware."""

import aiohttp

from .models import validate_host, validate_info
from .actions import validate_touch


class DisplayClient:
    def __init__(self, session, host, key):
        self.session = session
        self.base = f"http://{validate_host(host)}"
        self.headers = {"X-Desk-Key": key}

    async def info(self):
        async with self.session.get(
            f"{self.base}/api/info", headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=5), allow_redirects=False,
        ) as response:
            response.raise_for_status()
            return validate_info(await response.json())

    async def touch(self):
        async with self.session.get(
            f"{self.base}/api/touch", headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=5), allow_redirects=False,
        ) as response:
            response.raise_for_status()
            event = (await response.json()).get("event")
            return validate_touch(event) if event is not None else None

    async def acknowledge_touch(self, event_id):
        async with self.session.post(
            f"{self.base}/api/touch/ack", params={"id": event_id}, headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=5), allow_redirects=False,
        ) as response:
            response.raise_for_status()
            if response.status != 200:
                raise ValueError("Touch acknowledgement failed")
            await response.read()

    async def push(self, frame, revision=""):
        form = aiohttp.FormData()
        form.add_field("frame", frame, filename="frame.rgb565", content_type="application/octet-stream")
        async with self.session.post(
            f"{self.base}/api/frame", params={"revision": revision}, data=form, headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=20), allow_redirects=False,
        ) as response:
            response.raise_for_status()
            if response.status != 200:
                raise ValueError("Display hat die Uebertragung nicht bestaetigt")
            await response.read()

    async def set_debug(self, enabled):
        async with self.session.post(
            f"{self.base}/api/debug", params={"enabled": '1' if enabled else '0'},
            headers=self.headers, timeout=aiohttp.ClientTimeout(total=5), allow_redirects=False,
        ) as response:
            response.raise_for_status()
            if response.status != 200:
                raise ValueError("Debug setting not confirmed")
            await response.read()

    async def set_brightness(self,value):
        async with self.session.post(f'{self.base}/api/brightness',params={'value':value},headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=5),allow_redirects=False) as response:
            response.raise_for_status();await response.read()

    async def confirm_data(self,revision):
        async with self.session.post(f'{self.base}/api/heartbeat',params={'revision':revision},headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=5),allow_redirects=False) as response:
            response.raise_for_status();await response.read()

    async def update_firmware(self,data):
        from .device_settings import validate_firmware
        validate_firmware(data)
        form=aiohttp.FormData();form.add_field('firmware',data,filename='firmware.bin',content_type='application/octet-stream')
        async with self.session.post(f'{self.base}/api/update',data=form,headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=120),allow_redirects=False) as response:
            response.raise_for_status()
            if response.status!=200:raise ValueError('Firmware nicht bestaetigt')
            await response.read()

    async def push_jpeg(self, data, x, y, width, height, revision, replace=False):
        form = aiohttp.FormData()
        form.add_field('jpeg',data,filename='frame.jpg',content_type='image/jpeg')
        async with self.session.post(f'{self.base}/api/jpeg', params={
            'x':x,'y':y,'width':width,'height':height,'revision':revision,
            'replace':'1' if replace else '0'}, data=form, headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=5), allow_redirects=False) as response:
            response.raise_for_status()
            if response.status != 200:
                raise ValueError('JPEG transfer not confirmed')
            await response.read()

    async def push_regions(self, updates, revision):
        for index, (x,y,width,height,format_,data) in enumerate(updates):
            form = aiohttp.FormData()
            form.add_field('region',data,filename='region.bin',content_type='application/octet-stream')
            async with self.session.post(
                f"{self.base}/api/region", params={
                    'x':x,'y':y,'width':width,'height':height,'format':format_,
                    'revision':revision,'final':'1' if index == len(updates)-1 else '0'},
                data=form,headers=self.headers,timeout=aiohttp.ClientTimeout(total=20),allow_redirects=False,
            ) as response:
                response.raise_for_status()
                if response.status != 200:
                    raise ValueError("Region not confirmed")
                await response.read()
