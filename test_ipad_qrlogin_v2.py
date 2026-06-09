# -*- coding: utf-8 -*-
"""
测试企业微信真实的登录二维码接口
企微客户端登录的真正路径:
- work.weixin.qq.com/wework_admin/wwlogin/mng/qrcode
- work.weixin.qq.com/wework_admin/wwlogin/login
- 或开放平台 web.weixin.qq.com 系列
"""
import requests
import time
import json
import hashlib

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://work.weixin.qq.com/',
}

session = requests.Session()

def test(url, method='GET', params=None, data=None, desc=''):
    print(f'\n[{desc}]')
    print(f'  {method} {url[:140]}')
    if params:
        print(f'  params: {params}')
    try:
        h = dict(HEADERS)
        if method == 'POST':
            h['Content-Type'] = 'application/json'
        if method == 'GET':
            resp = session.get(url, params=params, headers=h, timeout=15)
        else:
            resp = session.post(url, params=params, json=data, headers=h, timeout=15)
        print(f'  Status: {resp.status_code}, Size: {len(resp.content)}')
        ctype = resp.headers.get('Content-Type', '')
        print(f'  Content-Type: {ctype}')
        # 是否是图片
        if 'image' in ctype.lower() or resp.content[:4] in (b'\x89PNG', b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1'):
            fname = f'test_qr_{abs(hash(url+str(params)))}.png'
            with open(fname, 'wb') as f:
                f.write(resp.content)
            print(f'  => 图片! 已保存为 {fname} ({len(resp.content)} bytes)')
        else:
            txt = resp.text
            if len(txt) > 800:
                txt = txt[:800] + '...[截断]'
            print(f'  Body: {txt}')
        print(f'  Cookies: {[c.name for c in session.cookies]}')
        return resp
    except Exception as e:
        print(f'  Error: {e}')
        return None

print('='*70)
print('测试企业微信各种登录二维码接口')
print('='*70)

# 1. 先访问主登录页面获取 cookie
test('https://work.weixin.qq.com/wework_admin/loginpage_wx', 'GET', None, None, '1. 管理端登录页')

# 2. 测试一系列的接口
cases = [
    # 管理端 wwlogin 系列 (与之前 qrcode_key 类似的路径)
    ('https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode', 'GET',
     {'login_type': 'wwclient', 'qrcode_key': ''}, None,
     '2. wwqrlogin/mng/qrcode (管理端)'),

    # 测试不带 key 的情况
    ('https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode', 'GET',
     {'login_type': 'login_admin', 'qrcode_key': ''}, None,
     '3. wwqrlogin/mng/qrcode login_admin 类型'),

    # wwlogin (不是 wwqrlogin) 路径
    ('https://work.weixin.qq.com/wework_admin/wwlogin/mng/qrcode', 'GET',
     None, None, '4. wwlogin/mng/qrcode (老路径)'),

    # web.weixin.qq.com (微信扫码)
    ('https://login.wx.qq.com/jslogin', 'GET',
     {'appid': 'wx782c26e4c19acffb', 'redirect_uri': 'https://work.weixin.qq.com/wework_admin/loginpage_wx?lang=zh_CN',
      'fun': 'new', 'lang': 'zh_CN', '_': str(int(time.time()*1000))},
     None, '5. 微信 jslogin (wx.qq.com)'),

    # work.weixin.qq.com 版本
    ('https://login.work.weixin.qq.com/jslogin', 'GET',
     {'appid': 'wx782c26e4c19acffb', 'redirect_uri': 'https://work.weixin.qq.com/wework_admin/loginpage_wx?lang=zh_CN',
      'fun': 'new', 'lang': 'zh_CN', '_': str(int(time.time()*1000))},
     None, '6. 企微 jslogin'),

    # 企微客户端登录 (手机端版)
    ('https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key', 'GET',
     {'login_type': 'login_admin', 'r': str(time.time())},
     None, '7. get_key (先获取 key 再获取二维码)'),
]

for url, method, params, data, desc in cases:
    test(url, method, params, data, desc)

# 8. 如果 get_key 返回结果，用 key 获取真正的二维码
print('\n' + '='*70)
print('尝试先获取 key 再获取二维码')
print('='*70)

# 获取 key
resp_key = session.get(
    'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key',
    params={'login_type': 'login_admin', 'r': str(time.time())},
    headers=dict(HEADERS),
    timeout=15,
)
print(f'get_key: status={resp_key.status_code}, body={resp_key.text[:300]}')

try:
    key_json = resp_key.json()
    qrcode_key = key_json.get('data', {}).get('qrcode_key', '')
    print(f'qrcode_key: {qrcode_key}')

    if qrcode_key:
        # 获取二维码
        test(
            'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode',
            'GET',
            {'qrcode_key': qrcode_key, 'login_type': 'login_admin'},
            None,
            '9. 用 qrcode_key 获取二维码'
        )
except Exception as e:
    print(f'解析 key 失败: {e}')
