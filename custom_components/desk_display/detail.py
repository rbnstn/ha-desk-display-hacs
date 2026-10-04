"""Temporary, read-only measurement details. Doorbell always takes priority."""
import copy

def detail_layout(widget,page,theme='material_dark'):
    light=theme=='material_light';color='#1d1b20' if light else '#e6e0e9'
    sensor=copy.deepcopy(widget);sensor.update(x=24,y=48,width=432,height=56,size=32);sensor.pop('config',None);sensor.pop('visible_when',None);sensor.pop('rules',None)
    chart=dict(kind='chart',text='Verlauf',entity_id=widget['entity_id'],x=24,y=120,width=432,height=168,size=16,color=color,config={'minutes':widget.get('config',{}).get('detail_minutes',60),'factor':widget.get('value',{}).get('factor',1)*(-1 if widget.get('value',{}).get('invert') else 1)})
    if 'unit' in widget.get('value',{}):chart['config']['unit']=widget['value']['unit']
    close=dict(kind='navigation',text='Schließen',entity_id='',target=page,x=368,y=8,width=104,height=32,size=16,color=color,style={'surface':True,'background':'#6750a4','radius':8})
    return {'background':'#fef7ff' if light else '#141218','theme':theme,'fullscreen':True,'widgets':[sensor,chart,close]}
