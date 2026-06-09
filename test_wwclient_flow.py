# -*- coding: utf-8 -*-
"""测试直接获取 wwclient 类型二维码，然后验证 check 接口是否能正常轮询"""
import requests
import time
import json
import base64

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://work.weixin.qq.com/',
    'X-Requested-With': 'XMLHttpRequest',
}

# 1. 访问登录页
session.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers=headers, timeout=15)
print('[1] 已获取 cookie')

# 2. 直接获取 wwclient 类型二维码
qr_params = {'login_type': 'wwclient'}
resp_qr = session.get(
    'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode',
    headers=headers, params=qr_params, timeout=15
)
print(f'[2] 二维码状态: {resp_qr.status_code}, Content-Type: {resp_qr.headers.get("Content-Type", "")}')

if resp_qr.status_code == 200 and resp_qr.content[:4] == b'\x89PNG':
    fname = 'wwclient_qrcode.png'
    with open(fname, 'wb') as f:
        f.write(resp_qr.content)
    print(f'    已保存为 {fname} ({len(resp_qr.content)} bytes)')

    # 检查响应头是否有 ticket/auth_code
    print(f'    响应头: {dict(resp_qr.headers)}')

    # 3. 测试 check 接口
    print('\n[3] 测试状态检查 (不提供 qrcode_key)...')
    for test_status in ['QRCODE_SCAN_NEVER', '']:
        check_params = {
            'login_type': 'wwclient',
            'status': test_status,
            'r': str(time.time()),
        }
        resp_check = session.get(
            'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/check',
            headers=headers, params=check_params, timeout=15
        )
        print(f'    status={test_status or "空"}: HTTP {resp_check.status_code}, body={resp_check.text[:300]}')

    # 4. 也测试一下 service_login (支持 get_key 的)
    print('\n[4] 测试 service_login 完整流程...')
    s2 = requests.Session()
    s2.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers=headers, timeout=15)

    resp_key = s2.get(
        'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key',
        headers=headers, params={'login_type': 'service_login', 'r': str(time.time())}, timeout=15
    )
    try:
        key_data = resp_key.json()
        print(f'    get_key: {key_data}')
        qrcode_key = key_data.get('data', {}).get('qrcode_key')
        if qrcode_key:
            resp_qr2 = s2.get(
                'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode',
                headers=headers, params={'qrcode_key': qrcode_key, 'login_type': 'service_login'},
                timeout=15
            )
            if resp_qr2.status_code == 200 and resp_qr2.content[:4] == b'\x89PNG':
                with open('service_login_qr.png', 'wb') as f:
                    f.write(resp_qr2.content)
                print(f'    service_login 二维码已保存 ({len(resp_qr2.content)} bytes)')

            # 测试 check
            resp_check2 = s2.get(
                'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/check',
                headers=headers, params={'qrcode_key': qrcode_key, 'status': 'QRCODE_SCAN_NEVER', 'r': str(time.time())},
                timeout=15
            )
            print(f'    service_login check: body={resp_check2.text[:300]}')
    except Exception as e:
        print(f'    service_login 解析失败: {e}, raw={resp_key.text[:200]}')

else:
    print(f'    不是图片: {resp_qr.text[:300]}')

# 5. 测试不同 login_type 直接 qrcode 的字节大小
print('\n[5] 不同 login_type 二维码大小对比 (用于确认确实是不同的二维码)...')
for lt in ['wwclient', 'login_admin', 'service_login', 'wxwork_pc_login', 'pc_login']:
    resp = session.get(
        'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode',
        headers=headers, params={'login_type': lt}, timeout=15
    )
    if resp.status_code == 200 and resp.content[:4] == b'\x89PNG':
        print(f'    {lt:<25} -> {len(resp.content)} bytes')
    else:
        print(f'    {lt:<25} -> ERROR: {resp.text[:100]}')

print('\n测试完成!')
