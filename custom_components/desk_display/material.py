"""Material-inspired bounded tiles; all drawing happens on the HA host."""

from PIL import Image, ImageDraw, ImageFont
from .values import sensor_value
from .pictures import picture_tile

PALETTES = {
    "material_dark": {"surface": "#211f26", "muted": "#cac4d0", "track": "#49454f", "thumb": "#eaddff"},
    "material_light": {"surface": "#f3edf7", "muted": "#49454f", "track": "#cac4d0", "thumb": "#ffffff"},
}


def material_tile(widget, states, media, theme):
    palette = PALETTES[theme]
    width, height = widget["width"], widget["height"]
    style = widget.get("style", {})
    radius = min(style.get("radius", 16), width // 2, height // 2)
    tile = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(tile)
    kind = widget["kind"]
    if kind == 'image':
        picture = picture_tile(widget['image'], width, height, widget.get('fit','contain'))
        mask = Image.new('L',(width,height))
        ImageDraw.Draw(mask).rounded_rectangle((0,0,width-1,height-1),radius=radius,fill=255)
        from PIL import ImageChops
        picture=picture.copy()
        picture.putalpha(ImageChops.multiply(picture.getchannel('A'),mask))
        if style.get('surface',False):
            draw.rounded_rectangle((0,0,width-1,height-1),radius=radius,fill=style.get('background',palette['surface']))
            tile.alpha_composite(picture)
            return tile
        return picture
    value = states.get(widget["entity_id"], "Nicht verfuegbar")
    enabled = value not in ("Nicht verfuegbar", "unknown", "unavailable")
    background = style.get("background", "#6750a4" if kind == "button" and enabled else palette["surface"])
    surface = style.get("surface", kind != "text")
    if surface or kind == "media":
        draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=background)
    if kind == "media":
        data = (media or {}).get((widget["source"], width, height))
        if data is not None and len(data) == width * height * 3:
            picture = Image.frombytes("RGB", (width, height), data)
            mask = Image.new("L", (width, height))
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, width-1, height-1), radius=radius, fill=255)
            tile.paste(picture, (0, 0), mask)
        else:
            draw.text((8, 8), "Stream offline", font=ImageFont.load_default(size=12), fill=palette["muted"])
        return tile
    inset = min(12, max(0, (width - 1) // 4)) if surface else 0
    right = width - inset
    color = widget["color"]
    label = widget["text"] or (widget["entity_id"] if kind in ("button", "switch") else "")
    if kind == 'clock':
        label = states.get('__clock__',{}).get(widget.get('clock_format','time'),'--:--')
    align = style.get("align", "center" if kind == "button" else "left")

    def text_line(text, size, top, bottom, fill, start=None, end=None, justify=None):
        start = inset if start is None else start
        end = right if end is None else end
        justify = align if justify is None else justify
        font = ImageFont.load_default(size=size)
        # Ellipsize within this widget, keeping adjacent elements untouched.
        available = max(0, end - start)
        text = str(text)[:160]
        if draw.textlength(text, font=font) > available:
            while text and draw.textlength(text + "…", font=font) > available:
                text = text[:-1]
            text = text + "…" if text else ""
        box = font.getbbox(text)
        length = draw.textlength(text, font=font)
        x = start if justify == "left" else end-length if justify == "right" else (start+end-length)/2
        y = top + max(0, (bottom-top-(box[3]-box[1]))/2) - box[1]
        draw.text((x, y), text, font=font, fill=fill)

    if kind == "switch":
        track_width = min(44, width // 3)
        track_height = min(24, height - 8, track_width // 2 + 2)
        if track_height >= 8:
            x, y = width-inset-track_width, (height-track_height)//2
            draw.rounded_rectangle((x, y, x+track_width-1, y+track_height-1), radius=track_height//2,
                                   fill="#6750a4" if value == "on" else palette["track"])
            diameter = track_height-6
            left = x+track_width-diameter-3 if value == "on" else x+3
            draw.ellipse((left,y+3,left+diameter-1,y+3+diameter-1), fill=palette["thumb"] if enabled else palette["muted"])
            right = x-8
        label += " · ?" if not enabled else ""
    if kind == "sensor":
        value = sensor_value(widget,states)
        if label and height >= 62:
            text_line(label, min(14, widget["size"]), 6, 26, palette["muted"],justify='left')
            text_line(value, widget["size"], 26, height-6, color,justify='right')
        elif label:
            split = inset+(right-inset)*.45
            text_line(label,min(16,widget["size"]),0,height,color,end=split-4,justify='left')
            text_line(value,widget["size"],0,height,color,start=split+4,justify='right')
        else:
            text_line(value,widget["size"],0,height,color,justify='right')
    else:
        text_line(label, widget["size"], 0, height, color)
    return tile
