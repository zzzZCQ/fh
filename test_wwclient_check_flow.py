# -*- coding: utf-8 -*-
"""探索：能不能从 wwclient 二维码的响应中提取 qrcode_key，或者有其他方式"""
import requests
import time
import json
import re
import base64

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://work.weixin.qq.com/',
    'X-Requested-With': 'XMLHttpRequest',
}

# 访问登录页
session.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers=headers, timeout=15)

# 1. 先测试 login_admin 完整流程
print('[方案1] login_admin 完整流程测试 (有 key -> 可 check)...')
key_resp = session.get(
    'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key',
    headers=headers, params={'login_type': 'login_admin', 'r': str(time.time())}, timeout=15
)
key_data = key_resp.json()
qrcode_key = key_data.get('data', {}).get('qrcode_key')
print(f'  qrcode_key: {qrcode_key}')

qr_resp = session.get(
    'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode',
    headers=headers, params={'qrcode_key': qrcode_key, 'login_type': 'login_admin'}, timeout=15
)
print(f'  二维码 size: {len(qr_resp.content)} bytes')
with open('flow1_login_admin.png', 'wb') as f:
    f.write(qr_resp.content)

# 立即 check
check_resp = session.get(
    'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/check',
    headers=headers,
    params={'qrcode_key': qrcode_key, 'status': 'QRCODE_SCAN_NEVER', 'r': str(time.time())},
    timeout=30
)
print(f'  check 响应: {check_resp.text[:300]}')

# 2. 测试 wwclient 类型但用 login_admin 的 key 能不能 check
print('\n[方案2] 用 login_admin 的 key + wwclient 二维码，能不能 check?')
qr_resp2 = session.get(
    'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode',
    headers=headers, params={'qrcode_key': qrcode_key, 'login_type': 'wwclient'}, timeout=15
)
ctype = qr_resp2.headers.get('Content-Type', '')
if 'image' in ctype.lower() or qr_resp2.content[:4] == b'\x89PNG':
    print(f'  ✓ 返回二维码 ({len(qr_resp2.content)} bytes)')
    with open('flow2_mixed_login.png', 'wb') as f:
        f.write(qr_resp2.content)
    # 用同一个 key 来 check
    check_resp2 = session.get(
        'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/check',
        headers=headers,
        params={'qrcode_key': qrcode_key, 'status': 'QRCODE_SCAN_NEVER', 'r': str(time.time())},
        timeout=30
    )
    print(f'  check: {check_resp2.text[:300]}')
else:
    print(f'  ✗ 返回非图片: {qr_resp2.text[:300]}')

# 3. 方案：直接用 wwclient 二维码，然后把 cookie 中的信息提取出来作为 key
print('\n[方案3] 检查 wwclient 二维码响应的 set-cookie，是否隐含 key...')
s3 = requests.Session()
s3.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers=headers, timeout=15)
qr_resp3 = s3.get(
    'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode',
    headers=headers, params={'login_type': 'wwclient'}, timeout=15
)
print(f'  Set-Cookie: {dict(qr_resp3.cookies) if hasattr(qr_resp3, "cookies") else qr_resp3.headers.get("Set-Cookie", "")}')
print(f'  Response headers:')
for k, v in qr_resp3.headers.items():
    print(f'    {k}: {v}')

# 4. 方案：先 get_key(login_admin) 拿 key，再用 wwclient 扫码，但 check 用 wwclient
print('\n[方案4] 先拿 login_admin key，再生成 wwclient 二维码，用 key check...')
# 用新的 session
s4 = requests.Session()
s4.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers=headers, timeout=15)
key_resp4 = s4.get(
    'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key',
    headers=headers, params={'login_type': 'login_admin', 'r': str(time.time())}, timeout=15
)
try:
    qrcode_key4 = key_resp4.json().get('data', {}).get('qrcode_key')
    print(f'  获取 key: {qrcode_key4}')

    # 用 key + wwclient 拿二维码
    qr_resp4 = s4.get(
        'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode',
        headers=headers, params={'qrcode_key': qrcode_key4, 'login_type': 'wwclient'}, timeout=15
    )
    ctype4 = qr_resp4.headers.get('Content-Type', '')
    if 'image' in ctype4.lower() or qr_resp4.content[:4] == b'\x89PNG':
        print(f'  ✓ 生成 wwclient 二维码 ({len(qr_resp4.content)} bytes)')
        with open('flow4_wwclient_withkey.png', 'wb') as f:
            f.write(qr_resp4.content)

        # check 测试
        check_resp4 = s4.get(
            'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/check',
            headers=headers,
            params={'qrcode_key': qrcode_key4, 'status': 'QRCODE_SCAN_NEVER', 'r': str(time.time())},
            timeout=30
        )
        print(f'  check: {check_resp4.text[:300]}')
    else:
        print(f'  ✗ 二维码获取失败: {qr_resp4.text[:300]}')
except Exception as e:
    print(f'  异常: {e}, raw={key_resp4.text[:200]}')

# 5. 测试 service_login 能不能用 wwclient 二维码
print('\n[方案5] service_login 方式...')
s5 = requests.Session()
s5.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers=headers, timeout=15)
key_resp5 = s5.get(
    'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key',
    headers=headers, params={'login_type': 'service_login', 'r': str(time.time())}, timeout=15
)
try:
    qrcode_key5 = key_resp5.json().get('data', {}).get('qrcode_key')
    print(f'  service_login key: {qrcode_key5}')
    qr_resp5 = s5.get(
        'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode',
        headers=headers, params={'qrcode_key': qrcode_key5, 'login_type': 'wwclient'}, timeout=15
    )
    if qr_resp5.content[:4] == b'\x89PNG':
        print(f'  ✓ 二维码: {len(qr_resp5.content)} bytes')
        check_resp5 = s5.get(
            'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/check',
            headers=headers,
            params={'qrcode_key': qrcode_key5, 'status': 'QRCODE_SCAN_NEVER', 'r': str(time.time())},
            timeout=30
        )
        print(f'  check: {check_resp5.text[:300]}')
    else:
        print(f'  ✗ 非图片: {qr_resp5.text[:200]}')
except Exception as e:
    print(f'  异常: {e}')

print('\n测试完成!')
