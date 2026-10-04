"""Bounded uploaded raster images, fitted without network access."""
import base64
from functools import lru_cache
from io import BytesIO
from PIL import Image, ImageOps

MAX_IMAGE_BYTES = 100_000


def image_bytes(source):
    if not isinstance(source, str) or len(source) > 134_000:
        raise ValueError('Bild: maximal 100 KB')
    header, separator, data = source.partition(',')
    if not separator or header not in ('data:image/png;base64','data:image/jpeg;base64','data:image/webp;base64'):
        raise ValueError('Bitte ein PNG-, JPEG- oder WebP-Bild hochladen')
    try:
        decoded = base64.b64decode(data, validate=True)
        if len(decoded) > MAX_IMAGE_BYTES:
            raise ValueError('Bild: maximal 100 KB')
        with Image.open(BytesIO(decoded)) as image:
            if image.format not in ('PNG', 'JPEG', 'WEBP') or image.width*image.height > 480*320:
                raise ValueError('Bild: maximal 480 x 320 Pixel')
            image.load()
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError('Bild konnte nicht gelesen werden') from error
    return decoded


@lru_cache(maxsize=16)
def picture_tile(source, width, height, fit):
    with Image.open(BytesIO(image_bytes(source))) as image:
        image = image.convert('RGBA')
        if fit == 'cover':
            return ImageOps.fit(image, (width,height), method=Image.Resampling.LANCZOS)
        picture = ImageOps.contain(image, (width,height), method=Image.Resampling.LANCZOS)
        tile = Image.new('RGBA', (width,height))
        tile.paste(picture, ((width-picture.width)//2,(height-picture.height)//2))
        return tile
