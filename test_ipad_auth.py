# -*- coding: utf-8 -*-
"""测试 IPAD_AUTH_URL 返回内容"""
import requests
import re

ua = 'Mozilla/5.0 (iPad; CPU OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'

# 企微开放平台扫码登录
url = 'https://open.work.weixin.qq.com/wwopen/sso/3rd_qrConnect'
params = {
    'appid': 'wx782c26e4c19acffb',
    'redirect_uri': 'https://wx.work.weixin.qq.com',
    'response_type': 'code',
    'scope': 'snsapi_userinfo',
    'state': 'test',
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

# 检查是否有二维码 URL
patterns = [
    r'qrcodeUrl\s*[:=]\s*["\']([^"\']+)["\']',
    r'<img[^>]*src=["\']([^"\']*qrcode[^"\']*)["\']',
    r'url\s*[:=]\s*["\']([^"\']*login[^"\']*)["\']',
]

for p in patterns:
    match = re.search(p, resp.text)
    if match:
        print(f'Pattern {p[:30]}... matched: {match.group(1)[:100]}')

# 检查重定向
if 'wx.work.weixin.qq.com' in resp.url:
    print('Redirected to wx.work.weixin.qq.com')
elif 'work.weixin.qq.com' in resp.url:
    print('Redirected to work.weixin.qq.com')
elif 'open.work.weixin.qq.com' in resp.url:
    print('Stayed at open.work.weixin.qq.com')

# 保存页面内容用于分析
with open('d:/fh/debug/ipad_auth_page.html', 'w', encoding='utf-8') as f:
    f.write(resp.text)
print('Page saved to debug/ipad_auth_page.html')