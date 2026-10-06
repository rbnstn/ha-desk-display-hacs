"""Bounded calendar reads, cached outside rendering worker threads."""
from datetime import timedelta
from time import monotonic


async def augment_calendar(hass,layout,states):
    from homeassistant.util import dt as dt_util
    from homeassistant.exceptions import HomeAssistantError
    from .pages import all_widgets
    widgets=[w for w in all_widgets(layout) if w['kind']=='calendar']
    if not widgets:return
    cache=hass.data.setdefault('desk_display_calendar_cache',{})
    states['__calendar__']={}
    for widget in widgets:
        if widget['kind']!='calendar':continue
        entity=widget['entity_id'];days=widget.get('config',{}).get('days',7);key=(entity,days)
        saved=cache.get(key)
        if not saved or monotonic()-saved[0]>300:
            now=dt_util.now()
            try:
                result=await hass.services.async_call('calendar','get_events',{'entity_id':entity,'start_date_time':now.isoformat(),'end_date_time':(now+timedelta(days=days)).isoformat()},blocking=True,return_response=True)
                events=result.get(entity,{}).get('events',[]) if isinstance(result,dict) else []
                rows=[{'start':str(item.get('start',''))[:40],'summary':str(item.get('summary','Termin'))[:100]} for item in events[:50] if isinstance(item,dict)]
                cache[key]=(monotonic(),sorted(rows,key=lambda row:row['start']))
            except (HomeAssistantError,ValueError,TimeoutError):
                cache[key]=(monotonic(),saved[1] if saved else [])
            while len(cache)>64:cache.pop(next(iter(cache)))
        states['__calendar__'][entity]=cache[key][1]
