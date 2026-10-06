"""Validated presentation options and compact household information cards."""
import copy
import math
import re
from PIL import Image, ImageDraw, ImageFont

ENTITY = re.compile(r'[a-z_][a-z0-9_]*\.[a-z0-9_]+\Z')
COLOR = re.compile(r'#[0-9a-fA-F]{6}\Z')


def validate_style(style):
    for key, choices in [('valign', ('top', 'middle', 'bottom')), ('font', ('sans', 'serif', 'mono')), ('weight', ('normal', 'bold'))]:
        if key in style and style[key] not in choices:raise ValueError('Ungültige Schriftoption')
    if 'unit_size' in style and (type(style['unit_size']) is not int or not 8<=style['unit_size']<=48):raise ValueError('Einheitengröße: 8 bis 48 Pixel')
    if 'unit_color' in style and (not isinstance(style['unit_color'],str) or not COLOR.fullmatch(style['unit_color'])):raise ValueError('Ungültige Einheitenfarbe')


def font_for(size, style):
    # Bundled fonts make preview and production independent of host packages.
    from pathlib import Path
    if style.get('font','sans')=='sans' and style.get('weight','normal')=='normal':return ImageFont.load_default(size=size)
    family={'sans':'Sans','serif':'Serif','mono':'SansMono'}[style.get('font','sans')]
    name='DejaVu'+family+('-Bold' if style.get('weight')=='bold' else '')+'.ttf'
    path=Path(__file__).with_name('fonts')/name
    return ImageFont.truetype(str(path),size) if path.exists() else ImageFont.load_default(size=size)


def validate_widget_options(widget):
    options=widget.get('availability',{})
    if not isinstance(options,dict) or set(options)-{'mode','text','stale_after','show_age'}:raise ValueError('Ungültige Verfügbarkeit')
    if options.get('mode','show') not in ('show','hide','replace'):raise ValueError('Ungültiger Ersatzmodus')
    if not isinstance(options.get('text',''),str) or len(options.get('text',''))>80:raise ValueError('Ersatztext: maximal 80 Zeichen')
    if type(options.get('stale_after',0)) is not int or not 0<=options.get('stale_after',0)<=604800:raise ValueError('Alter: 0 bis 604800 Sekunden')
    if type(options.get('show_age',False)) is not bool:raise ValueError('Ungültige Altersanzeige')
    icons=widget.get('icon_states',[])
    if not isinstance(icons,list) or len(icons)>4 or (icons and widget['kind'] not in ('icon','chip')):raise ValueError('Maximal vier Zustandsicons')
    from .rules import validate_condition
    from .pictures import image_bytes
    for item in icons:
        if not isinstance(item,dict) or set(item)!={'when','icon','image'}:raise ValueError('Ungültiges Zustandsicon')
        validate_condition(item['when']);image_bytes(item['image'])
        if not isinstance(item['icon'],str) or not re.fullmatch(r'[a-z0-9_-]+:[a-z0-9_-]+',item['icon']):raise ValueError('Ungültiges Icon')


def resolve_widget(widget,states):
    from .rules import matches
    widget=copy.deepcopy(widget)
    options=widget.get('availability',{})
    entity=widget.get('entity_id','')
    raw=states.get('__raw__',{}).get(entity,(states.get(entity,'unavailable'),''))[0]
    if entity and raw in ('unknown','unavailable','Nicht verfuegbar',''):
        if options.get('mode')=='hide':return None
        if options.get('mode')=='replace':
            widget.update(kind='text',text=options.get('text') or 'Nicht verfügbar',entity_id='')
            for key in ('config','value','icon','image','icon_states'):widget.pop(key,None)
    for item in widget.get('icon_states',[]):
        if matches(item['when'],states):widget.update(icon=item['icon'],image=item['image']);break
    return widget


def validate_schedule(items,pages):
    if not isinstance(items,list) or len(items)>8:raise ValueError('Maximal acht Zeitfenster')
    for item in items:
        if not isinstance(item,dict) or set(item)!={'start','end','page','days'}:raise ValueError('Ungültiger Seitenzeitplan')
        for key in ('start','end'):
            if not isinstance(item[key],str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',item[key]):raise ValueError('Uhrzeit HH:MM')
        if type(item['page']) is not int or not 0<=item['page']<=pages:raise ValueError('Zielseite fehlt')
        if not isinstance(item['days'],list) or not item['days'] or any(type(d) is not int or not 0<=d<=6 for d in item['days']):raise ValueError('Wochentage: Montag 0 bis Sonntag 6')
    return copy.deepcopy(items)


def scheduled_page(items,now):
    for item in items:
        time=now.strftime('%H:%M');start,end=item['start'],item['end']
        day=now.weekday() if start<=end or time>=start else (now.weekday()-1)%7
        if day in item['days'] and (start<=time<end if start<end else time>=start or time<end if start>end else False):return item['page']
    return None


def validate_config(widget):
    config=widget.get('config',{})
    allowed={'energy_day':{'solar','house','export','import','autarky','self_consumption'},'price':{'currency','cheap_below'},'ev_charge':{'target_entity_id','target'},'calendar':{'days','limit'}}[widget['kind']]
    if set(config)-allowed:raise ValueError('Unbekannte Kartenoption')
    for key in allowed-{'currency','cheap_below','target','days','limit'}:
        if key in config and (not isinstance(config[key],str) or (config[key] and not ENTITY.fullmatch(config[key]))):raise ValueError('Bitte HA-Entität auswählen')
    for key,low,high in [('cheap_below',-100,100),('target',0,100),('days',1,14),('limit',1,5)]:
        if key in config and (type(config[key]) not in (int,float) or not math.isfinite(config[key]) or not low<=config[key]<=high or (key in ('days','limit') and type(config[key]) is not int)):raise ValueError('Ungültiger Kartenbereich')
    if 'currency' in config and config['currency'] not in ('EUR','USD','CHF','GBP'):raise ValueError('Unbekannte Währung')
    if widget['kind']=='calendar' and not widget['entity_id'].startswith('calendar.'):raise ValueError('Bitte Kalender auswählen')


def numeric(states,entity):
    try:
        value=float(states.get('__raw__',{}).get(entity,('nan',''))[0])
        return value if math.isfinite(value) else None
    except (ValueError,TypeError):return None


def card_lines(widget,states):
    kind=widget['kind'];config=widget.get('config',{});entity=widget['entity_id']
    if kind=='energy_day':
        lines=[]
        for key,label in [('solar','Erzeugung'),('house','Verbrauch'),('export','Einspeisung'),('import','Bezug'),('autarky','Autarkie'),('self_consumption','Eigenverbrauch')]:
            if not config.get(key):continue
            value=numeric(states,config[key]);unit='%' if key in ('autarky','self_consumption') else 'kWh'
            if value is not None and states.get('__raw__',{}).get(config[key],('',''))[1]=='Wh':value/=1000
            lines.append(f'{label}: '+('—' if value is None else f'{value:.2f}'.replace('.',','))+f' {unit}')
        return lines or ['Tagesenergiesensoren auswählen']
    if kind=='ev_charge':
        value=numeric(states,entity);target=numeric(states,config.get('target_entity_id','')) if config.get('target_entity_id') else config.get('target',80)
        return ['Ladestand: '+('—' if value is None else f'{value:.0f} %'),'Ziel: '+('—' if target is None else f'{target:.0f} %'),'Bis zum Ziel: '+('—' if value is None or target is None else f'{max(0,target-value):.0f} %')]
    if kind=='calendar':
        events=states.get('__calendar__',{}).get(entity,[])
        return [f"{item['start']} · {item['summary']}" for item in events[:config.get('limit',3)]] or ['Keine anstehenden Termine']
    value=numeric(states,entity);currency=config.get('currency','EUR')
    lines=['Aktuell: '+('—' if value is None else f'{value:.3f}'.replace('.',','))+f' {currency}/kWh']
    attrs=states.get('__attributes__',{}).get(entity,{})
    # Explicit normalized HA template attribute; no provider-specific assumptions.
    prices=attrs.get('prices',[])
    valid=[]
    if isinstance(prices,list):
        for item in prices[:168]:
            if not isinstance(item,dict):continue
            try:
                price=float(item['price']);stamp=str(item['start'])
                if math.isfinite(price) and len(stamp)<=40:
                    from datetime import datetime,timezone
                    try:
                        parsed=datetime.fromisoformat(stamp)
                        if parsed.tzinfo is None:continue
                        if parsed.timestamp()<states.get('__now__',datetime.now(timezone.utc).timestamp()):continue
                    except ValueError:continue
                    valid.append((price,stamp))
            except (KeyError,ValueError,TypeError):continue
    if valid:
        price,stamp=min(valid);lines.append(f'Günstig: {stamp} · {price:.3f} {currency}/kWh')
        for price,stamp in valid:
            if price<=config.get('cheap_below',.2):lines.append(f'{stamp}: {price:.3f} {currency}/kWh')
    return lines[:5]


def tile(widget,states,theme):
    width,height=widget['width'],widget['height'];style=widget.get('style',{})
    image=Image.new('RGBA',(width,height));draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((0,0,width-1,height-1),radius=min(16,width//2,height//2),fill=style.get('background','#f3edf7' if theme=='material_light' else '#211f26'))
    lines=[widget['text'] or {'energy_day':'Energie heute','price':'Strompreis','ev_charge':'Auto laden','calendar':'Termine'}[widget['kind']],*card_lines(widget,states)]
    row=max(12,min(28,height//max(1,len(lines))))
    font=font_for(min(widget['size'],max(10,row-4)),style)
    for index,line in enumerate(lines):
        while line and font.getlength(line)>width-16:line=line[:-1]
        draw.text((8,index*row+3),line,font=font,fill=widget['color'])
    if widget['kind']=='ev_charge':
        value=numeric(states,widget['entity_id']);target=numeric(states,widget.get('config',{}).get('target_entity_id','')) if widget.get('config',{}).get('target_entity_id') else widget.get('config',{}).get('target',80)
        y=height-7;draw.line((8,y,width-8,y),fill='#49454f',width=4)
        if value is not None:draw.line((8,y,8+(width-16)*max(0,min(100,value))/100,y),fill=widget['color'],width=4)
        if target is not None:
            x=8+(width-16)*max(0,min(100,target))/100;draw.line((x,y-5,x,y+3),fill=widget['color'],width=2)
    return image
