"""Resolve saved HA sources and supervise their continuous video decoder."""

import asyncio
import logging
from contextlib import suppress

from homeassistant.components.camera import async_get_stream_source
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.components.media_source import async_resolve_media
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from .models import get_layout, validate_media_source
from .video import VideoDecoder, VideoError

LOGGER = logging.getLogger(__name__)

MESSAGES = {
    "camera_no_stream": "Diese HA-Kamera liefert keine Stream-URL. Bitte eine Live-/Substream-Entitaet statt einer Snapshot-Entitaet waehlen.",
    "not_video": "Die ausgewaehlte Medienquelle liefert kein Video.",
    "resolve_failed": "HA konnte die Medienquelle nicht aufloesen. Kamera-Verfuegbarkeit und Quellenwahl pruefen.",
    "authentication": "Die Videoquelle lehnt die Anmeldung ab. Zugangsdaten in der HA-Kameraintegration pruefen.",
    "connection": "Die Videoquelle ist vom HA-Host aus nicht erreichbar. Adresse, Stream-Port und Netzwerk pruefen.",
    "timeout": "Die Videoquelle liefert innerhalb der Wartezeit keinen Frame. Live-/Substream und Erreichbarkeit pruefen.",
    "decoder_options": "FFmpeg lehnt eine Stream-Option ab. FFmpeg-Version und Desk-Display-Update pruefen.",
    "source_format": "FFmpeg kann diese Quelle nicht als Video dekodieren. Streamformat oder Substream pruefen.",
    "source_missing": "Die Videoquelle wurde nicht gefunden (404). Quellenwahl pruefen.",
    "ffmpeg_missing": "FFmpeg wurde auf dem HA-Host nicht gefunden.",
    "decoder_failed": "Der Video-Decoder wurde ohne nutzbaren Frame beendet. Videoquelle oder Substream pruefen.",
}


async def resolve_source(hass, source):
    validate_media_source(source)
    if source.startswith("media-source://camera/"):
        source = source.split("/", 3)[-1]
    if source.startswith("camera."):
        source = await async_get_stream_source(hass, source)
        if not source:
            raise VideoError("camera_no_stream")
    elif source.startswith("media-source://"):
        media = await async_resolve_media(hass, source, None)
        if not (media.mime_type.startswith("video/") or media.mime_type in (
            "application/vnd.apple.mpegurl", "application/x-mpegURL", "application/dash+xml"
        )):
            raise VideoError("not_video")
        source = media.url
    # HA signs protected local media URLs. No HA token is sent to the ESP32.
    source = async_process_play_media_url(hass, source)
    validate_media_source(source)
    return source


class MediaWorker:
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.hass = coordinator.hass
        self.task = None
        self.signature = None
        self.frames = {}
        self.status = "idle"
        self.error_code = None

    @callback
    def start(self):
        self.coordinator.entry.async_on_unload(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop))
        self.coordinator.entry.async_on_unload(self.stop)
        self.sync(get_layout(self.coordinator.entry.options))

    @callback
    def stop(self, _event=None):
        self.signature = None
        self.frames.clear()
        self.status = "idle"
        self.error_code = None
        if self.task:
            self.task.cancel()
        self.task = None

    def sync(self, layout):
        widget = next((w for w in layout["widgets"] if w["kind"] == "media"), None)
        signature = (widget["source"], widget["width"], widget["height"]) if widget else None
        if signature == self.signature:
            return
        self.stop()
        self.signature = signature
        self.status = "connecting" if signature else "idle"
        if signature:
            self.task = self.coordinator.entry.async_create_background_task(
                self.hass, self.run(signature), "Desk Display video")

    async def run(self, signature):
        """Drain the source continuously; drop old frames when the display is slower."""
        source, width, height = signature
        while self.signature == signature:
            decoder_task = None
            stage = "resolve"
            try:
                async with asyncio.timeout(30):
                    url = await resolve_source(self.hass, source)
                stage = "decode"
                decoder = VideoDecoder(get_ffmpeg_manager(self.hass).binary, url, width, height)
                decoder_task = asyncio.create_task(decoder.run())
                sequence = 0
                while self.signature == signature:
                    await asyncio.sleep(0.5)
                    if decoder.latest is not None and decoder.sequence != sequence:
                        self.frames[signature] = decoder.latest
                        sequence = decoder.sequence
                        self.status = "live"
                        self.error_code = None
                        # Drain a pending touch before a firmware frame clears its event.
                        await self.coordinator._poll_touch()
                        await self.coordinator.async_refresh()
                    if decoder_task.done():
                        await decoder_task
            except asyncio.CancelledError:
                raise
            except Exception as err:
                # FFmpeg errors and URLs may contain credentials; never log them.
                self.status = "unavailable"
                self.error_code = err.code if isinstance(err, VideoError) else (
                    "timeout" if isinstance(err, TimeoutError) else "resolve_failed" if stage == "resolve" else "decoder_failed")
                self.frames.clear()
                LOGGER.warning("Desk Display video unavailable (%s); retrying in 10 seconds", self.error_code)
            finally:
                if decoder_task is not None:
                    decoder_task.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await decoder_task
            if self.signature != signature:
                return
            await self.coordinator.async_refresh()
            await asyncio.sleep(10)
