"""Optional modal doorbell overlay, with bounded configuration and trigger rules."""

import copy
from datetime import datetime, timezone
from .models import ENTITY, get_layout, validate_layout
from .actions import BUTTON_SERVICES

DEFAULT_DOORBELL={'enabled':False,'entity_id':'','camera':'','open_entity_id':'','duration':30,'preload':False}


def validate_doorbell(value):
    if not isinstance(value,dict) or set(value) not in (set(DEFAULT_DOORBELL),set(DEFAULT_DOORBELL)-{'preload'}):
        raise ValueError('Ungueltige Klingelkonfiguration')
    value={**DEFAULT_DOORBELL,**value}
    if type(value['preload']) is not bool:
        raise ValueError('Ungueltige Kameravorbereitung')
    if type(value['enabled']) is not bool or type(value['duration']) is not int or not 5<=value['duration']<=300:
        raise ValueError('Klingelansicht: Dauer 5 bis 300 Sekunden')
    domains={'entity_id':('binary_sensor','event','input_button'),
             'camera':('camera',),'open_entity_id':tuple(BUTTON_SERVICES)}
    for key,allowed in domains.items():
        entity=value[key]
        if not isinstance(entity,str) or (entity and (not ENTITY.fullmatch(entity) or entity.split('.')[0] not in allowed)):
            raise ValueError('Ungueltige Entitaet fuer '+key)
        if value['enabled'] and not entity:
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


def overlay_layout(config):
    def widget(kind,text,entity,x,y,width,height,size=20):
        return dict(kind=kind,text=text,entity_id=entity,x=x,y=y,width=width,height=height,size=size,color='#ffffff')
    camera=widget('media','', '',24,52,432,180)
    camera.update(source=config['camera'],fps=1)
    return validate_layout({'background':'#101827','widgets':[
        widget('text','Jemand an der Tuer','',24,20,432,28),camera,
        widget('button','Tuer oeffnen',config['open_entity_id'],24,244,432,48,24)]})


def current_layout(coordinator):
    layout=get_layout(coordinator.entry.options)
    config=get_doorbell(coordinator.entry.options)
    if getattr(coordinator,'doorbell_active',False) and config['enabled']:
        layout['overlay']=overlay_layout(config)
    return layout


def video_widget(layout):
    page=layout.get('overlay',layout)
    return next((w for w in page['widgets'] if w['kind']=='media'),None)
