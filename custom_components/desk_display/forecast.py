"""Bounded weather forecasts through the installed Home Assistant integration."""
import asyncio
from time import monotonic

async def augment_forecasts(hass,layout,states):
    states['__forecast__']={}
    widgets=[w for w in layout['widgets']+layout.get('overlay',{}).get('widgets',[]) if w['kind']=='weather' and w.get('config',{}).get('forecast','daily')!='none']
    if not widgets:return
    cache=hass.data.setdefault('desk_display_forecasts',{})
    for widget in widgets:
        entity=widget['entity_id'];mode=widget.get('config',{}).get('forecast','daily');key=(entity,mode);entry=cache.get(key)
        if entry is None or monotonic()-entry[0]>900:
            items=[]
            try:
                async with asyncio.timeout(5):
                    result=await hass.services.async_call('weather','get_forecasts',{'entity_id':entity,'type':mode},blocking=True,return_response=True)
                items=[{key:value for key,value in item.items() if key in ('datetime','temperature','templow','condition')} for item in result.get(entity,{}).get('forecast',[])[:3]]
            except (Exception,):pass
            entry=(monotonic(),items);cache[key]=entry
            if len(cache)>40:cache.pop(next(iter(cache)))
        states['__forecast__'][key]=entry[1]
        states['__forecast__'].setdefault(entity,entry[1])

