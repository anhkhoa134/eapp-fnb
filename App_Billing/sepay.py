"""SePay: QR chuyển khoản + webhook "tiền vào" cho yêu cầu gói dịch vụ.

Dùng chung một tài khoản SePay với ecom_final (một tài khoản ngân hàng nhận tiền của eApp).
SePay gửi MỌI giao dịch tiền vào của tài khoản đó tới từng webhook, nên mỗi app chỉ nhận
giao dịch có mã tham chiếu đúng tiền tố của mình (BILLING_REFERENCE_PREFIX) và bỏ qua phần còn lại.

Chỉ bật khi đủ SEPAY_WEBHOOK_HMAC_SECRET, SEPAY_BANK_ACCOUNT, SEPAY_BANK_CODE (xem settings).
File giống hệt nhau ở POS, FnB, PM, Photo (App_Billing/sepay.py) và ERP (App_Platform/sepay.py) — sửa ở một app thì đồng bộ sang các app còn lại.
"""
import hashlib
import hmac
import re
import time
from urllib.parse import urlencode

from django.conf import settings

PROVIDER = 'sepay'
REPLAY_TOLERANCE_SECONDS = 300
# VietinBank (TK cá nhân) chỉ đồng bộ giao dịch có nội dung bắt đầu bằng SEVQR; giữ cho mọi ngân hàng.
CONTENT_PREFIX = 'SEVQR'


def enabled():
    return PROVIDER in getattr(settings, 'BILLING_PAYMENT_PROVIDERS', ())


def transfer_content(reference):
    return f'{CONTENT_PREFIX} {reference}'


def payment_info(item):
    """Thông tin chuyển khoản cho yêu cầu đang chờ, có giá niêm yết > 0; None nếu không áp dụng."""
    if not enabled() or item.status != 'pending' or not item.amount_vnd:
        return None
    content = transfer_content(item.reference)
    query = urlencode({
        'acc': settings.SEPAY_BANK_ACCOUNT, 'bank': settings.SEPAY_BANK_CODE,
        'amount': item.amount_vnd, 'des': content, 'template': 'compact',
    })
    return {
        'qr_url': f'https://qr.sepay.vn/img?{query}',
        'content': content,
        'amount_vnd': item.amount_vnd,
        'bank': settings.SEPAY_BANK_CODE,
        'account': settings.SEPAY_BANK_ACCOUNT,
        'holder': getattr(settings, 'SEPAY_ACCOUNT_HOLDER', ''),
    }


def verify_signature(request):
    """HMAC-SHA256 của SePay: header X-SePay-Signature = "sha256=<hex>" ký trên "{timestamp}.{raw_body}".

    Trả về (ok, reason); reason chỉ để ghi log.
    """
    secret = getattr(settings, 'SEPAY_WEBHOOK_HMAC_SECRET', '')
    if not secret:
        return False, 'missing_server_secret'
    signature = request.headers.get('X-SePay-Signature', '')
    timestamp = request.headers.get('X-SePay-Timestamp', '')
    if not signature.startswith('sha256=') or not timestamp:
        return False, 'missing_signature_headers'
    try:
        sent_at = int(timestamp)
    except ValueError:
        return False, 'invalid_timestamp'
    if abs(time.time() - sent_at) > REPLAY_TOLERANCE_SECONDS:
        return False, 'stale_timestamp'
    expected = hmac.new(secret.encode(), f'{timestamp}.'.encode() + request.body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(f'sha256={expected}', signature):
        return False, 'signature_mismatch'
    return True, 'ok'


def _digits(value):
    return re.sub(r'\D', '', str(value or ''))


def find_reference(payload):
    """Mã yêu cầu của app này trong nội dung CK. Ngân hàng hay bỏ/thêm khoảng trắng nên so trên chuỗi đã bỏ ký tự lạ."""
    prefix = settings.BILLING_REFERENCE_PREFIX.upper()
    haystack = re.sub(r'[^0-9A-Z]', '', f"{payload.get('code') or ''} {payload.get('content') or ''}".upper())
    match = re.search(rf'{re.escape(prefix)}([0-9A-F]{{16}})', haystack)
    return f'{prefix}{match.group(1)}' if match else None


def parse_event(payload):
    """Kiểm tra chiều tiền, tài khoản nhận, số tiền, mã giao dịch. Trả về (event | None, reason)."""
    if not isinstance(payload, dict):
        return None, 'invalid_payload'
    reference = find_reference(payload)
    if reference is None:
        return None, 'not_this_app'
    if str(payload.get('transferType', '')).lower() != 'in':
        return None, 'not_money_in'
    receivers = {_digits(payload.get('accountNumber')), _digits(payload.get('subAccount'))} - {''}
    if _digits(settings.SEPAY_BANK_ACCOUNT) not in receivers:
        return None, 'wrong_receiver_account'
    transaction_id = str(payload.get('id') or '').strip()
    if not transaction_id:
        return None, 'missing_transaction_id'
    amount = payload.get('transferAmount')
    if isinstance(amount, bool):
        return None, 'invalid_amount'
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return None, 'invalid_amount'
    if amount <= 0:
        return None, 'invalid_amount'
    return {'reference': reference, 'transaction_id': transaction_id, 'amount_vnd': amount}, 'ok'
