# -*- coding: utf-8 -*-
import requests
import re
import base64

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

session = requests.Session()

# 1. 访问登录页获取cookie
resp = session.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers=headers, timeout=15)
print('cookies:', list(session.cookies))

# 2. 请求 login_qrcode
qr_url = 'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/login_qrcode?login_type=login_admin'
h2 = dict(headers)
h2['Referer'] = 'https://work.weixin.qq.com/wework_admin/loginpage_wx'
resp2 = session.get(qr_url, headers=h2, timeout=15)
print(f'status: {resp2.status_code}')
print(f'Content-Type: {resp2.headers.get("Content-Type", "")}')
print(f'content length: {len(resp2.content)}')

# 保存并分析
with open('qr_page.html', 'w', encoding='utf-8') as f:
    f.write(resp2.text)
print('\n=== 内容 (全文) ===')
print(resp2.text)
print()

# 分析: 查找 <img> <canvas> 或其他二维码元素
print('=== 查找关键元素 ===')
# 查找 img
imgs = re.findall(r'<img[^>]+>', resp2.text, re.IGNORECASE)
for img in imgs:
    print(f'  IMG: {img[:200]}')

# 查找 canvas
canvases = re.findall(r'<canvas[^>]*>', resp2.text, re.IGNORECASE)
for c in canvases:
    print(f'  CANVAS: {c[:200]}')

# 查找 src / data-url
srcs = re.findall(r'(?:src|href)\s*=\s*["\']([^"\']{10,})["\']', resp2.text)
for src in srcs:
    print(f'  SRC/HREF: {src[:200]}')
    # 如果是图片，尝试获取
    if src.startswith('//'):
        img_url = 'https:' + src
    elif src.startswith('http'):
        img_url = src
    elif src.startswith('data:'):
        print(f'    => data-url, length={len(src)}')
        continue
    else:
        continue
    try:
        resp3 = session.get(img_url, headers=h2, timeout=15)
        ctype = resp3.headers.get('Content-Type', '')
        if 'image' in ctype.lower():
            fname = f'qr_extracted_{abs(hash(img_url))}.png'
            with open(fname, 'wb') as f:
                f.write(resp3.content)
            print(f'    => 成功保存 {fname}, size={len(resp3.content)} bytes')
    except Exception as e:
        print(f'    => 获取失败: {e}')

print()
# 查找所有 script
scripts = re.findall(r'<script[^>]*>(.*?)</script>', resp2.text, re.DOTALL | re.IGNORECASE)
for i, s in enumerate(scripts):
    if len(s) > 30:
        print(f'SCRIPT[{i}] ({len(s)} chars): {s[:300]}')
        print()
