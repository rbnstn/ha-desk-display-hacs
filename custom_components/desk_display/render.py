"""Server-rendered frames. Never access HA state from a worker thread."""

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from .const import HEIGHT, WIDTH
from .models import validate_layout


def render_image(layout, states):
    """Render a snapshot of state strings; clip each widget to its rectangle."""
    layout = validate_layout(layout)
    image = Image.new("RGB", (WIDTH, HEIGHT), layout["background"])
    for widget in layout["widgets"]:
        tile = Image.new("RGBA", (widget["width"], widget["height"]))
        text = widget["text"]
        if widget["kind"] == "sensor":
            value = states.get(widget["entity_id"], "Nicht verfuegbar")
            text = f"{text}: {value}" if text else value
        draw = ImageDraw.Draw(tile)
        draw.text((0, 0), text[:160], font=ImageFont.load_default(size=widget["size"]),
                  fill=widget["color"], anchor="lt")
        image.paste(tile, (widget["x"], widget["y"]), tile)
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


def render_frame(layout, states):
    return rgb565(render_image(layout, states))


def render_preview(layout, states):
    buffer = BytesIO()
    render_image(layout, states).save(buffer, format="PNG")
    return buffer.getvalue()
