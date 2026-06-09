# -*- coding: utf-8 -*-
"""测试 IPAD_AUTH_URL（正确的参数）"""
import requests
import re

ua = 'Mozilla/5.0 (iPad; CPU OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'

# iPad 企微 APP 扫码登录（正确的参数）
url = 'https://open.work.weixin.qq.com/wwopen/sso/3rd_qrConnect'
params = {
    'appid': 'wx782c26e4c19acffb',
    'redirect_uri': 'https://wx.work.weixin.qq.com/wwlogin/wwlogin.html',
    'fun': 'new',
    'lang': 'zh_CN',
    '_': '1234567890',  # 时间戳
    'state': 'test_state',
}

session = requests.Session()
resp = session.get(url, params=params, headers={'User-Agent': ua}, timeout=15, allow_redirects=True)
print(f'Final URL: {resp.url}')
print(f'Status: {resp.status_code}')
print(f'Content length: {len(resp.content)}')

# 检查页面 title
title_match = re.search(r'<title>([^<]+)</title>', resp.text)
if title_match:
    print(f'Page title: {title_match.group(1)}')

# 检查状态
status_match = re.search(r'"status"\s*:\s*"([^"]+)"', resp.text)
if status_match:
    print(f'Status: {status_match.group(1)}')

error_match = re.search(r'"errorMask"\s*:\s*"([^"]+)"', resp.text)
if error_match:
    print(f'Error: {error_match.group(1)}')

# 检查二维码 URL
patterns = [
    r'qrcodeUrl\s*[:=]\s*["\']([^"\']+)["\']',
    r'src=["\']([^"\']*qrcode[^"\']*)["\']',
]

for p in patterns:
    match = re.search(p, resp.text)
    if match:
        print(f'Found QR: {match.group(1)[:100]}')

# 保存页面
with open('d:/fh/debug/ipad_auth_correct.html', 'w', encoding='utf-8') as f:
    f.write(resp.text)
print('Page saved to debug/ipad_auth_correct.html')