"""One continuous FFmpeg decoder, bounded memory and latest-frame delivery."""

import asyncio
from contextlib import suppress
from urllib.parse import urlsplit


class VideoError(ValueError):
    """Only fixed, credential-free messages may leave the decoder."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def classify_error(data):
    text = data.decode(errors="replace").lower()
    if "option" in text and ("not found" in text or "unrecognized" in text):
        return "decoder_options"
    for code, patterns in (
        ("authentication", ("401 unauthorized", "403 forbidden", "authentication failed")),
        ("connection", ("connection refused", "network is unreachable", "no route to host", "failed to resolve hostname")),
        ("timeout", ("timed out", "timeout")),
        ("decoder_options", ("option not found", "unrecognized option", "error splitting the argument list")),
        ("source_format", ("invalid data found", "unsupported codec", "decoder not found", "protocol not found", "not on whitelist", "does not contain any stream")),
        ("source_missing", ("404 not found", "server returned 404")),
    ):
        if any(pattern in text for pattern in patterns):
            return code
    return "decoder_failed"


def decoder_command(binary, source, width, height):
    """Arguments are passed directly to exec, never to a shell."""
    if not 1 <= width <= 160 or not 1 <= height <= 120:
        raise ValueError("Video dimensions outside MVP limits")
    command = [binary, "-nostdin", "-hide_banner", "-loglevel", "error",
               "-threads", "1", "-filter_threads", "1", "-re",
               "-protocol_whitelist",
               "http,https,tcp,tls,rtsp,rtsps,rtmp,rtmps,udp,rtp,crypto"]
    if urlsplit(source).scheme in ("rtsp", "rtsps"):
        command += ["-rtsp_transport", "tcp", "-timeout", "10000000"]
    else:
        command += ["-rw_timeout", "10000000"]
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
        self.errors = b""
        self.error_task = None

    async def read_errors(self):
        while chunk := await self.process.stderr.read(4096):
            self.errors = (self.errors + chunk)[-8192:]

    async def run(self):
        try:
            self.process = await asyncio.create_subprocess_exec(
                *self.command, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, limit=self.frame_size * 2)
            self.error_task = asyncio.create_task(self.read_errors())
            while True:
                async with asyncio.timeout(20):
                    frame = await self.process.stdout.readexactly(self.frame_size)
                self.latest = frame
                self.sequence += 1
        except FileNotFoundError:
            raise VideoError("ffmpeg_missing") from None
        except TimeoutError:
            raise VideoError("timeout") from None
        except asyncio.IncompleteReadError:
            await self.close()
            raise VideoError(classify_error(self.errors)) from None
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
        if self.error_task:
            with suppress(asyncio.CancelledError):
                await self.error_task
