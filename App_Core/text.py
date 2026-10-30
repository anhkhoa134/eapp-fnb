import unicodedata


def fold_vietnamese(text) -> str:
    """Bỏ dấu tiếng Việt + chữ thường để tìm kiếm không dấu: "Cà Phê Đá" -> "ca phe da"."""
    value = str(text or '').replace('đ', 'd').replace('Đ', 'D')
    value = unicodedata.normalize('NFD', value)
    value = ''.join(ch for ch in value if unicodedata.category(ch) != 'Mn')
    return ' '.join(value.lower().split())
