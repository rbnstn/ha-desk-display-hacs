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
