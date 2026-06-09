# -*- coding: utf-8 -*-
"""
测试：使用 iPad UA 和 X-Requested-With header 访问企业微信
获取普通用户会话凭证 wwrtx.sid
"""
import requests
import base64
import time

# iPad UA
IPAD_UA = 'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'

session = requests.Session()
session.headers.update({
    'User-Agent': IPAD_UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'X-Requested-With': 'wxwork',
})

print('=== 测试 iPad 方式访问企业微信 ===')

# 1. 访问企业微信首页
resp = session.get('https://work.weixin.qq.com/', timeout=15, allow_redirects=True)
print(f'访问首页: {resp.status_code}, URL: {resp.url}')

# 2. 尝试访问登录页（不是 wework_admin）
resp2 = session.get('https://work.weixin.qq.com/login', timeout=15)
print(f'访问登录页: {resp2.status_code}')
print(f'URL: {resp2.url}')

# 3. 查找页面中的登录二维码
import re
# 查找 QR code 相关内容
qr_patterns = [
    r'qrcodeUrl\s*[:=]\s*["\']([^"\']+)["\']',
    r'qr_code\s*[:=]\s*["\']([^"\']+)["\']',
    r'src=["\']([^"\']*qr[^"\']*)["\']',
]

for p in qr_patterns:
    match = re.search(p, resp2.text)
    if match:
        print(f'找到 QR pattern: {p[:30]}... -> {match.group(1)[:80]}')

# 保存页面用于分析
with open('d:/fh/debug/ipad_login_attempt.html', 'w', encoding='utf-8') as f:
    f.write(resp2.text)
print('页面已保存')

# 4. 尝试获取企业微信网页版的二维码
# 企业微信有一个网页版可以扫码登录
resp3 = session.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', timeout=15, allow_redirects=True)
print(f'\n访问 wework_admin: {resp3.status_code}, URL: {resp3.url}')

# 5. 检查 cookies
print('\n当前 Cookies:')
for c in session.cookies:
    print(f'  {c.name}={c.value[:20] if len(c.value) > 20 else c.value}...')

# 6. 获取 qrcode_key
ts = int(time.time() * 1000)
key_resp = session.get(f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key?login_type=login_admin&r={ts}', timeout=15)
print(f'\n获取 key: {key_resp.status_code}')
try:
    key_data = key_resp.json()
    qrcode_key = key_data.get('data', {}).get('qrcode_key', '')
    print(f'qrcode_key: {qrcode_key[:30] if qrcode_key else None}...')
except:
    print(f'响应: {key_resp.text[:200]}')

# 7. 用 key 获取 wwclient 二维码
if qrcode_key:
    print(f'\n=== 获取 wwclient 二维码 ===')
    qr_resp = session.get(
        f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode?qrcode_key={qrcode_key}&login_type=wwclient',
        timeout=15
    )
    print(f'状态: {qr_resp.status_code}, 大小: {len(qr_resp.content)}')
    if qr_resp.content[:4] == b'\x89PNG':
        with open('d:/fh/test_wwclient_qr.png', 'wb') as f:
            f.write(qr_resp.content)
        print('wwclient 二维码已保存')

    # 获取 login_admin 二维码
    qr_resp2 = session.get(
        f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode?qrcode_key={qrcode_key}&login_type=login_admin',
        timeout=15
    )
    print(f'\nlogin_admin 状态: {qr_resp2.status_code}, 大小: {len(qr_resp2.content)}')
    if qr_resp2.content[:4] == b'\x89PNG':
        with open('d:/fh/test_admin_qr.png', 'wb') as f:
            f.write(qr_resp2.content)
        print('login_admin 二维码已保存')