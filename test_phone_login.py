# -*- coding: utf-8 -*-
"""测试企业微信手机号验证码登录协议"""
import requests
import time
import re
import json

session = requests.Session()

headers = {
    'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.0',
    'Referer': 'https://wx.work.weixin.qq.com/',
    'Accept': 'application/json, text/plain, */*',
}

print('='*60)
print('研究企业微信手机号验证码登录协议')
print('='*60)

# 1. 测试发送验证码接口
print('\n[1] 测试发送验证码接口')
phone = '13800138000'  # 测试手机号

sms_urls = [
    # 企业微信手机号登录相关接口
    'https://wx.work.weixin.qq.com/wwlogin/sms/send',
    'https://wx.work.weixin.qq.com/wwlogin/wwlogin/sms_send',
    'https://qyapi.weixin.qq.com/cgi/login/sms_send',
    'https://open.work.weixin.qq.com/wwlogin/sms/send',
]

for url in sms_urls:
    try:
        resp = session.post(url, json={'phone': phone}, headers=headers, timeout=10)
        print(f'{url}')
        print(f'  状态: {resp.status_code}')
        print(f'  响应: {resp.text[:200]}')
    except Exception as e:
        print(f'{url}: 错误 - {e}')

# 2. 测试登录页面结构
print('\n[2] 分析登录页面结构')
login_page_urls = [
    'https://wx.work.weixin.qq.com/wwlogin/wwlogin.html',
    'https://work.weixin.qq.com/wework_admin/loginpage_wx',
]

for url in login_page_urls:
    try:
        resp = session.get(url, headers=headers, timeout=15)
        print(f'\n{url}')
        print(f'  状态: {resp.status_code}')
        
        # 搜索手机号相关接口
        phone_patterns = [
            r'sms[Uu]rl\s*[:=]\s*["\']([^"\']+)["\']',
            r'phone[Uu]rl\s*[:=]\s*["\']([^"\']+)["\']',
            r'api["\']?\s*:\s*["\']([^"\']*sms[^"\']*)["\']',
            r'api["\']?\s*:\s*["\']([^"\']*login[^"\']*)["\']',
        ]
        
        content = resp.text
        for p in phone_patterns:
            matches = re.findall(p, content, re.IGNORECASE)
            if matches:
                print(f'  找到: {matches[:2]}')
    except Exception as e:
        print(f'{url}: 错误 - {e}')

# 3. 测试企业微信开放平台的登录接口
print('\n[3] 测试企业微信开放平台登录接口')
open_urls = [
    'https://open.work.weixin.qq.com/wwlogin/sms/send?appid=wx782c26e4c19acffb&fun=new&lang=zh_CN&phone=13800138000',
]

for url in open_urls:
    try:
        resp = session.get(url, headers=headers, timeout=15, allow_redirects=False)
        print(f'{url}')
        print(f'  状态: {resp.status_code}')
        print(f'  headers: {dict(resp.headers)}')
    except Exception as e:
        print(f'{url}: 错误 - {e}')

# 4. 检查企业微信APP的登录协议
print('\n[4] 搜索企业微信手机登录相关文档/接口')
# 尝试一些常见的API模式
api_patterns = [
    'https://qyapi.weixin.qq.com/cgi/login/phone_send',
    'https://qyapi.weixin.qq.com/cgi/login/phone_verify',
    'https://wx.work.weixin.qq.com/cgi/login/phone_send',
]

for url in api_patterns:
    try:
        resp = session.get(url, headers=headers, timeout=10)
        print(f'{url}: {resp.status_code}')
    except Exception as e:
        print(f'{url}: {e}')

print('\n分析完成!')
print('\n结论：需要找到企业微信的手机号验证码登录API')
