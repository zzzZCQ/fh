# -*- coding: utf-8 -*-
import requests
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

session = requests.Session()
resp = session.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers=headers, timeout=15)
print('status:', resp.status_code)
print('final url:', resp.url)
print()
print('=== Cookies ===')
for c in resp.cookies:
    print(f'  {c.name} = {c.value[:100]}')

html = resp.text
print()
print('=== 查找 wwqrlogin 相关字符串 ===')
for m in re.finditer(r'wwqrlogin', html):
    start = max(0, m.start() - 80)
    end = min(len(html), m.end() + 200)
    print(f'  pos={m.start()}: {html[start:end]}')
    print()

print('=== 查找 JSON 中的配置（window\.xxx|window\[|config|DATA） ===')
for kw in ['window.', 'login_qrcode', 'login_qr', 'qrcodeUrl', 'qrUrl', 'QRCODE']:
    matches = list(re.finditer(re.escape(kw) if '\\' in kw or '.' in kw else kw, html, re.IGNORECASE))
    if matches:
        print(f'[{kw}]: {len(matches)} 处')
        for m in matches[:3]:
            start = max(0, m.start() - 30)
            end = min(len(html), m.end() + 100)
            print(f'  pos={m.start()}: {html[start:end]}')
        print()

# 保存完整HTML
with open('wecom_login_page.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f'\n已保存完整HTML: {len(html)} chars')
