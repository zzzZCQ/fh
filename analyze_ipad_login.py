# -*- coding: utf-8 -*-
"""分析iPad协议登录页面内容"""
import requests
import time
import re

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.0',
    'Referer': 'https://wx.work.weixin.qq.com/',
})

# 访问iPad协议登录页面
qr_url = f"https://open.work.weixin.qq.com/wwopen/sso/3rd_qrConnect?appid=wx782c26e4c19acffb&redirect_uri=https://wx.work.weixin.qq.com/wwlogin/wwlogin.html&fun=new&lang=zh_CN&_={int(time.time()*1000)}"

resp = session.get(qr_url, allow_redirects=True, timeout=15)
print(f'状态码: {resp.status_code}')
print(f'URL: {resp.url}')

# 保存页面内容
with open('ipad_login_page.html', 'w', encoding='utf-8') as f:
    f.write(resp.text)

print('\n页面内容已保存到 ipad_login_page.html')

# 搜索可能的二维码相关内容
print('\n=== 搜索二维码相关内容 ===')

# 搜索 qrcode
qrcode_patterns = ['qrcode', 'QRCode', 'qr_code', 'qrcodeUrl', 'qrUrl', 'img src']
for pattern in qrcode_patterns:
    matches = re.findall(rf'{pattern}[^\s"\'>]*["\'][^"\'>]+["\']', resp.text, re.IGNORECASE)
    if matches:
        print(f'{pattern}:')
        for m in matches[:3]:
            print(f'  {m}')

# 搜索 script 中的变量
script_pattern = re.compile(r'<script[^>]*>(.*?)</script>', re.DOTALL)
for script in script_pattern.findall(resp.text):
    if 'qrcode' in script.lower():
        print('\n包含qrcode的script:')
        print(script[:500] + '...')
        break
