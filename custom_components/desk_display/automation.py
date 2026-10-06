"""Explicit notification/page services and bounded page conditions."""
from .const import DOMAIN
from .rules import validate_condition,matches


def validate_notification_rules(rules):
    if not isinstance(rules,list) or len(rules)>8:raise ValueError('Maximal acht Hinweisregeln')
    for rule in rules:
        if not isinstance(rule,dict) or set(rule)!={'when','message','duration','priority'}:raise ValueError('Ungültige Hinweisregel')
        validate_condition(rule['when'])
        if not isinstance(rule['message'],str) or not 1<=len(rule['message'])<=160 or any(ord(c)<32 for c in rule['message']):raise ValueError('Hinweis: 1 bis 160 Zeichen')
        if type(rule['duration']) is not int or not 5<=rule['duration']<=300:raise ValueError('Hinweis: 5 bis 300 Sekunden')
        if type(rule['priority']) is not int or not 0<=rule['priority']<=3:raise ValueError('Priorität: 0 bis 3')


class NotificationRules:
    def __init__(self):
        from .rules import RuleEngine
        self.engine=RuleEngine();self.active={}

    def evaluate(self,rules,states,now=None):
        import json
        from .rules import condition_key
        triggered=[];keys=set()
        for index,rule in enumerate(rules):
            key=(index,json.dumps(rule,sort_keys=True));keys.add(key)
            active=self.engine.evaluate(rule['when'],states,now=now,prime=key not in self.active)
            if active and self.active.get(key,active) is False:triggered.append(rule)
            self.active[key]=active
        self.active={key:value for key,value in self.active.items() if key in keys}
        condition_keys={condition_key(rule['when']) for rule in rules}
        self.engine.memory={key:value for key,value in self.engine.memory.items() if key in condition_keys}
        return triggered


def validate_page_rules(rules):
    if not isinstance(rules,list) or len(rules)>8:raise ValueError('Maximal acht Seitenregeln')
    for rule in rules:
        if not isinstance(rule,dict) or set(rule)!={'when','page','duration'}:raise ValueError('Ungueltige Seitenregel')
        validate_condition(rule['when'])
        if type(rule['page']) is not int or not 0<=rule['page']<=3:raise ValueError('Ungueltige Zielseite')
        if type(rule['duration']) is not int or not 5<=rule['duration']<=300:raise ValueError('Seitenanzeige: 5 bis 300 Sekunden')


def register_services(hass):
    import voluptuous as vol
    from homeassistant.helpers import config_validation as cv,device_registry as dr
    base={vol.Optional('entry_id'):str,vol.Optional('device_id'):vol.All(cv.ensure_list,[str])}
    def coordinators(data):
        ids=set([data['entry_id']]) if data.get('entry_id') else set()
        registry=dr.async_get(hass)
        for device_id in data.get('device_id',[]):
            device=registry.async_get(device_id)
            if device:ids.update(device.config_entries)
        result=[coordinator for entry,coordinator in hass.data[DOMAIN].items() if entry in ids]
        if not result:raise vol.Invalid('Desk-Display-Geraet auswaehlen')
        return result
    async def notify(call):
        for coordinator in coordinators(call.data):
            coordinator.notify(call.data['message'],call.data['duration'],call.data['priority'])
            await coordinator.async_refresh()
    async def show_page(call):
        for coordinator in coordinators(call.data):
            coordinator.show_page(call.data['page'],call.data['duration']);await coordinator.async_refresh()
    hass.services.async_register(DOMAIN,'notify',notify,schema=vol.Schema({**base,vol.Required('message'):vol.All(str,vol.Length(min=1,max=160)),vol.Optional('duration',default=15):vol.All(int,vol.Range(min=5,max=300)),vol.Optional('priority',default=0):vol.All(int,vol.Range(min=0,max=3))}))
    hass.services.async_register(DOMAIN,'show_page',show_page,schema=vol.Schema({**base,vol.Required('page'):vol.All(int,vol.Range(min=0,max=3)),vol.Optional('duration',default=30):vol.All(int,vol.Range(min=5,max=300))}))
