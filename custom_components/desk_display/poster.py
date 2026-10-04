"""Resize a bounded HA camera image outside the event loop."""
from io import BytesIO
from PIL import Image, ImageOps


def camera_tile(content, width, height):
    if not isinstance(content,bytes) or not 0<len(content)<=8*1024*1024:
        raise ValueError('Invalid camera image')
    with Image.open(BytesIO(content)) as image:
        if image.width*image.height>20_000_000:
            raise ValueError('Camera image too large')
        fitted=ImageOps.contain(image.convert('RGB'),(width,height))
    tile=Image.new('RGB',(width,height),'black')
    tile.paste(fitted,((width-fitted.width)//2,(height-fitted.height)//2))
    return tile.tobytes()
