"""Local authenticated HTTP connection to the firmware."""

import aiohttp

from .models import validate_host, validate_info


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

    async def push(self, frame):
        form = aiohttp.FormData()
        form.add_field("frame", frame, filename="frame.rgb565", content_type="application/octet-stream")
        async with self.session.post(
            f"{self.base}/api/frame", data=form, headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=20), allow_redirects=False,
        ) as response:
            response.raise_for_status()
            if response.status != 200:
                raise ValueError("Display hat die Uebertragung nicht bestaetigt")
            await response.read()
