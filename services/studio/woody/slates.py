"""Normalize static camera slates; keep uploaded metadata and paths out of output."""
import base64
import binascii
import hashlib
from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from .controller import Rejected

MAX_UPLOAD = 4 * 1024 * 1024
WIDTH, HEIGHT = 1280, 720
Image.MAX_IMAGE_PIXELS = 16_000_000


def normalize_slate(data_url):
    header, separator, encoded = data_url.partition(',')
    if not separator or header not in ('data:image/png;base64', 'data:image/jpeg;base64', 'data:image/webp;base64'):
        raise Rejected('Kies een PNG-, JPG- of WebP-afbeelding van maximaal 4 MB')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise Rejected('De afbeelding kon niet worden gelezen') from None
    if not raw or len(raw) > MAX_UPLOAD:
        raise Rejected('De afbeelding mag maximaal 4 MB zijn')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw), formats=('PNG', 'JPEG', 'WEBP')) as source:
                if getattr(source, 'is_animated', False):
                    raise Rejected('Gebruik een stilstaande afbeelding')
                image = ImageOps.exif_transpose(source).convert('RGBA')
                fitted = ImageOps.contain(image, (WIDTH, HEIGHT), Image.Resampling.LANCZOS)
                canvas = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 255))
                canvas.alpha_composite(fitted, ((WIDTH - fitted.width) // 2, (HEIGHT - fitted.height) // 2))
                canvas = canvas.convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise Rejected('Gebruik een geldige afbeelding van maximaal 16 megapixels') from None
    preview = BytesIO()
    canvas.save(preview, format='JPEG', quality=90)
    jpeg = preview.getvalue()
    # Pillow YCbCr is full-range. GStreamer I420 uses studio-range luma/chroma.
    y, cb, cr = canvas.convert('YCbCr').split()
    luma = [round(16 + 219 * value / 255) for value in range(256)]
    chroma = [round(16 + 224 * value / 255) for value in range(256)]
    frame = y.point(luma).tobytes() + cb.resize((WIDTH // 2, HEIGHT // 2), Image.Resampling.BOX).point(chroma).tobytes() + cr.resize((WIDTH // 2, HEIGHT // 2), Image.Resampling.BOX).point(chroma).tobytes()
    return {'version': hashlib.sha256(jpeg).hexdigest(), 'image': jpeg, 'frame': frame}
