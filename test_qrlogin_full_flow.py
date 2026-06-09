# -*- coding: utf-8 -*-
import requests
import time
import base64
import json
import random

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'X-Requested-With': 'XMLHttpRequest',
}

session = requests.Session()

# 步骤 1: 访问登录页获取cookie
print('[1/4] 访问登录页...')
resp1 = session.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers=headers, timeout=15)
print(f'    status: {resp1.status_code}')
print(f'    cookies: {[(c.name, c.value[:30]) for c in session.cookies]}')

# 步骤 2: 获取 qrcode_key
print('[2/4] 获取 qrcode_key...')
h2 = dict(headers)
h2['Referer'] = 'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/login_qrcode?login_type=login_admin'
rand_r = str(random.random())
resp2 = session.get(
    f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key?r={rand_r}',
    params={'login_type': 'login_admin'},
    headers=h2,
    timeout=15,
)
print(f'    status: {resp2.status_code}')
print(f'    content-type: {resp2.headers.get("Content-Type", "")}')
print(f'    raw: {resp2.text[:500]}')

try:
    data = resp2.json()
    qrcode_key = data.get('data', {}).get('qrcode_key')
    print(f'    qrcode_key: {qrcode_key}')
except Exception as e:
    print(f'    json parse error: {e}')
    print(f'    尝试从 HTML 中提取...')
    qrcode_key = None

if not qrcode_key:
    print('  没有获取到 qrcode_key, 退出')
    exit(1)

# 步骤 3: 获取二维码图片
print('[3/4] 获取二维码图片...')
qr_url = (
    'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode'
    f'?qrcode_key={qrcode_key}&login_type=login_admin'
)
resp3 = session.get(qr_url, headers=h2, timeout=15)
print(f'    status: {resp3.status_code}')
print(f'    content-type: {resp3.headers.get("Content-Type", "")}')
print(f'    size: {len(resp3.content)} bytes')

ctype = resp3.headers.get('Content-Type', '')
if 'image' in ctype.lower() or resp3.content[:4] == b'\x89PNG' or resp3.content[:3] == b'\xff\xd8\xff':
    with open('real_wecom_qrcode.png', 'wb') as f:
        f.write(resp3.content)
    print(f'    成功保存为 real_wecom_qrcode.png ({len(resp3.content)} bytes)')
else:
    print(f'    不是图片! 内容前500字节: {resp3.text[:500] if resp3.text[:200].isprintable() or len(resp3.text) < 200 else repr(resp3.content[:200])}')

# 步骤 4: 尝试一次 check
print('[4/4] 测试一次状态检查...')
time.sleep(1)
resp4 = session.get(
    f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/check?qrcode_key={qrcode_key}&status=QRCODE_SCAN_NEVER&r={random.random()}',
    headers=h2,
    timeout=30,
)
print(f'    status: {resp4.status_code}')
print(f'    content-type: {resp4.headers.get("Content-Type", "")}')
print(f'    response: {resp4.text[:300]}')
