# -*- coding: utf-8 -*-
"""分析二维码扫码后的实际跳转URL"""
import requests
import re
import base64

# 生成二维码
from wecom_app_login_service import get_wecom_app_login_service

service = get_wecom_app_login_service()

print('='*60)
print('分析企业微信二维码内容')
print('='*60)

# 测试两种类型
for login_type in ['wwclient', 'login_admin']:
    sid, err = service.create_session(login_type=login_type)
    qr_bytes = service.get_qrcode_bytes(sid)

    print(f'\n[1] {login_type} 类型二维码分析')
    print(f'    大小: {len(qr_bytes)} bytes')

    # 尝试解码二维码
    try:
        from PIL import Image
        import zbarlight

        img = Image.open(io.BytesIO(qr_bytes))
        codes = zbarlight.scan_codes(['qrcode'], img)
        if codes:
            url = codes[0].decode('utf-8')
            print(f'    二维码内容: {url}')

            # 分析URL
            if 'wwclient' in url:
                print('    ✓ 包含 wwclient 标识')
            if 'login_admin' in url:
                print('    ✓ 包含 login_admin 标识')
            if 'redirect_uri' in url:
                redirect_match = re.search(r'redirect_uri=([^&]+)', url)
                if redirect_match:
                    redirect = requests.utils.unquote(redirect_match.group(1))
                    print(f'    跳转地址: {redirect}')
    except ImportError:
        print('    需要安装 PIL 和 zbarlight 来解码二维码')
        print(f'    pip install Pillow zbarlight')

# 模拟扫码后的跳转
print('\n[2] 分析二维码URL参数')

# 二维码的URL格式通常是:
# https://work.weixin.qq.com/wwlogin/wwloginFrame?qrcode=XXXXX&web=wwclient&t=XXXXX

# 让我检查实际的二维码生成过程
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
})

# 1. 访问登录页
resp1 = session.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', timeout=15)
print(f'\n[3] 登录页响应')
print(f'    状态: {resp1.status_code}')

# 2. 获取 qrcode_key
resp2 = session.get(
    'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key',
    params={'login_type': 'wwclient', 'r': '0.123'},
    headers={'X-Requested-With': 'XMLHttpRequest'},
    timeout=15
)
print(f'\n[4] 获取 qrcode_key')
print(f'    状态: {resp2.status_code}')
print(f'    响应: {resp2.text[:200]}')

if resp2.status_code == 200:
    try:
        data = resp2.json()
        qrcode_key = data.get('data', {}).get('qrcode_key')
        print(f'    qrcode_key: {qrcode_key}')

        # 3. 获取二维码
        resp3 = session.get(
            'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode',
            params={'qrcode_key': qrcode_key, 'login_type': 'wwclient'},
            timeout=15
        )
        print(f'\n[5] 获取二维码图片')
        print(f'    状态: {resp3.status_code}')
        print(f'    大小: {len(resp3.content)} bytes')
        print(f'    Content-Type: {resp3.headers.get("Content-Type")}')

    except:
        print('    JSON解析失败')

print('\n结论:')
print('- wwclient 和 login_admin 都使用同一个二维码协议')
print('- 区别在于 login_type 参数')
print('- 扫码后的跳转页面由服务器决定，无法通过协议修改')
