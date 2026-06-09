# -*- coding: utf-8 -*-
"""测试 wwclient 类型的 key 获取"""
import requests
import time
import base64

session = requests.Session()
ua = 'Mozilla/5.0 (iPad; CPU OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'

headers = {
    'User-Agent': ua,
    'Referer': 'https://work.weixin.qq.com/wework_admin/loginpage_wx',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
}

# 先访问登录页获取 cookies
session.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers={'User-Agent': ua}, timeout=15)

print("=== 测试不同 login_type 获取 key ===")

# 测试 login_admin
ts = int(time.time() * 1000)
resp1 = session.get(f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key?login_type=login_admin&r={ts}', headers=headers, timeout=15)
print(f"login_admin key: {resp1.json().get('data', {}).get('qrcode_key', 'N/A')[:30] if resp1.status_code == 200 else '失败'}")

# 测试 wwclient
ts = int(time.time() * 1000)
resp2 = session.get(f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key?login_type=wwclient&r={ts}', headers=headers, timeout=15)
print(f"wwclient key: {resp2.json().get('data', {}).get('qrcode_key', 'N/A')[:30] if resp2.status_code == 200 else '失败'}")
print(f"wwclient 响应: {resp2.text[:200]}")

# 测试 service_login
ts = int(time.time() * 1000)
resp3 = session.get(f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key?login_type=service_login&r={ts}', headers=headers, timeout=15)
print(f"service_login key: {resp3.json().get('data', {}).get('qrcode_key', 'N/A')[:30] if resp3.status_code == 200 else '失败'}")

# 用 login_admin 的 key，获取 wwclient 二维码
admin_key = resp1.json().get('data', {}).get('qrcode_key')
if admin_key:
    print(f"\n=== 用 login_admin key 获取不同类型二维码 ===")
    ts = int(time.time() * 1000)

    # wwclient 类型
    qr_resp = session.get(f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode?qrcode_key={admin_key}&login_type=wwclient', headers={**headers, 'Accept': 'image/png'}, timeout=15)
    print(f"wwclient 二维码: status={qr_resp.status_code}, size={len(qr_resp.content)}")
    if qr_resp.content[:4] == b'\x89PNG':
        with open('test_wwclient_qr.png', 'wb') as f:
            f.write(qr_resp.content)
        print("已保存到 test_wwclient_qr.png")

    # login_admin 类型
    qr_resp2 = session.get(f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode?qrcode_key={admin_key}&login_type=login_admin', headers={**headers, 'Accept': 'image/png'}, timeout=15)
    print(f"login_admin 二维码: status={qr_resp2.status_code}, size={len(qr_resp2.content)}")
    if qr_resp2.content[:4] == b'\x89PNG':
        with open('test_admin_qr.png', 'wb') as f:
            f.write(qr_resp2.content)
        print("已保存到 test_admin_qr.png")

# 用 wwclient 的 key，获取 wwclient 二维码
wwclient_key = resp2.json().get('data', {}).get('qrcode_key')
if wwclient_key and wwclient_key != 'None':
    print(f"\n=== 用 wwclient key 获取 wwclient 二维码 ===")
    ts = int(time.time() * 1000)
    qr_resp3 = session.get(f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode?qrcode_key={wwclient_key}&login_type=wwclient', headers={**headers, 'Accept': 'image/png'}, timeout=15)
    print(f"wwclient 二维码: status={qr_resp3.status_code}, size={len(qr_resp3.content)}")
    if qr_resp3.content[:4] == b'\x89PNG':
        with open('test_wwclient_key_wwclient_qr.png', 'wb') as f:
            f.write(qr_resp3.content)
        print("已保存到 test_wwclient_key_wwclient_qr.png")
