"""Optional modal doorbell overlay, with bounded configuration and trigger rules."""

import copy
from datetime import datetime, timezone
from .models import ENTITY, get_layout, validate_layout
from .actions import BUTTON_SERVICES

DEFAULT_DOORBELL={'enabled':False,'entity_id':'','camera':'','open_entity_id':'','duration':30,'preload':False,
                 'post_open_duration':45,'door_state_entity_id':'','open_enabled':True,'open_label':'Tuer oeffnen','layout':None,'history_enabled':False,'history_images':False,'history_days':7}


def validate_doorbell(value):
    required={'enabled','entity_id','camera','open_entity_id','duration'}
    if not isinstance(value,dict) or not required<=set(value)<=set(DEFAULT_DOORBELL):
        raise ValueError('Ungueltige Klingelkonfiguration')
    value={**DEFAULT_DOORBELL,**value}
    if type(value['history_enabled']) is not bool or type(value['history_images']) is not bool or type(value['history_days']) is not int or not 1<=value['history_days']<=30:raise ValueError('Klingelverlauf: 1 bis 30 Tage, Speicherung optional')
    if type(value['open_enabled']) is not bool or not isinstance(value['open_label'],str) or not 1<=len(value['open_label'].strip())<=80 or any(ord(c)<32 for c in value['open_label']):
        raise ValueError('Ungueltige Tuerknopf-Einstellungen')
    if type(value['preload']) is not bool:
        raise ValueError('Ungueltige Kameravorbereitung')
    if type(value['enabled']) is not bool or type(value['duration']) is not int or not 5<=value['duration']<=300:
        raise ValueError('Klingelansicht: Dauer 5 bis 300 Sekunden')
    if type(value['post_open_duration']) is not int or not 5<=value['post_open_duration']<=300:
        raise ValueError('Nachlauf nach Oeffnen: 5 bis 300 Sekunden')
    domains={'entity_id':('binary_sensor','event','input_button'),
             'camera':('camera',),'open_entity_id':tuple(BUTTON_SERVICES),'door_state_entity_id':('binary_sensor',)}
    for key,allowed in domains.items():
        entity=value[key]
        if not isinstance(entity,str) or (entity and (not ENTITY.fullmatch(entity) or entity.split('.')[0] not in allowed)):
            raise ValueError('Ungueltige Entitaet fuer '+key)
        if value['enabled'] and not entity and key!='door_state_entity_id' and (key!='open_entity_id' or value['open_enabled']):
            raise ValueError('Bitte Klingel, Kamera und Tuer-Button auswaehlen')
    if value['layout'] is not None:
        layout=validate_layout(value['layout'])
        if set(layout)-{'background','widgets','theme','debug','design'}:raise ValueError('Klingel-Layout enthaelt keine Seiten oder weiteren Overlays')
        if sum(w['kind']=='media' for w in layout['widgets'])!=1:raise ValueError('Klingel-Layout benoetigt genau eine Kamera')
        for role in ('title','door_status','door_open'):
            if sum(w.get('role')==role for w in layout['widgets'])>1:raise ValueError('Klingelrolle darf nur einmal vorkommen')
        value['layout']=layout
    return copy.deepcopy(value)


def get_doorbell(options):
    return validate_doorbell(options.get('doorbell',DEFAULT_DOORBELL))


def is_ring(config,entity_id,before,after):
    if not config['enabled'] or entity_id!=config['entity_id'] or before is None or after is None:
        return False
    if after.state in ('unknown','unavailable') or before.state==after.state:
        return False
    if entity_id.startswith('binary_sensor.'):
        return before.state=='off' and after.state=='on'
    # Permit the first actual event from "unknown", without replaying a restored timestamp.
    try:
        timestamp=datetime.fromisoformat(after.state)
        age=(datetime.now(timezone.utc)-timestamp).total_seconds()
    except (ValueError,TypeError):
        return False
    return -2<=age<=10


def overlay_layout(config, theme='classic'):
    if config.get('layout'):
        layout=copy.deepcopy(config['layout'])
        layout['widgets']=[w for w in layout['widgets'] if config.get('open_enabled',True) or w.get('role')!='door_open']
        for widget in layout['widgets']:
            if widget['kind']=='media':widget.update(source=config['camera'],fps=1)
            if widget.get('role')=='door_open':widget.update(entity_id=config['open_entity_id'],text=config['open_label'])
        layout['fullscreen']=True
        return validate_layout(layout)
    def widget(kind,text,entity,x,y,width,height,size=20):
        return dict(kind=kind,text=text,entity_id=entity,x=x,y=y,width=width,height=height,size=size,color='#ffffff')
    has_button=config.get('open_enabled',True)
    camera=widget('media','', '',24,52,432,180 if has_button else 240)
    camera.update(source=config['camera'],fps=1)
    layout = {'background':'#101827','widgets':[
        widget('text','Jemand an der Tuer','',24,20,432,28),camera]}
    if has_button:
        layout['widgets'].append(widget('button',config.get('open_label','Tuer oeffnen'),config['open_entity_id'],24,244,432,48,24))
        layout['widgets'][-1]['role']='door_open'
    layout['widgets'][0]['role']='title'
    if theme in ('material_dark', 'material_light'):
        layout['theme'] = theme
        layout['background'] = '#fef7ff' if theme == 'material_light' else '#141218'
        layout['widgets'][0]['color'] = '#1d1b20' if theme == 'material_light' else '#e6e0e9'
    return validate_layout(layout)


def current_layout(coordinator):
    layout=get_layout(coordinator.entry.options)
    from .pages import page_layout
    layout=page_layout(layout,getattr(coordinator,'page_index',0))
    config=get_doorbell(coordinator.entry.options)
    if getattr(coordinator,'doorbell_active',False) and config['enabled']:
        layout['overlay']=overlay_layout(config, layout.get('theme', 'classic'))
        status=getattr(coordinator,'doorbell_feedback','')
        button=next((w for w in layout['overlay']['widgets'] if w.get('role')=='door_open'),None)
        labels={'pending':('Wird geoeffnet ...','#ffd166'),
                'sent':('Befehl ausgefuehrt','#57d9b0'),
                'error':('Fehler - erneut tippen','#ff8080'),
                'uncertain':('Ergebnis unklar','#ffd166')}
        if button and status in labels:
            button['text'],button['color']=labels[status]
        header=next((w for w in layout['overlay']['widgets'] if w.get('role')=='door_status'),None)
        if header is None:header=next((w for w in layout['overlay']['widgets'] if w.get('role')=='title'),layout['overlay']['widgets'][0])
        states=getattr(getattr(coordinator,'hass',None),'states',None)
        contact=states.get(config['door_state_entity_id']) if states and config['door_state_entity_id'] else None
        lock=states.get(config['open_entity_id']) if states and config['open_enabled'] and config['open_entity_id'].startswith('lock.') else None
        if config['door_state_entity_id']:
            header['text']='Tuer offen' if contact and contact.state=='on' else 'Tuer geschlossen' if contact and contact.state=='off' else 'Tuerstatus unbekannt'
            header['color']=('#087f5b' if layout.get('theme')=='material_light' else '#57d9b0') if contact and contact.state=='on' else ('#1d1b20' if layout.get('theme')=='material_light' else '#ffffff')
        elif lock and lock.state in ('open','opening','unlocked','locked'):
            header['text']={'open':'Falle freigegeben','opening':'Schloss oeffnet ...',
                            'unlocked':'Schloss entriegelt','locked':'Schloss verriegelt'}[lock.state]
        elif status=='sent':
            header['text']='Oeffnungsbefehl ausgefuehrt'
    if not getattr(coordinator,'doorbell_active',False) and getattr(coordinator,'detail_widget',None):
        from .detail import detail_layout
        layout['overlay']=detail_layout(coordinator.detail_widget,getattr(coordinator,'page_index',0),layout.get('theme','material_dark'))
    from .rules import entities, resolve_layout
    hass=getattr(coordinator,'hass',None)
    if hass and hasattr(hass,'states'):
        raw={entity:(state.state,'') if (state:=hass.states.get(entity)) else ('unavailable','')
             for w in layout['widgets']+layout.get('overlay',{}).get('widgets',[]) for entity in entities(w)}
        states={'__raw__':raw}
        if hasattr(coordinator,'resolve_conditions'):coordinator.resolve_conditions(layout,states)
        layout=resolve_layout(layout,states)
    return layout


def video_widget(layout):
    page=layout.get('overlay',layout)
    return next((w for w in page['widgets'] if w['kind']=='media'),None)

