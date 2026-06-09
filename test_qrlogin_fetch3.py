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

# 1. 访问登录页
url1 = 'https://work.weixin.qq.com/wework_admin/loginpage_wx'
resp = session.get(url1, headers=headers, timeout=15)
print('[1] 登录页 status:', resp.status_code)
print('    cookies:', [c.name for c in session.cookies])
print()

# 测试多种获取二维码的方式
test_urls = [
    'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/login_qrcode',
    'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/login_qrcode?login_type=login_admin',
    'https://open.work.weixin.qq.com/wwopen/sso/qrConnect?appid=wx782c26e4c19acffb&redirect_uri=https://work.weixin.qq.com/wework_admin/loginpage_wx&state=STATE&lang=zh_CN',
]

for url in test_urls:
    try:
        h2 = dict(headers)
        h2['Referer'] = 'https://work.weixin.qq.com/wework_admin/loginpage_wx'
        resp2 = session.get(url, headers=h2, timeout=15)
        ctype = resp2.headers.get('Content-Type', '')
        print(f'URL: {url[:90]}')
        print(f'  status: {resp2.status_code}, Content-Type: {ctype}, size: {len(resp2.content)} bytes')
        if 'image' in ctype.lower():
            fname = f'qr_{abs(hash(url))}.png'
            with open(fname, 'wb') as f:
                f.write(resp2.content)
            print(f'  => 图片，保存为 {fname}')
        elif 'json' in ctype.lower():
            print(f'  => JSON: {resp2.text[:500]}')
        else:
            title = re.search(r'<title>([^<]+)</title>', resp2.text, re.IGNORECASE)
            if title:
                print(f'  标题: {title.group(1)}')
            print(f'  内容前500字符: {resp2.text[:500]}')
    except Exception as e:
        print(f'  => 错误: {e}')
    print()
