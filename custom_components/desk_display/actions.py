"""Resolve touches only against the layout successfully sent by HA."""

import re

BUTTON_SERVICES = {"button": "press", "input_button": "press", "script": "turn_on", "lock": "open"}
SWITCH_SERVICES = {"switch": "toggle", "input_boolean": "toggle"}


def widget_at(layout,x,y):
    if 'overlay' in layout:return widget_at(layout['overlay'],x,y)
    return next((w for w in reversed(layout['widgets']) if w['x']<=x<w['x']+w['width'] and w['y']<=y<w['y']+w['height']),None)


def action_at(layout, x, y,gesture='tap'):
    """The topmost rectangle blocks widgets underneath, including plain text."""
    if gesture in ('left','right'):return None
    if 'overlay' in layout:
        return action_at(layout['overlay'],x,y,gesture)
    for widget in reversed(layout["widgets"]):
        if widget["x"] <= x < widget["x"] + widget["width"] and (
            widget["y"] <= y < widget["y"] + widget["height"]
        ):
            if widget['kind']=='sensor' and gesture=='tap' and widget.get('config',{}).get('detail_enabled'):return ('desk_display','detail',widget['entity_id'])
            if widget['kind']=='navigation':return ('desk_display','page',str(widget['target']))
            if widget['kind']=='button' and gesture=='hold':
                entity=widget.get('config',{}).get('hold_entity_id','')
                domain=entity.split('.')[0]
                return (domain,BUTTON_SERVICES[domain],entity) if domain in BUTTON_SERVICES else None
            if widget['kind']=='slider':
                domain=widget['entity_id'].split('.')[0]
                return (domain,{'light':'turn_on','media_player':'volume_set','number':'set_value','input_number':'set_value'}[domain],widget['entity_id'])
            if widget['kind']=='player':
                relative_y=y-widget['y']
                service='volume_set' if relative_y<widget['height']-28 and relative_y>=widget['height']-52 else ['media_previous_track','media_play_pause','media_next_track'][min(2,(x-widget['x'])*3//widget['width'])] if relative_y>=widget['height']-28 else None
                return ('media_player',service,widget['entity_id']) if service else None
            domain = widget["entity_id"].split(".", 1)[0]
            services = BUTTON_SERVICES if widget["kind"] == "button" else (
                SWITCH_SERVICES if widget["kind"] == "switch" else {})
            service = services.get(domain)
            return (domain, service, widget["entity_id"]) if service else None
    return None


def validate_touch(event):
    if not isinstance(event, dict) or not {"id", "revision", "x", "y"}<=set(event)<={"id", "revision", "x", "y", "gesture", "value_x"}:
        raise ValueError("Invalid touch event")
    if not isinstance(event["id"], str) or not re.fullmatch(r"[0-9a-f]{8}-[0-9]{1,10}", event["id"]):
        raise ValueError("Invalid touch ID")
    if not isinstance(event["revision"], str) or not re.fullmatch(r"[0-9a-f]{32}", event["revision"]):
        raise ValueError("Invalid frame revision")
    for key, bound in (("x", 480), ("y", 320)):
        if type(event[key]) is not int or not 0 <= event[key] < bound:
            raise ValueError("Invalid touch position")
    if 'value_x' in event and (type(event['value_x']) is not int or not 0<=event['value_x']<480):raise ValueError('Invalid slider touch position')
    if event.get('gesture','tap') not in ('tap','hold','left','right'):raise ValueError('Invalid touch gesture')
    return event


def command_data(widget,x,attributes,service):
    data={'entity_id':widget['entity_id']}
    if widget['kind'] in ('slider','player'):
        fraction=max(0,min(1,(x-widget['x'])/max(1,widget['width']-1)))
        domain=widget['entity_id'].split('.')[0]
        if service=='volume_set':data['volume_level']=round(fraction,2)
        elif domain=='light':data['brightness_pct']=round(fraction*100)
        elif domain in ('number','input_number'):
            minimum=float(attributes.get('min',0));maximum=float(attributes.get('max',100));step=float(attributes.get('step',1))
            if not all(__import__('math').isfinite(v) for v in (minimum,maximum,step)) or maximum<=minimum or step<=0:raise ValueError('Invalid numeric entity range')
            data['value']=max(minimum,min(maximum,minimum+round(fraction*(maximum-minimum)/step)*step))
    return data

