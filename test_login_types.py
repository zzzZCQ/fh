# -*- coding: utf-8 -*-
"""测试各种 login_type 的 get_key 接口"""
import requests
import time
import json

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://work.weixin.qq.com/',
    'X-Requested-With': 'XMLHttpRequest',
}

# 先访问登录页
resp = session.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers=headers, timeout=15)
print(f'登录页: {resp.status_code}, cookies: {[c.name for c in session.cookies]}')

# 测试各种 login_type
login_types = [
    'login_admin',          # 管理后台 - 已测试可用
    'wwclient',             # 企微APP客户端 - 测试报错
    'service_login',        # 服务商登录
    'wxwork_pc_login',      # PC客户端登录
    'pc_login',             # PC登录
    'wework_login',         # 企微登录
    'mobile_login',         # 手机登录
    'app_login',            # APP登录
    'corp_login',           # 企业登录
    'wework_client',        # 企微客户端
    'wxwork_client',        # 微信企微客户端
    'wemeet_login',         # 会议登录
    'wx_login',             # 微信登录
    'phone_login',          # 手机号登录
]

print('\n' + '='*70)
print('测试各种 login_type')
print('='*70)

for lt in login_types:
    try:
        params = {'login_type': lt, 'r': str(time.time())}
        resp = session.get(
            'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key',
            headers=headers, params=params, timeout=15
        )
        result = resp.text
        status = resp.status_code

        # 分析结果
        if 'qrcode_key' in result:
            try:
                data = resp.json()
                key = data.get('data', {}).get('qrcode_key', '')
                print(f'✓ {lt:<25} -> {status}, key={key[:16] if key else "空"}')
            except:
                print(f'? {lt:<25} -> {status}, body={result[:120]}')
        else:
            print(f'✗ {lt:<25} -> {status}, body={result[:120]}')

    except Exception as e:
        print(f'✗ {lt:<25} -> Error: {e}')

# 同时也测试一下是否能直接获取二维码（不走 get_key）
print('\n' + '='*70)
print('测试直接获取二维码 (绕过 get_key)')
print('='*70)

direct_types = [
    'wwclient',
    'login_admin',
    'wxwork_pc_login',
    'pc_login',
]

for lt in direct_types:
    try:
        params = {'login_type': lt}
        resp = session.get(
            'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode',
            headers=headers, params=params, timeout=15
        )
        ctype = resp.headers.get('Content-Type', '')
        if 'image' in ctype.lower() or resp.content[:4] == b'\x89PNG':
            fname = f'direct_{lt}.png'
            with open(fname, 'wb') as f:
                f.write(resp.content)
            print(f'✓ direct qrcode login_type={lt}, size={len(resp.content)}, saved={fname}')
        else:
            print(f'✗ direct qrcode login_type={lt}, status={resp.status_code}, body={resp.text[:120]}')
    except Exception as e:
        print(f'✗ direct qrcode login_type={lt}, Error: {e}')
