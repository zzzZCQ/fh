# -*- coding: utf-8 -*-
"""
测试企业微信 iPad APP 客户端的真实登录协议
域名: wx.work.weixin.qq.com
路径: /wwlogin/wwlogin/...
"""
import requests
import time
import base64
import json
import random
import hashlib
import re

# 模拟企微iPad客户端的请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.0',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Content-Type': 'application/json;charset=UTF-8',
    'Origin': 'https://work.weixin.qq.com',
    'Referer': 'https://work.weixin.qq.com/',
}

session = requests.Session()

def gen_device_id():
    return 'e' + hashlib.md5(str(time.time()).encode()).hexdigest()[:15]

def test_endpoint(url, method='GET', params=None, data=None, headers=None, desc=''):
    print(f'\n[{desc}]')
    print(f'  URL: {url[:120]}')
    try:
        h = dict(HEADERS)
        if headers:
            h.update(headers)
        if method == 'GET':
            resp = session.get(url, params=params, headers=h, timeout=15)
        else:
            resp = session.post(url, params=params, json=data, headers=h, timeout=15)
        print(f'  Status: {resp.status_code}')
        print(f'  Content-Type: {resp.headers.get("Content-Type", "")}')
        ctype = resp.headers.get('Content-Type', '')
        if 'image' in ctype.lower():
            print(f'  Content-Size: {len(resp.content)} bytes')
            # 保存
            fname = f'ipadsdk_qr_{abs(hash(url))}.png'
            with open(fname, 'wb') as f:
                f.write(resp.content)
            print(f'  => 保存为: {fname}')
        else:
            # 文本响应
            txt = resp.text
            if len(txt) > 1500:
                txt = txt[:1500] + '...[截断]'
            print(f'  Body: {txt}')
        print(f'  Set-Cookie: {[c.name for c in session.cookies][-5:]}')
        return resp
    except Exception as e:
        print(f'  Error: {e}')
        return None

print('='*70)
print('企微iPad客户端登录协议测试')
print('='*70)

# 先访问企微客户端登录主页面
test_endpoint(
    'https://wx.work.weixin.qq.com/wwlogin/wwlogin.html',
    'GET',
    desc='1. 访问企微客户端登录主页面'
)

# 测试各类二维码/登录相关接口
test_cases = [
    # 客户端登录获取二维码
    ('https://wx.work.weixin.qq.com/wwlogin/wwlogin/qrcode', 'POST', None,
     {'login_type': 'wwclient'}, '', '2. POST qrcode 接口'),
    ('https://wx.work.weixin.qq.com/wwlogin/wwlogin/qrcode', 'GET',
     {'login_type': 'wwclient', 't': str(int(time.time()*1000))}, None, '', '3. GET qrcode 接口'),
    # 获取登录ticket / key
    ('https://wx.work.weixin.qq.com/wwlogin/wwlogin/login', 'GET',
     {'login_type': 'wwclient', 't': str(int(time.time()*1000))}, None, '', '4. GET login 接口'),
    # 检查登录状态
    ('https://wx.work.weixin.qq.com/wwlogin/wwlogin/checklogin', 'GET',
     {'login_type': 'wwclient', 't': str(int(time.time()*1000))}, None, '', '5. GET checklogin 接口'),
]

for url, method, params, data, hdrs, desc in test_cases:
    test_endpoint(url, method, params, data, hdrs, desc)

# 也测试开放平台的第三方登录接口（返回真正可扫的二维码）
print('\n' + '='*70)
print('测试开放平台第三方登录接口（可能返回真实二维码）')
print('='*70)

test_cases_open = [
    ('https://open.work.weixin.qq.com/wwopen/sso/3rd_qrConnect?appid=wx782c26e4c19acffb&redirect_uri=https%3A%2F%2Fwork.weixin.qq.com%2Fwework_admin%2Floginpage_wx&state=STATE&lang=zh_CN&lang=zh_CN#wechat_redirect',
     'GET', None, None, '', '6. 开放平台3rd_qrConnect'),
]
for url, method, params, data, hdrs, desc in test_cases_open:
    test_endpoint(url, method, params, data, hdrs, desc)
