"""Đường dẫn file media theo tenant: ``media/tenant_{id}/<loại>/...``."""

from __future__ import annotations

import uuid


def tenant_dir(tenant_id) -> str:
    return f'tenant_{tenant_id}' if tenant_id else 'tenant_unknown'


def _safe_image_ext(filename: str, default: str = 'webp') -> str:
    ext = (filename.rsplit('.', 1)[-1] if '.' in filename else default).lower()[:8]
    if ext not in ('webp', 'png', 'jpg', 'jpeg', 'gif'):
        ext = default
    return ext


def product_image_file_upload_to(instance, filename: str) -> str:
    ext = _safe_image_ext(filename, 'webp')
    return f'{tenant_dir(instance.tenant_id)}/products/{uuid.uuid4().hex}.{ext}'


def product_image_thumbnail_upload_to(instance, filename: str) -> str:
    ext = _safe_image_ext(filename, 'webp')
    return f'{tenant_dir(instance.tenant_id)}/products/thumbs/{uuid.uuid4().hex}.{ext}'


def store_payment_qr_upload_to(instance, filename: str) -> str:
    ext = (filename.rsplit('.', 1)[-1] if '.' in filename else 'png').lower()[:8]
    if ext not in ('png', 'jpg', 'jpeg', 'webp', 'gif'):
        ext = 'png'
    return f'{tenant_dir(instance.tenant_id)}/store_payment_qr/qr_{uuid.uuid4().hex}.{ext}'
