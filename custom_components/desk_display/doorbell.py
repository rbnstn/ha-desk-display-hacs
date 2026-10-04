"""Optional modal doorbell overlay, with bounded configuration and trigger rules."""

import copy
from datetime import datetime, timezone
from .models import ENTITY, get_layout, validate_layout
from .actions import BUTTON_SERVICES

DEFAULT_DOORBELL={'enabled':False,'entity_id':'','camera':'','open_entity_id':'','duration':30,'preload':False,
                 'post_open_duration':45,'door_state_entity_id':''}


def validate_doorbell(value):
    required={'enabled','entity_id','camera','open_entity_id','duration'}
    if not isinstance(value,dict) or not required<=set(value)<=set(DEFAULT_DOORBELL):
        raise ValueError('Ungueltige Klingelkonfiguration')
    value={**DEFAULT_DOORBELL,**value}
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
        if value['enabled'] and not entity and key!='door_state_entity_id':
            raise ValueError('Bitte Klingel, Kamera und Tuer-Button auswaehlen')
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
    def widget(kind,text,entity,x,y,width,height,size=20):
        return dict(kind=kind,text=text,entity_id=entity,x=x,y=y,width=width,height=height,size=size,color='#ffffff')
    camera=widget('media','', '',24,52,432,180)
    camera.update(source=config['camera'],fps=1)
    layout = {'background':'#101827','widgets':[
        widget('text','Jemand an der Tuer','',24,20,432,28),camera,
        widget('button','Tuer oeffnen',config['open_entity_id'],24,244,432,48,24)]}
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
        button=layout['overlay']['widgets'][-1]
        labels={'pending':('Wird geoeffnet ...','#ffd166'),
                'sent':('Befehl ausgefuehrt','#57d9b0'),
                'error':('Fehler - erneut tippen','#ff8080'),
                'uncertain':('Ergebnis unklar','#ffd166')}
        if status in labels:
            button['text'],button['color']=labels[status]
        header=layout['overlay']['widgets'][0]
        states=getattr(getattr(coordinator,'hass',None),'states',None)
        contact=states.get(config['door_state_entity_id']) if states and config['door_state_entity_id'] else None
        lock=states.get(config['open_entity_id']) if states and config['open_entity_id'].startswith('lock.') else None
        if config['door_state_entity_id']:
            header['text']='Tuer offen' if contact and contact.state=='on' else 'Tuer geschlossen' if contact and contact.state=='off' else 'Tuerstatus unbekannt'
            header['color']=('#087f5b' if layout.get('theme')=='material_light' else '#57d9b0') if contact and contact.state=='on' else ('#1d1b20' if layout.get('theme')=='material_light' else '#ffffff')
        elif lock and lock.state in ('open','opening','unlocked','locked'):
            header['text']={'open':'Falle freigegeben','opening':'Schloss oeffnet ...',
                            'unlocked':'Schloss entriegelt','locked':'Schloss verriegelt'}[lock.state]
        elif status=='sent':
            header['text']='Oeffnungsbefehl ausgefuehrt'
    from .rules import entities, resolve_layout
    hass=getattr(coordinator,'hass',None)
    if hass:
        raw={entity:(state.state,'') if (state:=hass.states.get(entity)) else ('unavailable','')
             for w in layout['widgets'] for entity in entities(w)}
        layout=resolve_layout(layout,{'__raw__':raw})
    return layout


def video_widget(layout):
    page=layout.get('overlay',layout)
    return next((w for w in page['widgets'] if w['kind']=='media'),None)
