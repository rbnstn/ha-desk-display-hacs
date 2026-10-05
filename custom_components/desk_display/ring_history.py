"""Opt-in, per-display ringing history. Pictures never leave local HA storage."""
import asyncio
from datetime import datetime,timezone,timedelta
from io import BytesIO
import base64
from PIL import Image,ImageDraw,ImageFont

def trim(records,days,now=None):
    cutoff=(now or datetime.now(timezone.utc))-timedelta(days=days)
    result=[]
    for item in records:
        try:
            if isinstance(item,dict) and datetime.fromisoformat(item['at'])>=cutoff:result.append(item)
        except (KeyError,TypeError,ValueError):continue
    return result[:20]

def thumbnail(frame,width,height):
    image=Image.frombytes('RGB',(width,height),frame);image.thumbnail((96,64));output=BytesIO();image.save(output,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(output.getvalue()).decode()

class RingHistory:
    def __init__(self,hass,key):
        self.hass=hass;self.key=key;self.records=[];self.store=None;self.lock=asyncio.Lock();self.loaded=False;self.enabled=False;self.days=7
    def storage(self):
        if self.store is None:
            from homeassistant.helpers.storage import Store
            self.store=Store(self.hass,1,'desk_display_ring_history_'+self.key)
        return self.store
    async def configure(self,config):
        async with self.lock:
            enabled=config.get('history_enabled',False);self.days=config.get('history_days',7)
            if enabled and not self.loaded:
                data=await self.storage().async_load();self.records=trim((data or {}).get('records',[]),self.days);self.loaded=True
            if not enabled:
                self.records=[]
                if self.enabled:await self.storage().async_save({'records':[]})
            elif not config.get('history_images',False):
                self.records=[{'at':r['at']} for r in self.records]
            self.enabled=enabled
            if enabled:await self.storage().async_save({'records':trim(self.records,self.days)})
    async def record(self,config,frame=None):
        if not config.get('history_enabled',False):return
        if not self.enabled:await self.configure(config)
        async with self.lock:
            if not self.enabled:return
            record={'at':datetime.now(timezone.utc).isoformat()}
            if config.get('history_images',False) and frame:
                data,width,height=frame
                record['image']=await self.hass.async_add_executor_job(thumbnail,data,width,height)
            self.records=trim([record,*self.records],self.days)
            await self.storage().async_save({'records':self.records})
    async def expire(self):
        async with self.lock:
            current=trim(self.records,self.days)
            if current!=self.records:
                self.records=current
                if self.enabled:await self.storage().async_save({'records':current})
    async def clear(self):
        async with self.lock:
            self.records=[];await self.storage().async_save({'records':[]})
    def snapshot(self,zone='UTC'):
        from zoneinfo import ZoneInfo
        self.records=trim(self.records,self.days)
        return [{**r,'label':datetime.fromisoformat(r['at']).astimezone(ZoneInfo(zone)).strftime('%d.%m. %H:%M:%S')} for r in self.records]

def tile(widget,states,theme):
    image=Image.new('RGBA',(widget['width'],widget['height']));draw=ImageDraw.Draw(image);color=widget['color'];font=ImageFont.load_default(size=12)
    draw.text((6,4),widget['text'],font=font,fill=color)
    records=states.get('__ring_history__',[])
    if not records:draw.text((6,28),'Kein Klingelverlauf',font=font,fill=color)
    for i,record in enumerate(records[:4]):
        y=24+i*48
        if y>=widget['height']:break
        left=6
        if record.get('image'):
            from .pictures import picture_tile
            picture=picture_tile(record['image'],64,42,'contain');image.alpha_composite(picture,(6,y));left=76
        draw.text((left,y+10),record.get('label',record['at'])[:40],font=font,fill=color)
    return image

