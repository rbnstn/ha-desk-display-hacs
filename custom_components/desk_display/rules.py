"""Bounded declarative rules; no templates, scripts or service execution."""
import copy
import math
import re
import json
from time import monotonic

ENTITY=re.compile(r'[a-z_][a-z0-9_]*\.[a-z0-9_]+\Z')
COLOR=re.compile(r'#[0-9a-fA-F]{6}\Z')
OPS=('eq','ne','gt','gte','lt','lte','missing')

def validate_condition(condition):
    if not isinstance(condition,dict) or not {'entity_id','op','value'} <= set(condition) <= {'entity_id','op','value','hysteresis','delay'}:
        raise ValueError('Ungueltige Bedingung')
    if not isinstance(condition['entity_id'],str) or not ENTITY.fullmatch(condition['entity_id']) or condition['op'] not in OPS:
        raise ValueError('Bedingung: Entitaet und Vergleich auswaehlen')
    if not isinstance(condition['value'],str) or len(condition['value'])>80:
        raise ValueError('Vergleichswert: maximal 80 Zeichen')
    if condition['op'] in ('gt','gte','lt','lte'):
        try:
            if not math.isfinite(float(condition['value'])):raise ValueError()
        except ValueError as error:raise ValueError('Vergleich benoetigt eine endliche Zahl') from error
    hysteresis=condition.get('hysteresis',0)
    if type(hysteresis) not in (int,float) or not math.isfinite(hysteresis) or not 0<=hysteresis<=1e9:
        raise ValueError('Hysterese: endliche Zahl von 0 bis 1000000000')
    if hysteresis and condition['op'] not in ('gt','gte','lt','lte'):
        raise ValueError('Hysterese nur bei Zahlenvergleichen')
    delay=condition.get('delay',0)
    if type(delay) not in (int,float) or not math.isfinite(delay) or not 0<=delay<=300:
        raise ValueError('Verzögerung: 0 bis 300 Sekunden')
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
    if widget['kind']=='energy':linked.extend(widget.get('config',{}).get(role,'') for role in ('solar','house','battery','grid','battery_soc','wallbox'))
    return [e for e in linked if e]+[c['entity_id'] for c in ([widget['visible_when']] if 'visible_when' in widget else [])+[r['when'] for r in widget.get('rules',[])]]

def condition_key(condition):
    return json.dumps(condition,sort_keys=True,separators=(",",":"))

def matches(condition,states):
    resolved=states.get("__conditions__",{})
    if condition_key(condition) in resolved:return resolved[condition_key(condition)]
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
        # The renderer can resolve this copy again; do not overwrite a matched color.
        widget['inherit_design']=False
        widget.pop('rules',None);widget.pop('visible_when',None);widgets.append(widget)
    layout['widgets']=widgets
    if 'overlay' in layout:layout['overlay']=resolve_layout(layout['overlay'],states)
    return layout



class RuleEngine:
    """Per-device runtime memory. Draft simulation stays stateless."""
    def __init__(self):
        self.memory={}

    def evaluate(self,condition,states,now=None,prime=False):
        now=monotonic() if now is None else now
        key=condition_key(condition)
        active,pending,since=self.memory.get(key,(False,None,now))
        plain={k:v for k,v in condition.items() if k not in ('hysteresis','delay')}
        if active and condition.get('hysteresis') and plain['op'] in ('gt','gte','lt','lte'):
            threshold=float(plain['value'])
            threshold+=(-1 if plain['op'] in ('gt','gte') else 1)*condition['hysteresis']
            plain['value']=str(threshold)
        desired=matches(plain,{k:v for k,v in states.items() if k!='__conditions__'})
        if prime:
            active=desired;pending=None
        elif desired==active:
            pending=None
        else:
            if pending!=desired:pending=desired;since=now
            if now-since>=condition.get('delay',0):active=desired;pending=None
        self.memory[key]=(active,pending,since)
        return active

    def snapshot(self,conditions,states,now=None):
        keys={condition_key(c) for c in conditions}
        self.memory={k:v for k,v in self.memory.items() if k in keys}
        states['__conditions__']={condition_key(c):self.evaluate(c,states,now) for c in conditions}
        return states
