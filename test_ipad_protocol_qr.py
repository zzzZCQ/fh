# -*- coding: utf-8 -*-
"""测试 wecom_ipad_protocol.py 获取的二维码类型"""
from wecom_ipad_protocol import WeComIPadProtocol

protocol = WeComIPadProtocol()

print('='*60)
print('测试 WeComIPadProtocol 获取二维码')
print('='*60)

# 1. 获取ticket
print('[1] 获取 login_ticket...')
ticket = protocol.get_login_ticket()
print(f'  ticket: {ticket[:20] if ticket else "None"}')

# 2. 获取二维码URL
print('\n[2] 获取二维码URL...')
qr_url = protocol.get_qrcode_url()
print(f'  URL: {qr_url}')

# 3. 尝试获取二维码图片
print('\n[3] 尝试生成二维码图片...')
try:
    qr_file = protocol.generate_qrcode_image()
    print(f'  二维码文件: {qr_file}')
except Exception as e:
    print(f'  生成失败: {e}')

# 4. 测试直接用 requests 获取
print('\n[4] 直接测试iPad协议的二维码获取...')
import requests
import os

headers = {
    'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
    'Accept': '*/*',
    'Referer': 'https://work.weixin.qq.com/',
}

session = requests.Session()
session.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers=headers, timeout=15)

# 测试不同 login_type
for lt in ['wwclient', 'login_admin']:
    resp = session.get(
        'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode',
        headers=headers, params={'login_type': lt}, timeout=15
    )
    if resp.content[:4] == b'\x89PNG':
        fname = f'ipad_{lt}.png'
        with open(fname, 'wb') as f:
            f.write(resp.content)
        print(f'  login_type={lt}: {len(resp.content)} bytes -> {fname}')
    else:
        print(f'  login_type={lt}: 失败')

print('\n=== 分析 ===')
print('iPad协议获取的二维码仍然是 work.weixin.qq.com 的管理后台二维码')
print('这是因为 iPad版企业微信APP 就是通过这个接口获取登录二维码的')
print('扫码后用户确认的是登录管理后台，而不是登录APP客户端')
