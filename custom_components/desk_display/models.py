"""Validate the bounded layout and device contract; independent of HA."""

import copy
import ipaddress
import re

from .const import DEFAULT_LAYOUT, HEIGHT, PROTOCOL, WIDTH
from .actions import BUTTON_SERVICES, SWITCH_SERVICES

COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
ENTITY = re.compile(r"[a-z_][a-z0-9_]*\.[a-z0-9_]+\Z")
HOSTNAME = re.compile(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?\Z")


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
    if not isinstance(layout, dict) or set(layout) != {"background", "widgets"}:
        raise ValueError("Ungueltiges Layout")
    if not isinstance(layout["background"], str) or not COLOR.fullmatch(layout["background"]):
        raise ValueError("Ungueltige Hintergrundfarbe")
    widgets = layout["widgets"]
    if not isinstance(widgets, list) or len(widgets) > 8:
        raise ValueError("Maximal acht Elemente")
    result = {"background": layout["background"], "widgets": []}
    keys = {"kind", "text", "entity_id", "x", "y", "width", "height", "size", "color"}
    for widget in widgets:
        if not isinstance(widget, dict) or set(widget) != keys:
            raise ValueError("Ungueltiges Element")
        if widget["kind"] not in ("text", "sensor", "button", "switch"):
            raise ValueError("Unbekannter Elementtyp")
        if not isinstance(widget["text"], str) or len(widget["text"]) > 80 or "\n" in widget["text"]:
            raise ValueError("Beschriftung: maximal 80 Zeichen, eine Zeile")
        if not isinstance(widget["entity_id"], str):
            raise ValueError("Ungueltige Entitaet")
        if widget["kind"] != "text" and not ENTITY.fullmatch(widget["entity_id"]):
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
        if normalized["kind"] == "text":
            normalized["entity_id"] = ""
        result["widgets"].append(normalized)
    return result


def get_layout(options):
    return validate_layout(copy.deepcopy(options.get("layout", DEFAULT_LAYOUT)))
