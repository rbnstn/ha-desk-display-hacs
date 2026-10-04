"""Preview-only simulated states. Never used by the device or actions."""
from .rules import ENTITY

def apply_simulation(states,layout,simulation):
    if not isinstance(simulation,dict) or set(simulation)-{'states','door'}:raise ValueError('Ungueltige Simulation')
    overrides=simulation.get('states',{})
    if not isinstance(overrides,dict) or len(overrides)>12:raise ValueError('Maximal 12 simulierte Entitaeten')
    for entity,value in overrides.items():
        if not isinstance(entity,str) or not ENTITY.fullmatch(entity) or not isinstance(value,str) or len(value)>80:
            raise ValueError('Ungueltiger simulierter Zustand')
        unit=states['__raw__'].get(entity,('',''))[1]
        states['__raw__'][entity]=(value,unit);states[entity]=value
    door=simulation.get('door','')
    labels={'pending':'Wird geoeffnet ...','sent':'Befehl ausgefuehrt','error':'Fehler - erneut tippen','uncertain':'Ergebnis unklar','open':'Tuer offen','closed':'Tuer geschlossen','':''}
    if door not in labels:raise ValueError('Ungueltige Tuersimulation')
    if door and 'overlay' in layout:
        widgets=layout['overlay']['widgets']
        if door in ('open','closed'):widgets[0]['text']=labels[door]
        else:widgets[-1]['text']=labels[door]
    return bool(overrides or door)
