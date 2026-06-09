# -*- coding: utf-8 -*-
"""分析真正的企业微信APP登录协议"""
import requests
import time
import re
import hashlib

session = requests.Session()

# 1. 模拟iPad微信客户端访问
headers = {
    'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.0',
    'Referer': 'https://wx.work.weixin.qq.com/',
}

# 访问企业微信登录页面
print('='*60)
print('分析企业微信APP登录协议')
print('='*60)

# 方式1: 访问 wx.work.weixin.qq.com 的登录页面
print('\n[1] 访问 wx.work.weixin.qq.com 登录页面')
resp = session.get('https://wx.work.weixin.qq.com/wwlogin/wwlogin.html', headers=headers, timeout=15)
print(f'状态: {resp.status_code}')
print(f'URL: {resp.url}')
print(f'内容长度: {len(resp.text)}')

# 保存页面内容分析
with open('wwlogin_page.html', 'w', encoding='utf-8') as f:
    f.write(resp.text)

# 方式2: 尝试获取二维码
print('\n[2] 尝试获取APP登录二维码')

# 访问授权页面
auth_url = 'https://open.work.weixin.qq.com/wwopen/sso/3rd_qrConnect?appid=wx782c26e4c19acffb&redirect_uri=https://wx.work.weixin.qq.com/wwlogin/wwlogin.html&fun=new&lang=zh_CN&_=' + str(int(time.time()*1000))
resp2 = session.get(auth_url, headers=headers, timeout=15, allow_redirects=True)
print(f'授权页面状态: {resp2.status_code}')
print(f'最终URL: {resp2.url}')

# 搜索二维码相关内容
content = resp2.text
patterns = [
    r'qrcode[Uu]rl\s*[:=]\s*["\']([^"\']+)["\']',
    r'<img[^>]+src=["\']([^"\']*qrcode[^"\']*)["\']',
    r'["\']?(https?://[^"\'\s]+qrcode[^"\'\s]*)["\']?',
    r'base64,[A-Za-z0-9+/=]+',
]

for p in patterns:
    matches = re.findall(p, content)
    if matches:
        print(f'\n找到匹配 ({p}):')
        for m in matches[:3]:
            print(f'  {m[:100]}')

# 方式3: 直接尝试企业微信APP的API
print('\n[3] 尝试企业微信APP的API')
app_urls = [
    'https://wx.work.weixin.qq.com/wwlogin/wwlogin/qrcode',
    'https://qyapi.weixin.qq.com/cgi/login?type=wwclient',
]

for url in app_urls:
    try:
        resp = session.get(url, headers=headers, timeout=10)
        print(f'{url}: {resp.status_code}')
        if resp.content[:4] == b'\x89PNG':
            print('  -> 这是一个PNG图片!')
    except Exception as e:
        print(f'{url}: 错误 - {e}')

print('\n分析完成!')
