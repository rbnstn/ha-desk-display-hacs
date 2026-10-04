"""Display-only costs, weather and countdowns; never change HA measurements."""
import math
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from .widgets import number

KINDS=('cost','weather','countdown')
CONDITIONS={'sunny':'Sonnig','clear-night':'Klare Nacht','partlycloudy':'Teils bewölkt','cloudy':'Bewölkt','rainy':'Regen','pouring':'Starker Regen','snowy':'Schnee','snowy-rainy':'Schneeregen','fog':'Nebel','windy':'Windig','windy-variant':'Windig','lightning':'Gewitter','lightning-rainy':'Gewitter','hail':'Hagel','exceptional':'Unwetter'}

def validate(widget):
    config=widget.get('config',{});kind=widget['kind']
    allowed={'cost':{'price','tariff_entity_id','currency','mode','absolute'},'weather':{'forecast'},'countdown':{'mode','total'}}[kind]
    if not isinstance(config,dict) or set(config)-allowed:raise ValueError('Unbekannte Datenkonfiguration')
    if kind=='cost':
        if number(config.get('price',.3)) is None or not 0<=float(config.get('price',.3))<=1000000:raise ValueError('Preis pro kWh: endliche positive Zahl')
        if config.get('mode','energy') not in ('energy','power'):raise ValueError('Kosten: Energie oder Leistungsrate wählen')
        if type(config.get('absolute',False)) is not bool:raise ValueError('Ungültiges Vorzeichen')
        import re
        entity=config.get('tariff_entity_id','')
        if not isinstance(entity,str) or (entity and not re.fullmatch(r'[a-z_][a-z0-9_]*\.[a-z0-9_]+',entity)):raise ValueError('Ungültige Preisentität')
        currency=config.get('currency','EUR')
        if not isinstance(currency,str) or not 1<=len(currency)<=8 or any(ord(c)<32 for c in currency):raise ValueError('Währung: 1 bis 8 Zeichen')
    if kind=='weather' and config.get('forecast','daily') not in ('none','daily','hourly','twice_daily'):raise ValueError('Ungültige Vorhersage')
    if kind=='countdown':
        if config.get('mode','auto') not in ('auto','timestamp','seconds','minutes','hours'):raise ValueError('Ungültiger Countdownmodus')
        if number(config.get('total',0)) is None or not 0<=float(config.get('total',0))<=31536000:raise ValueError('Gesamtdauer: 0 bis ein Jahr in Sekunden')

def seconds(value):
    if not isinstance(value,str):return None
    try:
        parts=[float(x) for x in value.split(':')]
        return sum(x*60**i for i,x in enumerate(reversed(parts))) if 1<=len(parts)<=3 and all(math.isfinite(x) and x>=0 for x in parts) else None
    except ValueError:return None

def countdown(widget,states):
    entity=widget['entity_id'];raw=states.get('__raw__',{}).get(entity,('unavailable',''))[0]
    attrs=states.get('__attributes__',{}).get(entity,{})
    if raw in ('unknown','unavailable',''):return None,0
    config=widget.get('config',{});mode=config.get('mode','auto');remaining=None
    total=number(config.get('total'),0)
    if entity.startswith('timer.'):
        total=total or seconds(attrs.get('duration')) or 0
        if raw=='idle':return 0,total
        if raw=='paused':remaining=seconds(attrs.get('remaining'))
        else:raw=attrs.get('finishes_at','');mode='timestamp'
    if remaining is None:
        numeric=number(raw)
        if mode=='timestamp' or (mode=='auto' and numeric is None):
            try:
                target=datetime.fromisoformat(str(raw).replace('Z','+00:00'))
                if target.tzinfo is None:
                    from zoneinfo import ZoneInfo
                    target=target.replace(tzinfo=ZoneInfo(states.get('__timezone__','UTC')))
                remaining=target.timestamp()-states.get('__now__',0)
            except (ValueError,TypeError):return None,total
        else:remaining=None if numeric is None else numeric*{'minutes':60,'hours':3600}.get(mode,1)
    return (max(0,remaining) if remaining is not None and math.isfinite(remaining) else None),total

def cost_value(widget,states):
    config=widget.get('config',{});value,unit=states.get('__raw__',{}).get(widget['entity_id'],('unavailable',''))
    value=number(value)
    price=number(states.get('__raw__',{}).get(config['tariff_entity_id'],('unavailable',''))[0]) if config.get('tariff_entity_id') else number(config.get('price',.3))
    scales={'energy':{'Wh':.001,'kWh':1,'MWh':1000},'power':{'W':.001,'kW':1,'MW':1000}}
    scale=scales[config.get('mode','energy')].get(unit)
    if value is None or price is None:return 'Nicht verfügbar'
    if scale is None:return 'Einheit prüfen'
    result=(abs(value) if config.get('absolute') else value)*scale*price
    if not math.isfinite(result):return 'Nicht verfügbar'
    return f'{result:.2f} {config.get("currency","EUR")}' + ('/h' if config.get('mode')=='power' else '')

def weather_icon(draw,condition,x,y,color):
    if condition in ('sunny','clear-night','partlycloudy'):
        draw.ellipse((x+8,y+4,x+26,y+22),fill=color)
        if condition=='clear-night':draw.ellipse((x+14,y,x+30,y+16),fill='#6750a4')
        else:
            for dx,dy in [(0,-4),(0,30),(-5,13),(34,13)]:draw.line((x+dx,y+dy,x+dx+3,y+dy+3),fill=color,width=2)
    if condition not in ('sunny','clear-night'):
        draw.ellipse((x,y+14,x+24,y+33),fill=color);draw.ellipse((x+14,y+8,x+38,y+33),fill=color);draw.rectangle((x+8,y+22,x+30,y+33),fill=color)
    if condition in ('rainy','pouring','lightning-rainy','snowy-rainy'):
        for i in range(3):draw.line((x+8+i*10,y+38,x+4+i*10,y+44),fill=color,width=2)

def tile(widget,states,theme):
    w,h=widget['width'],widget['height'];color=widget['color'];style=widget.get('style',{})
    image=Image.new('RGBA',(w,h));draw=ImageDraw.Draw(image);font=ImageFont.load_default(size=widget['size']);small=ImageFont.load_default(size=12)
    draw.rounded_rectangle((0,0,w-1,h-1),radius=min(style.get('radius',12),h//2,w//2),fill=style.get('background','#f3edf7' if theme=='material_light' else '#211f26'))
    draw.text((8,6),widget['text'][:40],font=small,fill=color)
    kind=widget['kind']
    if kind=='cost':draw.text((8,26),cost_value(widget,states),font=font,fill=color)
    elif kind=='countdown':
        remaining,total=countdown(widget,states)
        if remaining is None:label='Nicht verfügbar'
        else:
            minutes,sec=divmod(math.ceil(remaining),60);hours,minutes=divmod(minutes,60);label=f'{hours:02}:{minutes:02}:{sec:02}' if hours else f'{minutes:02}:{sec:02}'
        draw.text((8,26),label,font=font,fill=color)
        if total>0 and remaining is not None:
            draw.rectangle((8,max(0,h-10),w-8,h-5),fill='#6750a4');draw.rectangle((8,max(0,h-10),8+max(0,min(1,1-remaining/total))*max(0,w-16),h-5),fill=color)
    elif kind=='weather':
        entity=widget['entity_id'];attrs=states.get('__attributes__',{}).get(entity,{})
        condition=states.get('__raw__',{}).get(entity,('unavailable',''))[0];temperature=number(attrs.get('temperature'))
        weather_icon(draw,condition,8,26,color)
        draw.text((56,24),'—' if temperature is None else f'{temperature:g} {attrs.get("temperature_unit","°C")}',font=font,fill=color)
        draw.text((56,54),CONDITIONS.get(condition,'Nicht verfügbar'),font=small,fill=color)
        forecast=states.get('__forecast__',{}).get(entity,[])
        if widget.get('config',{}).get('forecast','daily')!='none':
            for i,item in enumerate(forecast[:3]):
                x=8+i*max(1,(w-16)//3);value=number(item.get('temperature'));when=str(item.get('datetime',''))
                label=when[11:16] if widget.get('config',{}).get('forecast')=='hourly' else when[5:10]
                draw.text((x,82),label,font=small,fill=color);draw.text((x,99),'—' if value is None else f'{value:g}°',font=small,fill=color)
            if not forecast:draw.text((8,82),'Keine Vorhersage verfügbar',font=small,fill=color)
    return image
