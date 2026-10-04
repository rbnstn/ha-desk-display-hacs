"""Validate the bounded layout and device contract; independent of HA."""

import copy
import ipaddress
import re
from urllib.parse import urlsplit

from .const import DEFAULT_LAYOUT, HEIGHT, PROTOCOL, WIDTH
from .actions import BUTTON_SERVICES, SWITCH_SERVICES

COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
ENTITY = re.compile(r"[a-z_][a-z0-9_]*\.[a-z0-9_]+\Z")
HOSTNAME = re.compile(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?\Z")


def validate_media_source(source):
    if not isinstance(source, str) or not source or len(source) > 2048 or any(ord(c) < 32 for c in source):
        raise ValueError("Bitte eine Kamera, HA-Medienquelle oder Video-URL angeben")
    if ENTITY.fullmatch(source) and source.startswith("camera."):
        return source
    url = urlsplit(source)
    if url.scheme not in ("media-source", "http", "https", "rtsp", "rtsps", "rtmp", "rtmps") or not url.netloc:
        raise ValueError("Unterstuetzt: camera.*, media-source://, HTTP(S), RTSP(S), RTMP(S)")
    return source


def validate_host(value):
    """Accept IPv4 or a hostname, never URL paths, ports or credentials."""
    host = value.strip()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if not HOSTNAME.fullmatch(host) or ".." in host:
            raise ValueError("Bitte nur IPv4-Adresse oder Hostnamen eingeben")
    else:
        if address.version != 4:
            raise ValueError("Der MVP unterstuetzt IPv4")
    return host.lower()


def validate_info(info):
    """Reject other devices and incompatible versions before transferring frames."""
    if not isinstance(info, dict) or any(info.get(k) != v for k, v in {
        "product": "desk_display", "protocol": PROTOCOL,
        "model": "E32R35T", "width": WIDTH, "height": HEIGHT,
    }.items()):
        raise ValueError("Unpassende Display-Firmware oder Protokollversion")
    if not isinstance(info.get("id"), str) or not re.fullmatch(r"[0-9a-f]{12}", info["id"]):
        raise ValueError("Ungueltige Geraete-ID")
    return info


def validate_layout(layout):
    """Normalize untrusted editor input, with strict bounds for rendering."""
    if not isinstance(layout, dict) or not {"background", "widgets"} <= set(layout) <= {"background", "widgets", "debug", "overlay", "theme"}:
        raise ValueError("Ungueltiges Layout")
    if not isinstance(layout["background"], str) or not COLOR.fullmatch(layout["background"]):
        raise ValueError("Ungueltige Hintergrundfarbe")
    widgets = layout["widgets"]
    if not isinstance(widgets, list) or len(widgets) > 8:
        raise ValueError("Maximal acht Elemente")
    if type(layout.get("debug", False)) is not bool:
        raise ValueError("Debug-Anzeige muss ein- oder ausgeschaltet sein")
    result = {"background": layout["background"], "widgets": [], "debug": layout.get("debug", False)}
    if "theme" in layout:
        if layout["theme"] not in ("classic", "material_dark", "material_light"):
            raise ValueError("Unbekanntes Display-Design")
        result["theme"] = layout["theme"]
    keys = {"kind", "text", "entity_id", "x", "y", "width", "height", "size", "color"}
    for widget in widgets:
        if not isinstance(widget, dict) or not keys <= set(widget) <= keys | {"source", "fps", "style"}:
            raise ValueError("Ungueltiges Element")
        if widget["kind"] not in ("text", "sensor", "button", "switch", "media"):
            raise ValueError("Unbekannter Elementtyp")
        if not isinstance(widget["text"], str) or len(widget["text"]) > 80 or "\n" in widget["text"]:
            raise ValueError("Beschriftung: maximal 80 Zeichen, eine Zeile")
        if not isinstance(widget["entity_id"], str):
            raise ValueError("Ungueltige Entitaet")
        if widget["kind"] not in ("text", "media") and not ENTITY.fullmatch(widget["entity_id"]):
            raise ValueError("Bitte eine HA-Entitaet auswaehlen")
        domain = widget["entity_id"].split(".", 1)[0]
        if widget["kind"] == "button" and domain not in BUTTON_SERVICES:
            raise ValueError("Button: button, input_button oder script auswaehlen")
        if widget["kind"] == "switch" and domain not in SWITCH_SERVICES:
            raise ValueError("Switch: switch oder input_boolean auswaehlen")
        for key, minimum, maximum in (
            ("x", 0, WIDTH - 1), ("y", 0, HEIGHT - 1),
            ("width", 1, WIDTH), ("height", 1, HEIGHT), ("size", 12, 64),
        ):
            if type(widget[key]) is not int or not minimum <= widget[key] <= maximum:
                raise ValueError(f"Ungueltiger Wert fuer {key}")
        if widget["x"] + widget["width"] > WIDTH or widget["y"] + widget["height"] > HEIGHT:
            raise ValueError("Das Element liegt ausserhalb des Displays")
        if not isinstance(widget["color"], str) or not COLOR.fullmatch(widget["color"]):
            raise ValueError("Ungueltige Textfarbe")
        normalized = dict(widget)
        if "style" in widget:
            style = widget["style"]
            if not isinstance(style, dict) or not set(style) <= {"surface", "background", "radius", "align"}:
                raise ValueError("Ungueltiger Elementstil")
            if "surface" in style and type(style["surface"]) is not bool:
                raise ValueError("Kartenflaeche muss ein- oder ausgeschaltet sein")
            if "radius" in style and (type(style["radius"]) is not int or not 0 <= style["radius"] <= 32):
                raise ValueError("Eckenradius: 0 bis 32 Pixel")
            if "align" in style and style["align"] not in ("left", "center", "right"):
                raise ValueError("Ungueltige Textausrichtung")
            if "background" in style and (not isinstance(style["background"], str) or not COLOR.fullmatch(style["background"])):
                raise ValueError("Ungueltige Kartenfarbe")
            normalized["style"] = dict(style)
        if normalized["kind"] == "media":
            normalized["source"] = validate_media_source(widget.get("source", ""))
            fps = widget.get('fps', 1)
            if type(fps) is not int or not 1 <= fps <= 20:
                raise ValueError("Zielbildrate: 1 bis 20 FPS")
            # Migrate older saved rates while keeping their input validation.
            normalized['fps'] = 1
        else:
            normalized.pop("source", None)
            normalized.pop("fps", None)
        if normalized["kind"] in ("text", "media"):
            normalized["entity_id"] = ""
        result["widgets"].append(normalized)
    if sum(w["kind"] == "media" for w in result["widgets"]) > 1:
        raise ValueError("Stream-MVP: eine Videoquelle pro Display")
    if 'overlay' in layout:
        if not isinstance(layout['overlay'],dict) or 'overlay' in layout['overlay']:
            raise ValueError('Nur eine Overlay-Ebene erlaubt')
        result['overlay']=validate_layout(layout['overlay'])
    return result


def get_layout(options):
    return validate_layout(copy.deepcopy(options.get("layout", DEFAULT_LAYOUT)))
