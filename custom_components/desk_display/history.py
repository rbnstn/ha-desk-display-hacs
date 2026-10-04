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
                except (ImportError,KeyError,RuntimeError):pass
            entry=(monotonic(),points,start.timestamp(),now.timestamp());cache[key]=entry
            if len(cache)>40:cache.pop(next(iter(cache)))
        states['__history__'][entity]=(entry[1],entry[2],entry[3])
    return states
