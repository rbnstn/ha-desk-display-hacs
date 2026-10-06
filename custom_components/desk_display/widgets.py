"""Bounded display widgets, rendered entirely on the Home Assistant host."""
import math
from PIL import Image, ImageDraw, ImageFont

KINDS=('progress','gauge','chip','chart','energy','slider','player')


def number(value,default=None):
    try:
        result=float(value)
        return result if math.isfinite(result) else default
    except (TypeError,ValueError):return default


def validate_config(widget):
    config=widget.get('config',{})
    if not isinstance(config,dict):raise ValueError('Ungueltige Elementkonfiguration')
    kind=widget['kind']
    if kind in ('cost','weather','countdown'):
        from .data_widgets import validate
        validate(widget);return
    allowed={'progress':{'min','max','unit'},'gauge':{'min','max','unit'},'chip':{'active','on_text','off_text'},'chart':{'minutes','min','max','threshold','factor','unit'},'sensor':{'detail_enabled','detail_minutes'},'button':{'hold_entity_id','confirm'},'slider':set(),'player':set(),'energy':{'solar','house','battery','grid','factor','grid_invert','battery_invert','battery_soc','wallbox','power_unit'}}.get(kind,set())
    if set(config)-allowed:raise ValueError('Unbekannte Elementeinstellung')
    if kind=='sensor':
        if type(config.get('detail_enabled',False)) is not bool:raise ValueError('Ungültige Detailansicht')
        if type(config.get('detail_minutes',60)) is not int or not 15<=config.get('detail_minutes',60)<=1440:raise ValueError('Detailverlauf: 15 bis 1440 Minuten')
    if kind in ('progress','gauge'):
        for key,default in [('min',0),('max',100)]:
            if number(config.get(key,default)) is None:raise ValueError('Endliche Bereichsgrenzen angeben')
        if float(config.get('min',0))>=float(config.get('max',100)):raise ValueError('Maximum muss groesser als Minimum sein')
    if kind=='button':
        import re
        from .actions import BUTTON_SERVICES
        entity=config.get('hold_entity_id','')
        if not isinstance(entity,str) or (entity and (not re.fullmatch(r'[a-z_][a-z0-9_]*\.[a-z0-9_]+',entity) or entity.split('.')[0] not in BUTTON_SERVICES)):raise ValueError('Ungueltige Aktion fuer langes Druecken')
        if type(config.get('confirm',False)) is not bool:raise ValueError('Ungueltige Bestaetigung')
    if kind=='chart':
        if type(config.get('minutes',60)) is not int or not 15<=config.get('minutes',60)<=1440:raise ValueError('Verlauf: 15 bis 1440 Minuten')
        for key in ('min','max','threshold','factor'):
            if key in config and number(config[key]) is None:raise ValueError('Endliche Diagrammwerte angeben')
        if 'min' in config and 'max' in config and float(config['min'])>=float(config['max']):raise ValueError('Diagrammmaximum muss groesser sein')
    if kind=='energy':
        import re
        for key in ('solar','house','battery','grid'):
            if not isinstance(config.get(key,''),str) or not re.fullmatch(r'[a-z_][a-z0-9_]*\.[a-z0-9_]+',config.get(key,'')):raise ValueError('Energiefluss: vier HA-Entitaeten auswaehlen')
        for key in ('battery_soc','wallbox'):
            entity=config.get(key,'')
            if not isinstance(entity,str) or (entity and not re.fullmatch(r'sensor\.[a-z0-9_]+',entity)):raise ValueError('Batteriestand und Wallbox: Sensor auswählen oder leer lassen')
        if config.get('power_unit','auto') not in ('auto','factor'):raise ValueError('Ungültige Leistungseinheit')
        for key in ('grid_invert','battery_invert'):
            if type(config.get(key,False)) is not bool:raise ValueError('Ungueltige Flussrichtung')
        if number(config.get('factor',1)) is None:raise ValueError('Ungueltiger Energiefaktor')
    for key in ('unit','active','on_text','off_text'):
        if key in config and (not isinstance(config[key],str) or len(config[key])>40 or any(ord(c)<32 for c in config[key])):raise ValueError('Text: maximal 40 Zeichen')


def tile(widget,states,theme):
    width,height=widget['width'],widget['height'];color=widget['color'];config=widget.get('config',{})
    image=Image.new('RGBA',(width,height));draw=ImageDraw.Draw(image)
    font=ImageFont.load_default(size=min(widget['size'],24));small=ImageFont.load_default(size=12)
    raw=states.get('__raw__',{}).get(widget['entity_id'],('unavailable',''))
    value=number(raw[0]);kind=widget['kind'];muted='#49454f' if theme=='material_light' else '#cac4d0'
    style=widget.get('style',{});surface=style.get('background','#f3edf7' if theme=='material_light' else '#211f26')
    radius=min(style.get('radius',12),height//2,width//2)
    if style.get('surface',False):draw.rounded_rectangle((0,0,width-1,height-1),radius=radius,fill=surface)
    if kind in ('slider','player'):
        attributes=states.get('__attributes__',{}).get(widget['entity_id'],{})
        draw.rounded_rectangle((0,0,width-1,height-1),radius=radius,fill=surface)
        if kind=='player':
            cover=states.get('__covers__',{}).get(widget['entity_id'])
            left=4
            if cover:
                from .pictures import picture_tile
                diameter=min(48,max(1,height-56),width//3);image.alpha_composite(picture_tile(cover,diameter,diameter,'cover'),(4,4));left=diameter+8
            draw.text((left,4),str(attributes.get('media_title',widget['text']))[:40],font=small,fill=color)
            draw.text((left,22),str(attributes.get('media_artist',''))[:40],font=small,fill=muted)
            for i,label in enumerate(('<<','Pause' if raw[0]=='playing' else 'Play','>>')):draw.text((i*width//3+4,max(0,height-24)),label,font=small,fill=color)
            fraction=number(attributes.get('volume_level'),0);top=max(0,height-46)
        else:
            domain=widget['entity_id'].split('.')[0]
            if domain=='light':fraction=number(attributes.get('brightness'),0)/255
            elif domain=='media_player':fraction=number(attributes.get('volume_level'),0)
            else:
                minimum=number(attributes.get('min'),0);maximum=number(attributes.get('max'),100);fraction=0 if value is None else (value-minimum)/max(.001,maximum-minimum)
            draw.text((6,4),widget['text'][:30],font=small,fill=color);draw.text((6,22),f'{max(0,min(1,fraction))*100:.0f} %',font=font,fill=color);top=max(0,height-16)
        fraction=max(0,min(1,fraction));right=max(4,width-8);draw.line((6,top,right,top),fill=muted,width=4);draw.line((6,top,6+fraction*(right-6),top),fill=color,width=4);x=6+fraction*(right-6);draw.ellipse((x-5,top-5,x+5,top+5),fill=color)
        feedback=states.get('__feedback__',{}).get(widget['entity_id'])
        if feedback:draw.text((6,max(0,height-30)),feedback,font=small,fill='#ffd166')
        return image
    if kind=='chart':
        points,start,end=states.get('__history__',{}).get((widget['entity_id'],config.get('minutes',60)),states.get('__history__',{}).get(widget['entity_id'],([],0,1)))
        factor=float(config.get('factor',1));values=[v*factor for _,v in points if v is not None]
        draw.text((4,2),widget['text'][:32],font=small,fill=color)
        if not values:
            draw.text((4,24),'Kein Verlauf verfügbar',font=small,fill=muted);return image
        low=float(config.get('min',min(values)));high=float(config.get('max',max(values)))
        if high<=low:high=low+1
        top=22;bottom=max(top+1,height-18);right=max(1,width-6)
        draw.line((4,bottom,right,bottom),fill=muted)
        def position(timestamp,value):
            return (4+max(0,min(1,(timestamp-start)/max(1,end-start)))*(right-4),bottom-max(0,min(1,(value-low)/(high-low)))*(bottom-top))
        previous=None
        for timestamp,value in points:
            if value is None:previous=None;continue
            current=position(timestamp,value*factor)
            if previous:draw.line((previous,current),fill=color,width=2)
            previous=current
        if 'threshold' in config:
            y=position(start,float(config['threshold']))[1];draw.line((4,y,right,y),fill='#ffb74d',width=1)
        draw.text((4,max(0,height-15)),f'{values[-1]:g} {config.get("unit",raw[1])}',font=small,fill=color)
        return image
    if kind=='energy':
        from .energy import tile as energy_tile
        return energy_tile(widget,states,theme)
    if kind=='chip':
        active=raw[0]==config.get('active','on');text=config.get('on_text','Aktiv') if active else config.get('off_text','Inaktiv')
        if raw[0] in ('unknown','unavailable'):text='Nicht verfügbar'
        draw.rounded_rectangle((0,0,width-1,height-1),radius=min(height//2,20),fill=style.get('background','#eaddff' if active and theme=='material_light' else '#6750a4' if active else '#cac4d0' if theme=='material_light' else '#49454f'))
        label=(widget['text']+' · '+text).strip(' ·')
        draw.text((8,max(0,(height-18)//2)),label[:45],fill=color,font=font)
        if widget.get('image'):
            from .pictures import picture_tile
            icon=picture_tile(widget['image'],min(24,height),min(24,height),'contain')
            mask=icon.getchannel('A');icon=Image.new('RGBA',icon.size,color);icon.putalpha(mask)
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

