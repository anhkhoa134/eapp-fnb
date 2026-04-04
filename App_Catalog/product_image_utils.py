"""Convert uploaded product images to WebP + smaller thumbnail for bandwidth."""
from __future__ import annotations

import uuid
from io import BytesIO

from django.core.files.base import ContentFile

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_MAIN_SIDE = 1400
MAX_THUMB_SIDE = 420
WEBP_QUALITY_MAIN = 82
WEBP_QUALITY_THUMB = 78


def _delete_stored_image(fieldfile) -> None:
    if fieldfile and getattr(fieldfile, 'name', None):
        fieldfile.delete(save=False)


def _image_to_webp_bytes(im, max_side: int, quality: int) -> bytes:
    from PIL import Image, ImageOps

    im = ImageOps.exif_transpose(im)
    if im.mode not in ('RGB', 'RGBA'):
        im = im.convert('RGBA')
    im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buf = BytesIO()
    im.save(buf, format='WEBP', quality=quality, method=6)
    return buf.getvalue()


def build_webp_pair_from_upload(uploaded_file) -> tuple[bytes, bytes]:
    from PIL import Image

    uploaded_file.seek(0)
    im = Image.open(uploaded_file)
    main_bytes = _image_to_webp_bytes(im.copy(), MAX_MAIN_SIDE, WEBP_QUALITY_MAIN)
    uploaded_file.seek(0)
    im2 = Image.open(uploaded_file)
    thumb_bytes = _image_to_webp_bytes(im2, MAX_THUMB_SIDE, WEBP_QUALITY_THUMB)
    return main_bytes, thumb_bytes


def apply_product_image_upload(instance, uploaded_file) -> None:
    """Attach WebP main + thumbnail to `instance` (save not called). Replaces existing files."""
    from App_Catalog.models import Product

    if not isinstance(instance, Product):
        raise TypeError('instance must be Product')

    tenant_id = instance.tenant_id
    if not tenant_id:
        raise ValueError('Product must have tenant_id set before saving upload')

    if instance.pk:
        _delete_stored_image(instance.image_file)
        _delete_stored_image(instance.image_thumbnail)

    main_bytes, thumb_bytes = build_webp_pair_from_upload(uploaded_file)
    base = uuid.uuid4().hex
    rel_main = f'products/t{tenant_id}/{base}.webp'
    rel_thumb = f'products/t{tenant_id}/thumbs/{base}.webp'

    instance.image_file.save(rel_main, ContentFile(main_bytes), save=False)
    instance.image_thumbnail.save(rel_thumb, ContentFile(thumb_bytes), save=False)
