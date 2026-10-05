"""Bounded region updates: RGB565 runs for graphics, raw bands for noisy images."""

import struct
from PIL import Image, ImageChops

WIDTH, HEIGHT, LIMIT = 480, 320, 65536


def encode_runs(data):
    output = bytearray()
    previous, count = None, 0
    for (pixel,) in struct.iter_unpack('<H', data):
        if pixel == previous and count < 65535:
            count += 1
        else:
            if count:
                output.extend(struct.pack('<HH', count, previous))
            previous, count = pixel, 1
    if count:
        output.extend(struct.pack('<HH', count, previous))
    return bytes(output)


def regions(frame, previous=None):
    if len(frame) != WIDTH * HEIGHT * 2:
        raise ValueError('Invalid frame length')
    x, y, right, bottom = 0, 0, WIDTH, HEIGHT
    if previous is not None:
        if len(previous) != len(frame):
            raise ValueError('Invalid previous frame length')
        # Treat each pixel's two bytes as channels; bbox is on exact RGB565 pixels.
        a = Image.frombytes('LA', (WIDTH, HEIGHT), frame)
        b = Image.frombytes('LA', (WIDTH, HEIGHT), previous)
        bounds = ImageChops.difference(a, b).getbbox(alpha_only=False)
        if bounds:
            x, y, right, bottom = bounds
        # Identical pixels can still have different touch actions: send a full frame
        # to establish the new revision rather than leave the old action map active.
    def encode_box(box):
        x,y,right,bottom=box
        width,height=right-x,bottom-y
        raw=b''.join(frame[(row*WIDTH+x)*2:(row*WIDTH+right)*2] for row in range(y,bottom))
        packed=encode_runs(raw)
        if len(packed)<=LIMIT and len(packed)<len(raw):
            return [(x,y,width,height,'rle',packed)]
        rows=LIMIT//(width*2)
        return [(x,row,width,min(rows,bottom-row),'raw',raw[(row-y)*width*2:(min(row+rows,bottom)-y)*width*2]) for row in range(y,bottom,rows)]
    whole=encode_box((x,y,right,bottom))
    if previous is None or not bounds:return whole
    # Coalesce neighbouring dirty tiles. Limit requests and include HTTP overhead
    # in the choice: sparse updates win only when they are actually cheaper.
    diff=ImageChops.difference(a,b)
    boxes=[]
    for top in range(0,HEIGHT,32):
        run=None
        for left in range(0,WIDTH+32,32):
            dirty=left<WIDTH and diff.crop((left,top,min(left+32,WIDTH),min(top+32,HEIGHT))).getbbox(alpha_only=False)
            if dirty and run is None:run=left
            if not dirty and run is not None:
                box=(run,top,min(left,WIDTH),min(top+32,HEIGHT))
                previous_box=next((i for i,b in enumerate(boxes) if b[0]==box[0] and b[2]==box[2] and b[3]==top),None)
                if previous_box is not None:
                    old=boxes[previous_box];boxes[previous_box]=(old[0],old[1],old[2],box[3])
                else:boxes.append(box)
                run=None
    if len(boxes)>24:return whole
    sparse=[update for box in boxes for update in encode_box(box)]
    cost=lambda updates:sum(len(update[-1])+700 for update in updates)
    return sparse if sparse and len(sparse)<=24 and cost(sparse)<cost(whole) else whole
