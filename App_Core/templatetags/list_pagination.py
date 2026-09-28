from django import template

register = template.Library()


@register.filter
def elided_pages(page_obj):
    """Dãy số trang rút gọn quanh trang hiện tại, ví dụ [1, '…', 4, 5, 6, '…', 12]."""
    return page_obj.paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
