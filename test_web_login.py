# -*- coding: utf-8 -*-
"""测试企业微信网页版登录接口"""
import requests
import re

ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

session = requests.Session()

# 访问企业微信网页版登录页
login_url = 'https://work.weixin.qq.com/wework_admin/loginpage_wx'
resp = session.get(login_url, headers={'User-Agent': ua}, timeout=15)
print(f'登录页状态: {resp.status_code}')

# 查找页面中的二维码相关信息
html = resp.text

# 查找 iframe
iframe_match = re.search(r'<iframe[^>]*src=["\']([^"\']+)["\']', html)
if iframe_match:
    iframe_url = iframe_match.group(1)
    if not iframe_url.startswith('http'):
        iframe_url = 'https://work.weixin.qq.com' + iframe_url
    print(f'找到 iframe: {iframe_url}')
    
    # 访问 iframe
    iframe_resp = session.get(iframe_url, headers={'User-Agent': ua}, timeout=15)
    print(f'iframe 状态: {iframe_resp.status_code}')
    
    # 检查是否是图片
    if iframe_resp.content[:4] == b'\x89PNG':
        print('iframe 返回的是 PNG 图片')
        with open('d:/fh/test_web_qr.png', 'wb') as f:
            f.write(iframe_resp.content)
        print('图片已保存')
    else:
        # 解析 iframe 内容
        iframe_html = iframe_resp.text
        qr_match = re.search(r'qrcodeUrl\s*[:=]\s*["\']([^"\']+)["\']', iframe_html)
        if qr_match:
            qr_url = qr_match.group(1)
            print(f'找到二维码 URL: {qr_url}')

# 查找页面中的 JavaScript 变量
js_vars = re.findall(r'(\w+)\s*=\s*["\']([^"\']+)["\']', html)
print(f'找到 {len(js_vars)} 个变量')
for name, value in js_vars[:10]:
    print(f'  {name} = {value}')

# 保存页面
with open('d:/fh/debug/web_login_page.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('页面已保存')