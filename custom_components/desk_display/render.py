"""Server-rendered frames. Never access HA state from a worker thread."""

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from .const import HEIGHT, WIDTH
from .models import validate_layout
from .material import material_tile, PALETTES


def render_image(layout, states, media=None):
    """Render a snapshot of state strings; clip each widget to its rectangle."""
    layout = validate_layout(layout)
    image = Image.new("RGB", (WIDTH, HEIGHT), layout["background"])
    for widget in layout["widgets"]:
        if layout.get("theme") in PALETTES or widget['kind'] in ('sensor','image','clock'):
            styled = widget
            if layout.get('theme') not in PALETTES:
                styled = {**widget, 'style':{**widget.get('style',{}),'surface':False,'radius':0}}
            tile = material_tile(styled, states, media, layout.get("theme") if layout.get('theme') in PALETTES else 'material_dark')
            image.paste(tile, (widget["x"], widget["y"]), tile)
            continue
        if widget["kind"] == "media":
            tile = Image.new("RGB", (widget["width"], widget["height"]), "#111111")
            data = (media or {}).get((widget["source"], widget["width"], widget["height"]))
            if data is not None and len(data) == widget["width"] * widget["height"] * 3:
                tile = Image.frombytes("RGB", tile.size, data)
            else:
                ImageDraw.Draw(tile).text((4, 4), "Stream offline", font=ImageFont.load_default(size=12), fill="#ffffff")
            image.paste(tile, (widget["x"], widget["y"]))
            continue
        tile = Image.new("RGBA", (widget["width"], widget["height"]))
        text = widget["text"]
        if widget["kind"] == "sensor":
            value = states.get(widget["entity_id"], "Nicht verfuegbar")
            text = f"{text}: {value}" if text else value
        draw = ImageDraw.Draw(tile)
        inset = 0
        if widget["kind"] in ("button", "switch"):
            value = states.get(widget["entity_id"], "Nicht verfuegbar")
            enabled = value not in ("Nicht verfuegbar", "unknown", "unavailable")
            background = "#2563eb" if enabled else "#374151"
            if widget["kind"] == "switch":
                background = "#087f5b" if value == "on" else "#374151"
                label = "Ein" if value == "on" else "Aus" if value == "off" else "?"
                text = f"{text or widget['entity_id']}: {label}"
            elif not text:
                text = widget["entity_id"]
            draw.rounded_rectangle((0, 0, widget["width"]-1, widget["height"]-1),
                                   radius=min(10, widget["height"]//3), fill=background)
            inset = 8
        draw.text((inset, inset), text[:160], font=ImageFont.load_default(size=widget["size"]),
                  fill=widget["color"], anchor="lt")
        image.paste(tile, (widget["x"], widget["y"]), tile)
    if 'overlay' in layout:
        image=Image.blend(image,Image.new('RGB',image.size,'black'),.6)
        modal=render_image(layout['overlay'],states,media)
        image.paste(modal.crop((16,12,464,304)),(16,12))
    return image


def rgb565(image):
    """RGB565 little endian, top-left first; no PNG/JPEG decoder on the ESP32."""
    output = bytearray(WIDTH * HEIGHT * 2)
    source = image.convert("RGB").tobytes()
    for index in range(WIDTH * HEIGHT):
        red, green, blue = source[index * 3:index * 3 + 3]
        pixel = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
        output[2 * index] = pixel & 0xFF
        output[2 * index + 1] = pixel >> 8
    return bytes(output)


def render_frame(layout, states, media=None):
    return rgb565(render_image(layout, states, media))


def render_preview(layout, states, media=None):
    buffer = BytesIO()
    render_image(layout, states, media).save(buffer, format="PNG")
    return buffer.getvalue()


def render_jpeg(layout, states, media, box=None):
    """Baseline JPEG, bounded by the firmware's shared 64 KiB upload buffer."""
    image = render_image(layout, states, media)
    if box is not None:
        image = image.crop(box)
    for quality in (80, 65, 50, 35, 20, 10):
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=quality, subsampling=2, progressive=False)
        result = buffer.getvalue()
        if len(result) <= 65536:
            return result
    raise ValueError('JPEG exceeds display buffer')
