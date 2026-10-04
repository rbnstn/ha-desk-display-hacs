"""Validate the bounded layout and device contract; independent of HA."""

import copy
import ipaddress
import re
import math
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


def validate_layout(layout, nested=False):
    """Normalize untrusted editor input, with strict bounds for rendering."""
    if not isinstance(layout, dict) or not {"background", "widgets"} <= set(layout) <= {"background", "widgets", "debug", "overlay", "theme", "pages", "page_name", "rotation", "device"}:
        raise ValueError("Ungueltiges Layout")
    if not isinstance(layout["background"], str) or not COLOR.fullmatch(layout["background"]):
        raise ValueError("Ungueltige Hintergrundfarbe")
    widgets = layout["widgets"]
    if not isinstance(widgets, list) or len(widgets) > 14 or sum(isinstance(w,dict) and w.get('kind')!='navigation' for w in widgets)>10:
        raise ValueError("Maximal zehn Elemente")
    if type(layout.get("debug", False)) is not bool:
        raise ValueError("Debug-Anzeige muss ein- oder ausgeschaltet sein")
    result = {"background": layout["background"], "widgets": [], "debug": layout.get("debug", False)}
    if 'device' in layout:
        from .device_settings import validate_settings
        if nested:raise ValueError('Geraeteeinstellungen nur auf der Hauptseite')
        result['device']=validate_settings(layout['device'])
    if 'page_name' in layout:
        if not isinstance(layout['page_name'],str) or not 1<=len(layout['page_name'])<=20 or any(ord(c)<32 for c in layout['page_name']):raise ValueError('Seitenname: 1 bis 20 Zeichen')
        result['page_name']=layout['page_name']
    if 'rotation' in layout:
        value=layout['rotation']
        if type(value) is not int or (value!=0 and not 15<=value<=300):raise ValueError('Seitenwechsel: 0 oder 15 bis 300 Sekunden')
        result['rotation']=value
    if 'pages' in layout:
        if nested or not isinstance(layout['pages'],list) or len(layout['pages'])>3:raise ValueError('Maximal vier Seiten ohne Verschachtelung')
        result['pages']=[validate_layout(page,True) for page in layout['pages']]
        if any('overlay' in page or 'rotation' in page for page in result['pages']):raise ValueError('Seiten enthalten kein Overlay oder Rotation')
    if "theme" in layout:
        if layout["theme"] not in ("classic", "material_dark", "material_light"):
            raise ValueError("Unbekanntes Display-Design")
        result["theme"] = layout["theme"]
    keys = {"kind", "text", "entity_id", "x", "y", "width", "height", "size", "color"}
    for widget in widgets:
        if not isinstance(widget, dict) or not keys <= set(widget) <= keys | {"source", "fps", "style", "value", "clock_format", "image", "fit", "group", "rules", "visible_when", "target", "icon", "line_width", "config", "locked", "hidden"}:
            raise ValueError("Ungueltiges Element")
        if widget["kind"] not in ("text", "sensor", "button", "switch", "media", "image", "clock", "navigation", "icon", "line", "progress", "gauge", "chip", "chart", "energy"):
            raise ValueError("Unbekannter Elementtyp")
        if not isinstance(widget["text"], str) or len(widget["text"]) > 80 or "\n" in widget["text"]:
            raise ValueError("Beschriftung: maximal 80 Zeichen, eine Zeile")
        if not isinstance(widget["entity_id"], str):
            raise ValueError("Ungueltige Entitaet")
        if widget["kind"] not in ("text", "media", "image", "clock", "navigation", "icon", "line", "energy") and not ENTITY.fullmatch(widget["entity_id"]):
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
        from .widgets import validate_config
        validate_config(widget)
        for flag in ("locked","hidden"):
            if type(widget.get(flag,False)) is not bool:raise ValueError("Ungueltiger Elementstatus")
        normalized = dict(widget)
        if widget['kind']=='navigation':
            if type(widget.get('target')) is not int or not 0<=widget['target']<=3:raise ValueError('Ungueltige Zielseite')
        elif 'target' in widget:raise ValueError('Zielseite nur fuer Navigation')
        from .rules import validate_rules
        validate_rules(widget)
        if 'group' in widget and (not isinstance(widget['group'],str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',widget['group'])):
            raise ValueError('Ungueltige Elementgruppe')
        if 'value' in widget:
            value = widget['value']
            if widget['kind'] != 'sensor' or not isinstance(value, dict) or not set(value) <= {'factor','unit','invert','decimals','fallback_entity_id','fallback_mode'}:
                raise ValueError('Ungueltige Werteinstellungen')
            factor = value.get('factor', 1)
            if type(factor) not in (int,float) or abs(factor)>1e9 or not math.isfinite(factor):
                raise ValueError('Ungueltiger Umrechnungsfaktor')
            if type(value.get('invert',False)) is not bool:
                raise ValueError('Ungueltiger Vorzeichenwechsel')
            if 'decimals' in value and (type(value['decimals']) is not int or not 0<=value['decimals']<=6):
                raise ValueError('Nachkommastellen: 0 bis 6')
            unit = value.get('unit','')
            if not isinstance(unit,str) or len(unit)>16 or any(ord(c)<32 for c in unit):
                raise ValueError('Einheit: maximal 16 Zeichen')
            fallback = value.get('fallback_entity_id','')
            if not isinstance(fallback,str) or (fallback and not ENTITY.fullmatch(fallback)) or value.get('fallback_mode','both') not in ('missing','zero','both'):
                raise ValueError('Ungueltiger Ersatzwert')
            normalized['value'] = dict(value)
        if widget['kind']=='clock':
            if widget.get('clock_format','time') not in ('time','date','datetime'):
                raise ValueError('Ungueltiges Uhrzeitformat')
            normalized['clock_format']=widget.get('clock_format','time')
        else:
            normalized.pop('clock_format',None)
        if widget['kind'] in ('image','icon'):
            from .pictures import image_bytes
            if widget['kind']=='image' or widget.get('image'):image_bytes(widget.get('image',''))
            if widget.get('fit','contain') not in ('contain','cover'):
                raise ValueError('Ungueltige Bildanpassung')
            normalized['fit']=widget.get('fit','contain')
        else:
            normalized.pop('image',None)
            normalized.pop('fit',None)
        if widget['kind']=='icon':
            name=widget.get('icon','mdi:home')
            if not isinstance(name,str) or len(name)>100 or not re.fullmatch(r'[a-z0-9_-]+:[a-z0-9_-]+',name):raise ValueError('Ungueltiges HA-Icon')
            normalized['icon']=name
        else:normalized.pop('icon',None)
        if widget['kind']=='line':
            thickness=widget.get('line_width',2)
            if type(thickness) is not int or not 1<=thickness<=8:raise ValueError('Linienstaerke: 1 bis 8 Pixel')
            normalized['line_width']=thickness
        else:normalized.pop('line_width',None)
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
        if normalized["kind"] in ("text", "media", "image", "clock", "icon", "line", "energy"):
            normalized["entity_id"] = ""
        result["widgets"].append(normalized)
    if sum(w["kind"] == "media" for w in result["widgets"]) > 1:
        raise ValueError("Stream-MVP: eine Videoquelle pro Display")
    if 'overlay' in layout:
        if not isinstance(layout['overlay'],dict) or 'overlay' in layout['overlay']:
            raise ValueError('Nur eine Overlay-Ebene erlaubt')
        result['overlay']=validate_layout(layout['overlay'])
    if not nested:
        from .pages import all_widgets
        if sum(len(w.get('image','')) for w in all_widgets(result))>1100000:
            raise ValueError('Bilder im gesamten Layout: maximal ca. 800 KiB; kleinere Bilder verwenden')
    return result


def get_layout(options):
    return validate_layout(copy.deepcopy(options.get("layout", DEFAULT_LAYOUT)))
