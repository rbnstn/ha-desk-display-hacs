"""Per-user templates stored in Home Assistant, with bounded validated payloads."""
import json
import asyncio
from homeassistant.helpers.storage import Store
from .models import validate_layout


class TemplateStore:
    def __init__(self,hass):
        self.store=Store(hass,1,'desk_display.templates');self.lock=asyncio.Lock();self.data=None

    async def access(self,user_id,items=None):
        async with self.lock:
            if self.data is None:self.data=await self.store.async_load() or {}
            if items is not None:
                validate_templates(items)
                self.data[user_id]=items
                await self.store.async_save(self.data)
            return self.data.get(user_id,[])


def validate_templates(items):
    if not isinstance(items,list) or len(items)>8 or len(json.dumps(items))>1800000:raise ValueError('Maximal acht Vorlagen und 1,8 MB')
    ids=set()
    for item in items:
        if not isinstance(item,dict) or set(item)!={'id','name','data'} or not isinstance(item['id'],str) or not 1<=len(item['id'])<=80 or item['id'] in ids:raise ValueError('Ungültige Vorlagen-ID')
        ids.add(item['id'])
        if not isinstance(item['name'],str) or not 1<=len(item['name'])<=40:raise ValueError('Vorlagenname: 1 bis 40 Zeichen')
        data=item['data']
        if not isinstance(data,dict) or data.get('version')!=1:raise ValueError('Ungültige Vorlage')
        if data.get('format')=='desk-display-page':validate_layout(data['page'])
        elif data.get('format')=='desk-display-components':validate_layout({'background':'#000000','widgets':data['widgets']})
        else:raise ValueError('Unbekanntes Vorlagenformat')


def get_store(hass):
    if 'desk_display_template_store' not in hass.data:hass.data['desk_display_template_store']=TemplateStore(hass)
    return hass.data['desk_display_template_store']
