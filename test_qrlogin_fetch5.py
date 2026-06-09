# -*- coding: utf-8 -*-
import requests
import re

# 先获取企微的 login_mng.js
url = 'https://wwcdn.weixin.qq.com/node/wwmng/wwmng/js/ww_qrcode_login/login_mng$2ee3da37.js'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

resp = requests.get(url, headers=headers, timeout=15)
print(f'status: {resp.status_code}, size: {len(resp.content)}')
js_code = resp.text
print(js_code[:5000])
print()
print('=' * 60)
print('== 查找 URL 构造/请求模式 ==')
# 查找 GET/请求URL模式
# 查找 "login_qrcode" 相关
for m in re.finditer(r'[^.](login|qrcode|qrlogin|loginqrcode)[^a-z]', js_code, re.IGNORECASE):
    start = max(0, m.start() - 50)
    end = min(len(js_code), m.end() + 200)
    print(f'{m.start()}: ...{js_code[start:end]}...')
    print()
