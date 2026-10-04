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
    width, height = right-x, bottom-y
    raw = b''.join(frame[(row*WIDTH+x)*2:(row*WIDTH+right)*2] for row in range(y,bottom))
    packed = encode_runs(raw)
    if len(packed) <= LIMIT and len(packed) < len(raw):
        return [(x,y,width,height,'rle',packed)]
    rows_per_band = LIMIT // (width * 2)
    return [(x,row,width,min(rows_per_band,bottom-row),'raw',
             raw[(row-y)*width*2:(min(row+rows_per_band,bottom)-y)*width*2])
            for row in range(y,bottom,rows_per_band)]
