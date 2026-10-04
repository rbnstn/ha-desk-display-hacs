"""Bounded declarative rules; no templates, scripts or service execution."""
import copy
import math
import re

ENTITY=re.compile(r'[a-z_][a-z0-9_]*\.[a-z0-9_]+\Z')
COLOR=re.compile(r'#[0-9a-fA-F]{6}\Z')
OPS=('eq','ne','gt','gte','lt','lte','missing')

def validate_condition(condition):
    if not isinstance(condition,dict) or set(condition)!={'entity_id','op','value'}:
        raise ValueError('Ungueltige Bedingung')
    if not isinstance(condition['entity_id'],str) or not ENTITY.fullmatch(condition['entity_id']) or condition['op'] not in OPS:
        raise ValueError('Bedingung: Entitaet und Vergleich auswaehlen')
    if not isinstance(condition['value'],str) or len(condition['value'])>80:
        raise ValueError('Vergleichswert: maximal 80 Zeichen')
    if condition['op'] in ('gt','gte','lt','lte'):
        try:
            if not math.isfinite(float(condition['value'])):raise ValueError()
        except ValueError as error:raise ValueError('Vergleich benoetigt eine endliche Zahl') from error
    return copy.deepcopy(condition)

def validate_rules(widget):
    if 'visible_when' in widget:validate_condition(widget['visible_when'])
    rules=widget.get('rules',[])
    if not isinstance(rules,list) or len(rules)>4:raise ValueError('Maximal vier Farbregeln')
    for rule in rules:
        if not isinstance(rule,dict) or set(rule)!={'when','color','symbol'}:raise ValueError('Ungueltige Farbregel')
        validate_condition(rule['when'])
        if not isinstance(rule['color'],str) or not COLOR.fullmatch(rule['color']):raise ValueError('Ungueltige Regelfarbe')
        if not isinstance(rule['symbol'],str) or len(rule['symbol'])>4 or any(ord(c)<32 for c in rule['symbol']):raise ValueError('Symbol: maximal vier Zeichen')

def entities(widget):
    linked=[widget.get('entity_id',''),widget.get('value',{}).get('fallback_entity_id',''),widget.get('config',{}).get('tariff_entity_id','')]
    if widget['kind']=='energy':linked.extend(widget.get('config',{}).get(role,'') for role in ('solar','house','battery','grid'))
    return [e for e in linked if e]+[c['entity_id'] for c in ([widget['visible_when']] if 'visible_when' in widget else [])+[r['when'] for r in widget.get('rules',[])]]

def matches(condition,states):
    entity=condition['entity_id'];raw=states.get('__raw__',{}).get(entity)
    state=str(raw[0] if raw is not None else states.get(entity,'unavailable'))
    missing=state in ('unknown','unavailable','Nicht verfuegbar','')
    op=condition['op'];value=condition['value']
    if op=='missing':return missing
    if missing:return False
    if op=='eq':return state==value
    if op=='ne':return state!=value
    try:
        a,b=float(state),float(value)
        if not math.isfinite(a) or not math.isfinite(b):return False
        return {'gt':a>b,'gte':a>=b,'lt':a<b,'lte':a<=b}[op]
    except (ValueError,KeyError):return False

def resolve_layout(layout,states):
    layout=copy.deepcopy(layout);widgets=[]
    for widget in layout['widgets']:
        if widget.get('hidden'):continue
        design=layout.get('design',{})
        if widget.get('inherit_design',True) and widget['kind']!='navigation':
            for key in ('color','size'):
                if key in design:widget[key]=design[key]
            if design:widget['style']={**widget.get('style',{}),**{k:v for k,v in design.items() if k in ('background','radius','surface')}}
        if 'visible_when' in widget and not matches(widget['visible_when'],states):continue
        for rule in widget.get('rules',[]):
            if matches(rule['when'],states):
                widget['color']=rule['color']
                if rule['symbol']:widget['text']=(rule['symbol']+' '+widget['text'])[:80]
                break
        widget.pop('rules',None);widget.pop('visible_when',None);widgets.append(widget)
    layout['widgets']=widgets
    if 'overlay' in layout:layout['overlay']=resolve_layout(layout['overlay'],states)
    return layout
