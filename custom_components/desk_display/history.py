"""Cached, bounded history for small charts; recorder remains optional."""
from datetime import timedelta
from functools import partial
from time import monotonic
from .widgets import number


def sample_history(items,start,end,limit=120):
    """Keep time gaps instead of pretending missing values are measurements."""
    result=[]
    for item in items:
        value=number(item.state)
        timestamp=item.last_updated.timestamp()
        if start<=timestamp<=end:result.append((timestamp,value))
    if len(result)>limit:
        result=[result[round(i*(len(result)-1)/(limit-1))] for i in range(limit)]
    return result


async def augment_states(hass,layout,states):
    from homeassistant.util import dt as dt_util
    charts=[w for w in layout['widgets']+layout.get('overlay',{}).get('widgets',[]) if w['kind']=='chart']
    states['__history__']={}
    states['__covers__']={}
    cache=hass.data.setdefault('desk_display_history',{})
    now=dt_util.utcnow()
    for widget in charts:
        entity=widget['entity_id'];minutes=widget.get('config',{}).get('minutes',60);key=(entity,minutes)
        start=now-timedelta(minutes=minutes)
        entry=cache.get(key)
        if not entry or monotonic()-entry[0]>60:
            points=[]
            if 'recorder' in hass.data:
                try:
                    from homeassistant.components.recorder import get_instance
                    from homeassistant.components.recorder.history import get_significant_states
                    query=partial(get_significant_states,hass,start,now,[entity],no_attributes=True)
                    data=await get_instance(hass).async_add_executor_job(query)
                    points=sample_history(data.get(entity,[]),start.timestamp(),now.timestamp())
                except Exception:pass
            entry=(monotonic(),points,start.timestamp(),now.timestamp());cache[key]=entry
            if len(cache)>40:cache.pop(next(iter(cache)))
        states['__history__'][entity]=(entry[1],entry[2],entry[3])
    cover_cache=hass.data.setdefault('desk_display_covers',{})
    for widget in layout['widgets']:
        if widget['kind']!='player':continue
        entity=widget['entity_id'];attributes=states.get('__attributes__',{}).get(entity,{})
        signature=(attributes.get('entity_picture'),attributes.get('media_title'))
        entry=cover_cache.get(entity)
        if entry is None or entry[1]!=signature:
            picture=None
            try:
                from homeassistant.components.media_player import DATA_COMPONENT
                component=hass.data.get(DATA_COMPONENT);player=component.get_entity(entity) if component else None
                if player:
                    import asyncio
                    async with asyncio.timeout(5):data,_mime=await player.async_get_media_image()
                    if data and len(data)<=1000000:
                        import base64
                        from io import BytesIO
                        from PIL import Image
                        def normalize():
                            image=Image.open(BytesIO(data));image.thumbnail((128,128));output=BytesIO();image.convert('RGBA').save(output,format='PNG');return 'data:image/png;base64,'+base64.b64encode(output.getvalue()).decode()
                        picture=await hass.async_add_executor_job(normalize)
            except Exception:pass
            entry=(monotonic(),signature,picture);cover_cache[entity]=entry
            if len(cover_cache)>40:cover_cache.pop(next(iter(cover_cache)))
        if entry[2]:states['__covers__'][entity]=entry[2]
    return states
