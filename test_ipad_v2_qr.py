# -*- coding: utf-8 -*-
"""测试真正的iPad协议 v2"""
import time
from wecom_ipad_protocol_v2 import WeComIPadProtocolV2

print('='*60)
print('测试 WeComIPadProtocolV2 (真正的iPad企微APP协议)')
print('='*60)

protocol = WeComIPadProtocolV2()

# 1. 获取授权URL
print('[1] 获取授权URL...')
auth_url = protocol._get_authorization_url()
print(f'  URL: {auth_url}')

# 2. 直接获取二维码
print('\n[2] 直接获取二维码图片...')
import requests

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.0',
    'Referer': 'https://wx.work.weixin.qq.com/',
})

# 使用iPad协议的二维码接口
qr_url = f"https://open.work.weixin.qq.com/wwopen/sso/3rd_qrConnect?appid=wx782c26e4c19acffb&redirect_uri=https://wx.work.weixin.qq.com/wwlogin/wwlogin.html&fun=new&lang=zh_CN&_={int(time.time()*1000)}"

try:
    # 获取二维码页面
    resp = session.get(qr_url, allow_redirects=True, timeout=15)
    print(f'  访问状态: {resp.status_code}')
    
    # 查找二维码图片URL
    import re
    match = re.search(r'qrcodeUrl\s*[:=]\s*["\']([^"\']+)["\']', resp.text)
    if match:
        qr_img_url = match.group(1)
        print(f'  二维码图片URL: {qr_img_url}')
        
        # 获取二维码图片
        resp_img = session.get(qr_img_url, timeout=15)
        if resp_img.content[:4] == b'\x89PNG':
            fname = 'ipad_app_qrcode.png'
            with open(fname, 'wb') as f:
                f.write(resp_img.content)
            print(f'  ✅ 已保存二维码: {fname} ({len(resp_img.content)} bytes)')
        else:
            print(f'  ❌ 获取二维码失败')
    else:
        print('  ❌ 未找到二维码URL')
    
except Exception as e:
    print(f'  ❌ 错误: {e}')

print('\n=== 总结 ===')
print('iPad协议V2使用的是 wx.work.weixin.qq.com 端点')
print('redirect_uri 指向 wx.work.weixin.qq.com/wwlogin/wwlogin.html')
print('这才是iPad企微APP的真实协议！')
