"""Resolve saved HA sources and supervise their continuous video decoder."""

import asyncio
import logging
from time import monotonic
from contextlib import suppress

from homeassistant.components.camera import async_get_stream_source, async_get_image
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.components.media_source import async_resolve_media
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.core import callback
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from .models import get_layout, validate_media_source
from .video import VideoDecoder, VideoError
from .doorbell import current_layout, video_widget, get_doorbell, overlay_layout
from .poster import camera_tile

LOGGER = logging.getLogger(__name__)

MESSAGES = {
    "firmware_required": "Diese Videogroesse benoetigt Display-Firmware 0.5.0. Bis dahin maximal 160 x 120 Pixel.",
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
    def __init__(self, coordinator, owner=None):
        self.coordinator = coordinator
        self.hass = coordinator.hass
        self.task = None
        self.signature = None
        self.owner = owner
        self.preloader = None
        self._frames = {}
        self.updated_at = None
        self.snapshot_task = None
        self.snapshot = None
        self.snapshot_at = None
        self.last_upload_at = 0
        self.status = "idle"
        self.error_code = None

    @property
    def frames(self):
        if self.owner is not None:
            if self.signature and self.snapshot is not None and (not self._frames or (self.snapshot_at or 0)>(self.updated_at or 0)):
                return {self.signature[:3]:self.snapshot}
            return self._frames
        if self.preloader is None:
            return self._frames
        return {**self._frames, **self.preloader.frames}

    def visible(self, signature):
        return self.owner is None or self.owner.signature == signature

    def readiness(self):
        if not self.signature:
            return {'state':'disabled'}
        if self.frames:
            stream = self.updated_at is not None and monotonic()-self.updated_at <= 2.5
            age = monotonic()-max(self.updated_at or 0,self.snapshot_at or 0)
            return {'state':'ready','mode':'stream' if stream else 'snapshot','age':round(age,1)}
        return {'state':'unavailable' if self.status=='unavailable' else 'connecting',
                'message':MESSAGES.get(self.error_code,'Noch kein aktuelles Kamerabild vorhanden.')}

    async def publish(self, signature, fast):
        if not self.visible(signature) or monotonic()-self.last_upload_at < 1:
            return
        self.last_upload_at = monotonic()
        if fast:
            await self.coordinator.async_video_frame(signature)
        else:
            await self.coordinator._poll_touch()
            await self.coordinator.async_refresh()

    async def prepare_snapshot(self, signature):
        """Keep a fresh HA still image while the stream starts or stops producing frames."""
        source,width,height=signature[:3]
        while self.signature==signature:
            try:
                if self.updated_at is None or monotonic()-self.updated_at > 2.5:
                    async with asyncio.timeout(4):
                        image=await async_get_image(self.hass,source,timeout=4,width=width,height=height)
                    tile=await self.hass.async_add_executor_job(camera_tile,image.content,width,height)
                    if self.signature!=signature:
                        return
                    self.snapshot=tile
                    self.snapshot_at=monotonic()
                    await self.publish(signature,bool((self.coordinator.data or {}).get('jpeg_regions')))
            except asyncio.CancelledError:
                raise
            except Exception:
                # Camera responses and exception strings can include secrets.
                pass
            await asyncio.sleep(2)

    @property
    def status(self):
        if self.preloader is not None and self.signature == self.preloader.signature:
            return self.preloader.status
        return self._status

    @status.setter
    def status(self, value):
        self._status = value

    @property
    def error_code(self):
        if self.preloader is not None and self.signature == self.preloader.signature:
            return self.preloader.error_code
        return self._error_code

    @error_code.setter
    def error_code(self, value):
        self._error_code = value

    @callback
    def start(self):
        self.coordinator.entry.async_on_unload(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.stop))
        self.coordinator.entry.async_on_unload(self.stop)
        self.sync(current_layout(self.coordinator))

    @callback
    def stop(self, _event=None):
        if self.preloader is not None:
            self.preloader.stop()
            self.preloader = None
        self._stop_active()

    def _stop_active(self):
        self.signature = None
        self._frames.clear()
        self.updated_at = None
        self.snapshot = None
        self.snapshot_at = None
        self.last_upload_at = 0
        if self.snapshot_task:
            self.snapshot_task.cancel()
        self.snapshot_task = None
        self.status = "idle"
        self.error_code = None
        if self.task:
            self.task.cancel()
        self.task = None

    def sync(self, layout):
        config = get_doorbell(self.coordinator.entry.options)
        warm_widget = video_widget(overlay_layout(config)) if config['enabled'] and config['preload'] else None
        warm_signature = (warm_widget['source'],warm_widget['width'],warm_widget['height'],1) if warm_widget else None
        if warm_signature:
            if self.preloader is None:
                self.preloader = MediaWorker(self.coordinator, owner=self)
            self.preloader._select(warm_signature)
        elif self.preloader is not None:
            self.preloader.stop()
            self.preloader = None
        widget = video_widget(layout)
        signature = (widget["source"], widget["width"], widget["height"], widget['fps']) if widget else None
        delegated = warm_signature is not None and signature == warm_signature
        if signature == self.signature and (self.task is None) == (signature is None or delegated):
            return
        base=next((w for w in layout['widgets'] if w['kind']=='media'),None)
        key=(base['source'],base['width'],base['height']) if base else None
        cached=self._frames.get(key)
        self._select(signature, start=not delegated)
        if signature and cached is not None and (warm_signature is None or key != warm_signature[:3]):
            self._frames[key]=cached

    def _select(self, signature, start=True):
        if signature == self.signature and (self.task is not None) == bool(signature and start):
            return
        self._stop_active()
        self.signature = signature
        self.status = "connecting" if signature else "idle"
        if signature and start:
            self.task = self.coordinator.entry.async_create_background_task(
                self.hass, self.run(signature), "Desk Display video")
            if self.owner is not None and signature[0].startswith('camera.'):
                self.snapshot_task = self.coordinator.entry.async_create_background_task(
                    self.hass,self.prepare_snapshot(signature),'Desk Display camera preparation')

    async def run(self, signature):
        """Drain the source continuously; drop old frames when the display is slower."""
        source, width, height = signature[:3]
        while self.signature == signature:
            decoder_task = None
            stage = "resolve"
            try:
                async with asyncio.timeout(30):
                    url = await resolve_source(self.hass, source)
                stage = "decode"
                fast = bool((self.coordinator.data or {}).get('jpeg_regions'))
                fps = 1
                if not fast and (width>160 or height>120):
                    raise VideoError('firmware_required')
                decoder = VideoDecoder(get_ffmpeg_manager(self.hass).binary, url, width, height, fps)
                decoder_task = asyncio.create_task(decoder.run())
                sequence = 0
                deadline = monotonic()
                while self.signature == signature:
                    await asyncio.sleep(max(0,deadline-monotonic()))
                    if decoder.latest is not None and decoder.sequence != sequence:
                        self._frames[signature[:3]] = decoder.latest
                        self.updated_at = monotonic()
                        sequence = decoder.sequence
                        self.status = "live"
                        self.error_code = None
                        # Drain a pending touch before a firmware frame clears its event.
                        await self.publish(signature,fast)
                    if decoder_task.done():
                        await decoder_task
                    # Leave a full interval after processing, including lock waits.
                    # A late transfer must never produce a catch-up burst.
                    deadline = monotonic()+1/fps
            except asyncio.CancelledError:
                raise
            except Exception as err:
                # FFmpeg errors and URLs may contain credentials; never log them.
                self.status = "unavailable"
                self.error_code = err.code if isinstance(err, VideoError) else (
                    "timeout" if isinstance(err, TimeoutError) else "resolve_failed" if stage == "resolve" else "decoder_failed")
                # Retain the last frame and timestamp; renderer visibly marks its age.
                LOGGER.warning("Desk Display video unavailable (%s); retrying in 10 seconds", self.error_code)
            finally:
                if decoder_task is not None:
                    decoder_task.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await decoder_task
            if self.signature != signature:
                return
            if self.visible(signature):
                await self.coordinator.async_refresh()
            await asyncio.sleep(10)
