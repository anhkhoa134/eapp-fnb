from django import template

register = template.Library()


@register.filter
def audit_headline(message):
    """'Sửa sản phẩm "Phở": Giá: 30.000 → 35.000' -> 'Sửa sản phẩm "Phở"'.

    Dùng khi dòng nhật ký đã có danh sách thay đổi bên dưới, tránh in chi tiết 2 lần.
    """
    text = str(message or '')
    head, sep, _rest = text.partition('": ')
    return f'{head}"' if sep else text
