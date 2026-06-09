# -*- coding: utf-8 -*-
import requests
import re
import base64

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

session = requests.Session()

# 1. 访问登录页获取 cookie
resp = session.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers=headers, timeout=15)
print('登录页 status:', resp.status_code)
print('cookies:', {c.name: c.value[:60] for c in resp.cookies})

# 2. 请求 login_qrcode
qr_url = 'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/login_qrcode?login_type=login_admin&redirect_uri=' + \
         requests.compat.urlencode({'':'https://work.weixin.qq.com/wework_admin/frame'})[1:]

# 构造请求，带 Referer
headers2 = dict(headers)
headers2['Referer'] = 'https://work.weixin.qq.com/wework_admin/loginpage_wx'

print('\n=== 请求 login_qrcode ===')
print('URL:', qr_url[:200])
resp2 = session.get(qr_url, headers=headers2, timeout=15)
print('status:', resp2.status_code)
print('Content-Type:', resp2.headers.get('Content-Type', ''))
print('length:', len(resp2.content))

# 3. 检查响应类型
ctype = resp2.headers.get('Content-Type', '')
if 'image' in ctype.lower():
    print('=> 返回的是图片')
    with open('qr_code_resp.png', 'wb') as f:
        f.write(resp2.content)
    print('   已保存为 qr_code_resp.png')
elif 'html' in ctype.lower():
    print('=> 返回的是 HTML')
    print(resp2.text[:3000])
else:
    print('=> 返回内容 (前 1000 bytes):')
    try:
        print(resp2.text[:1000])
    except:
        print(resp2.content[:1000])

# 4. 检查 response 是否是 JSON
try:
    import json
    data = resp2.json()
    print('\n=> JSON response:')
    print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
except:
    pass
