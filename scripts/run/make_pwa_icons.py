"""Tạo icon PWA + favicon riêng cho eApp FnB: logo eApp + nhãn "FnB" màu mint.

Icon phải khác các PWA eApp khác (POS, PM, Reader…) để người dùng không nhầm app đã cài.
Nhãn nằm trong vùng an toàn của icon maskable. Chạy từ thư mục gốc project (cần Pillow, macOS có font Arial Rounded Bold):
    python scripts/run/make_pwa_icons.py
"""
from PIL import Image, ImageDraw, ImageFont

SRC = 'static/images/logo/eapp.webp'
OUT = 'static/pwa/icons/fnb-icon-{s}x{s}.webp'
# Safari iOS chỉ nhận PNG cho apple-touch-icon nên riêng cỡ 180 xuất thêm bản PNG.
APPLE_TOUCH_PNG = 'static/pwa/icons/fnb-icon-180x180.png'
FONT = '/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf'
MINT = (16, 185, 129, 255)      # #10b981 = theme_color của FnB
WHITE = (255, 255, 255, 255)

base = Image.open(SRC).convert('RGBA').resize((1024, 1024), Image.LANCZOS)
draw = ImageDraw.Draw(base)
W = 1024
# Nhãn: rộng 52%, cao 20%, đáy ở 80% — góc nhãn cách tâm < 40% cạnh (vùng an toàn maskable).
pill_w, pill_h = int(W * 0.52), int(W * 0.20)
x0 = (W - pill_w) // 2
y1 = int(W * 0.80)
y0 = y1 - pill_h
draw.rounded_rectangle((x0, y0, x0 + pill_w, y1), radius=pill_h // 2, fill=MINT, outline=WHITE, width=int(W * 0.018))
font = ImageFont.truetype(FONT, int(pill_h * 0.66))
text = 'FnB'
l, t, r, b = draw.textbbox((0, 0), text, font=font)
draw.text(((W - (r - l)) / 2 - l, y0 + (pill_h - (b - t)) / 2 - t), text, font=font, fill=WHITE)

for size in (72, 96, 128, 144, 152, 180, 192, 384, 512):
    base.resize((size, size), Image.LANCZOS).save(OUT.format(s=size), 'WEBP', quality=95, method=6)
base.resize((180, 180), Image.LANCZOS).save(APPLE_TOUCH_PNG, optimize=True)

fav = base.resize((256, 256), Image.LANCZOS)
fav.save('static/pwa/icons/fnb-favicon.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
print('ok')
