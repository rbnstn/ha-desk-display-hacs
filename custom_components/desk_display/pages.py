"""Small page sets, selected in HA; firmware only sees the current frame."""
import copy

def page_layout(layout,index=0):
    pages=[layout]+layout.get('pages',[])
    index=max(0,min(len(pages)-1,index))
    page=copy.deepcopy(pages[index])
    for key in ('pages','page_name','rotation','page_rules'):page.pop(key,None)
    page['debug']=layout.get('debug',False)
    if 'design' in layout:page['design']=copy.deepcopy(layout['design'])
    page.pop('device',None)
    if len(pages)>1 and layout.get('navigation',True):
        for i,item in enumerate(pages):
            left=i*480//len(pages);right=(i+1)*480//len(pages)
            page['widgets'].append(dict(kind='navigation',text=item.get('page_name',f'Seite {i+1}'),entity_id='',x=left,y=276,width=right-left,height=44,size=12,color='#ffffff' if i==index else '#94a3b8',target=i,style={'surface':True,'background':'#6750a4' if i==index else '#24212b','radius':0,'align':'center'}))
    return page

def all_widgets(layout):
    return layout['widgets']+[w for p in layout.get('pages',[]) for w in p['widgets']]+layout.get('overlay',{}).get('widgets',[])

