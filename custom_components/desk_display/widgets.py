"""Bounded display widgets, rendered entirely on the Home Assistant host."""
import math
from PIL import Image, ImageDraw, ImageFont

KINDS=('progress','gauge','chip')


def number(value,default=None):
    try:
        result=float(value)
        return result if math.isfinite(result) else default
    except (TypeError,ValueError):return default


def validate_config(widget):
    config=widget.get('config',{})
    if not isinstance(config,dict):raise ValueError('Ungueltige Elementkonfiguration')
    kind=widget['kind']
    allowed={'progress':{'min','max','unit'},'gauge':{'min','max','unit'},'chip':{'active','on_text','off_text'}}.get(kind,set())
    if set(config)-allowed:raise ValueError('Unbekannte Elementeinstellung')
    if kind in ('progress','gauge'):
        for key,default in [('min',0),('max',100)]:
            if number(config.get(key,default)) is None:raise ValueError('Endliche Bereichsgrenzen angeben')
        if float(config.get('min',0))>=float(config.get('max',100)):raise ValueError('Maximum muss groesser als Minimum sein')
    for key in ('unit','active','on_text','off_text'):
        if key in config and (not isinstance(config[key],str) or len(config[key])>40 or any(ord(c)<32 for c in config[key])):raise ValueError('Text: maximal 40 Zeichen')


def tile(widget,states,theme):
    width,height=widget['width'],widget['height'];color=widget['color'];config=widget.get('config',{})
    image=Image.new('RGBA',(width,height));draw=ImageDraw.Draw(image)
    font=ImageFont.load_default(size=min(widget['size'],24));small=ImageFont.load_default(size=12)
    raw=states.get('__raw__',{}).get(widget['entity_id'],('unavailable',''))
    value=number(raw[0]);kind=widget['kind'];muted='#49454f' if theme=='material_light' else '#cac4d0'
    if kind=='chip':
        active=raw[0]==config.get('active','on');text=config.get('on_text','Aktiv') if active else config.get('off_text','Inaktiv')
        if raw[0] in ('unknown','unavailable'):text='Nicht verfügbar'
        draw.rounded_rectangle((0,0,width-1,height-1),radius=min(height//2,20),fill='#6750a4' if active else '#49454f')
        label=(widget['text']+' · '+text).strip(' ·')
        draw.text((8,max(0,(height-18)//2)),label[:45],fill=color,font=font)
        if widget.get('image'):
            from .pictures import picture_tile
            icon=picture_tile(widget['image'],min(24,height),min(24,height),'contain')
            image.alpha_composite(icon,(max(0,width-icon.width-6),max(0,(height-icon.height)//2)))
        return image
    minimum=float(config.get('min',0));maximum=float(config.get('max',100))
    fraction=0 if value is None else max(0,min(1,(value-minimum)/(maximum-minimum)))
    label='—' if value is None else f'{value:g} {config.get("unit",raw[1])}'.strip()
    if kind=='progress':
        draw.text((4,2),widget['text'][:40],font=small,fill=muted)
        draw.text((4,20),label,font=font,fill=color)
        top=max(0,height-12);draw.rounded_rectangle((0,top,width-1,height-1),radius=5,fill='#49454f')
        if fraction:draw.rounded_rectangle((0,top,max(0,int((width-1)*fraction)),height-1),radius=5,fill=color)
    elif kind=='gauge':
        diameter=max(1,min(width,height)-6);left=(width-diameter)//2;top=(height-diameter)//2;box=(left,top,left+diameter-1,top+diameter-1)
        draw.arc(box,0,360,fill='#49454f',width=max(1,min(8,diameter//8)))
        if fraction:draw.arc(box,-90,-90+360*fraction,fill=color,width=max(1,min(8,diameter//8)))
        length=draw.textlength(label,font=font);draw.text(((width-length)/2,(height-18)/2),label,font=font,fill=color)
        draw.text((4,max(0,height-15)),widget['text'][:24],font=small,fill=muted)
    return image
