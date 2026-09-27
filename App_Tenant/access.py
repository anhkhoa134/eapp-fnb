"""Kiểm tra doanh nghiệp còn được phép dùng POS / trang quản lý hay không (BL-001)."""

BLOCK_TENANT_INACTIVE = 'tenant_inactive'
BLOCK_SUBSCRIPTION_EXPIRED = 'subscription_expired'

# Hiện cảnh báo trên /quanly/ khi gói còn <= số ngày này.
SUBSCRIPTION_WARNING_DAYS = 7

TENANT_INACTIVE_MESSAGE = 'Doanh nghiệp đã ngừng hoạt động. Vui lòng liên hệ quản trị hệ thống.'
SUBSCRIPTION_EXPIRED_MESSAGE = 'Gói dịch vụ đã hết hạn. Vui lòng gia hạn để tiếp tục bán hàng và cập nhật dữ liệu.'
SUBSCRIPTION_EXPIRED_STAFF_MESSAGE = 'Gói dịch vụ của cửa hàng đã hết hạn. Vui lòng liên hệ quản lý để gia hạn.'


def tenant_block_reason(tenant, today=None):
    """Trả về lý do chặn (BLOCK_*) hoặc None nếu doanh nghiệp đang dùng bình thường."""
    if tenant is None:
        return None
    if not tenant.is_active:
        return BLOCK_TENANT_INACTIVE
    if tenant.is_subscription_expired(today):
        return BLOCK_SUBSCRIPTION_EXPIRED
    return None


def subscription_notice(tenant, today=None):
    """Thông tin cho banner trên /quanly/: gói đã hết hạn hoặc sắp hết hạn. None = không cần hiện."""
    if tenant is None:
        return None
    days_left = tenant.subscription_days_left(today)
    if days_left is None or days_left > SUBSCRIPTION_WARNING_DAYS:
        return None
    return {
        'expired': days_left < 0,
        'days_left': days_left,
        'ends_on': tenant.subscription_ends_on,
    }
