"""One continuous FFmpeg decoder, bounded memory and latest-frame delivery."""

import asyncio
from contextlib import suppress
from urllib.parse import urlsplit


def decoder_command(binary, source, width, height):
    """Arguments are passed directly to exec, never to a shell."""
    if not 1 <= width <= 160 or not 1 <= height <= 120:
        raise ValueError("Video dimensions outside MVP limits")
    command = [binary, "-nostdin", "-hide_banner", "-loglevel", "error",
               "-threads", "1", "-filter_threads", "1", "-re",
               "-rw_timeout", "10000000", "-protocol_whitelist",
               "http,https,tcp,tls,rtsp,rtsps,rtmp,rtmps,udp,rtp,crypto"]
    if urlsplit(source).scheme in ("rtsp", "rtsps"):
        command += ["-rtsp_transport", "tcp"]
    return command + ["-i", source, "-an", "-sn", "-dn", "-vf",
        f"fps=2,scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
        "-pix_fmt", "rgb24", "-threads", "1", "-f", "rawvideo", "pipe:1"]


class VideoDecoder:
    def __init__(self, binary, source, width, height):
        self.command = decoder_command(binary, source, width, height)
        self.frame_size = width * height * 3
        self.latest = None
        self.sequence = 0
        self.process = None

    async def run(self):
        try:
            self.process = await asyncio.create_subprocess_exec(
                *self.command, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, limit=self.frame_size * 2)
            while True:
                async with asyncio.timeout(20):
                    frame = await self.process.stdout.readexactly(self.frame_size)
                self.latest = frame
                self.sequence += 1
        finally:
            await self.close()

    async def close(self):
        process = self.process
        if process is None:
            return
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.terminate()
            try:
                async with asyncio.timeout(3):
                    await process.wait()
            except TimeoutError:
                with suppress(ProcessLookupError):
                    process.kill()
        await process.wait()
