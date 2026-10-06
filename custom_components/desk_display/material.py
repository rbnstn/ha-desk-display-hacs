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
    if kind == 'line':
        thickness=min(widget.get('line_width',2),height if width>=height else width)
        if width>=height:
            y=(height-thickness)//2;draw.rectangle((0,y,width-1,y+thickness-1),fill=widget['color'])
        else:
            x=(width-thickness)//2;draw.rectangle((x,0,x+thickness-1,height-1),fill=widget['color'])
        return tile
    if kind == 'icon':
        if widget.get('image'):
            picture=picture_tile(widget['image'],width,height,'contain')
            tile=Image.new('RGBA',(width,height),widget['color']);tile.putalpha(picture.getchannel('A'))
        else:
            draw.text((2,2),'Icon',font=ImageFont.load_default(size=12),fill=widget['color'])
        return tile
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
        from .enhancements import font_for
        font = font_for(size,style)
        available = max(0, end - start)
        lines=str(text)[:240].split('\n')[:6]
        heights=[font.getbbox(line or 'Ag')[3]-font.getbbox(line or 'Ag')[1] for line in lines]
        total=sum(heights)+max(0,len(lines)-1)*4
        valign=style.get('valign','middle')
        y=top if valign=='top' else bottom-total if valign=='bottom' else top+(bottom-top-total)/2
        for line,line_height in zip(lines,heights):
            if draw.textlength(line,font=font)>available:
                while line and draw.textlength(line+'…',font=font)>available:line=line[:-1]
                line=line+'…' if line else ''
            length=draw.textlength(line,font=font)
            x=start if justify=='left' else end-length if justify=='right' else (start+end-length)/2
            draw.text((x,y-font.getbbox(line or 'Ag')[1]),line,font=font,fill=fill)
            y+=line_height+4

    def value_line(value,top,bottom,start=None,end=None):
        start=inset if start is None else start;end=right if end is None else end
        if 'unit_size' not in style:
            text_line(value,widget['size'],top,bottom,color,start=start,end=end,justify=style.get('align','right'));return
        parts=str(value).rsplit(' ',1)
        if len(parts)!=2:
            text_line(value,widget['size'],top,bottom,color,start=start,end=end,justify=style.get('align','right'));return
        from .enhancements import font_for
        value,unit=parts;main=font_for(widget['size'],style);small=font_for(style['unit_size'],style)
        length=main.getlength(value)+6+small.getlength(unit);justify=style.get('align','right')
        x=start if justify=='left' else end-length if justify=='right' else (start+end-length)/2
        box=main.getbbox(value);total=box[3]-box[1];valign=style.get('valign','middle')
        y=top if valign=='top' else bottom-total if valign=='bottom' else top+(bottom-top-total)/2
        draw.text((x,y-box[1]),value,font=main,fill=color)
        ubox=small.getbbox(unit);draw.text((x+main.getlength(value)+6,y+total-(ubox[3]-ubox[1])-ubox[1]),unit,font=small,fill=style.get('unit_color',color))

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
            text_line(label, min(14, widget["size"]), 6, 26, palette["muted"],justify=style.get('align','left'))
            value_line(value,26,height-6)
        elif label:
            split = inset+(right-inset)*.45
            text_line(label,min(16,widget["size"]),0,height,color,end=split-4,justify=style.get('align','left'))
            value_line(value,0,height,start=split+4)
        else:
            value_line(value,0,height)
    else:
        feedback=states.get("__feedback__",{}).get(widget["entity_id"])
        text_line(feedback or label, min(widget["size"],16) if feedback else widget["size"], 0, height, "#ffd166" if feedback else color)
    options=widget.get('availability',{})
    age=states.get('__age__',{}).get(widget['entity_id'])
    if age is not None and (options.get('show_age') or (options.get('stale_after',0) and age>=options['stale_after'])):
        stale=bool(options.get('stale_after',0) and age>=options['stale_after'])
        badge=('Veraltet · ' if stale else '')+f'{int(age)//60} min' if age>=60 else ('Veraltet · ' if stale else '')+f'{int(age)} s'
        draw.rectangle((0,max(0,height-16),width-1,height-1),fill='#663c00' if stale else background)
        draw.text((3,max(0,height-15)),badge,font=ImageFont.load_default(size=10),fill='#ffffff')
    return tile
