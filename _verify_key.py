# -*- coding: utf-8 -*-
"""分析 work.weixin.qq.com 的登录 iframe URL"""
import requests
import re
import json
import time

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://work.weixin.qq.com/',
})

WORK_BASE = 'https://work.weixin.qq.com'

def test_login_page():
    """请求登录页面"""
    url = f'{WORK_BASE}/wework_admin/loginpage_wx'
    print(f"请求登录页面: {url}")
    resp = session.get(url, timeout=10, allow_redirects=True)
    print(f"状态: {resp.status_code}, 大小: {len(resp.text)}")
    return resp


def test_qr_iframe():
    """直接请求 QR iframe URL"""
    # 这个 URL 是从 JS 中提取的
    callback = f'wwqrloginCallback_{int(time.time() * 1000)}'
    redirect_uri = f'{WORK_BASE}/wework_admin/loginpage_wx'

    params = {
        'login_type': 'login_admin',
        'callback': callback,
        'redirect_uri': redirect_uri,
        'scope': 'snsapi_login',
    }

    url = f'{WORK_BASE}/wework_admin/wwqrlogin/mng/login_qrcode'
    print(f"\n请求 QR iframe: {url}")
    print(f"参数: {params}")

    resp = session.get(url, params=params, timeout=10, allow_redirects=True)
    print(f"状态: {resp.status_code}, 大小: {len(resp.content)}")
    print(f"类型: {resp.headers.get('Content-Type')}")

    # 检查是否是 HTML/JS
    if b'<script' in resp.content[:200] or b'window' in resp.content[:200]:
        print("可能是 JS 内容")
        # 提取 JS 中的 key 或 qrcode
        text = resp.text
        for pattern in [r'key["\s]*[:=]["\s]*([a-zA-Z0-9_-]{20,})',
                       r'qrcode["\s]*[:=]["\s]*([^"\';\s]{50,})',
                       r'src=["\']([^"\']+\.png[^"\']*)["\'']]:
            m = re.search(pattern, text)
            if m:
                print(f"找到: {m.group(0)[:100]}")

        with open('_qr_iframe_resp.html', 'w', encoding='utf-8') as f:
            f.write(text)
        print("已保存到 _qr_iframe_resp.html")
        return text

    elif resp.content[:8] == b'\x89PNG\r\n\x1a\n':
        print("返回的是 PNG 图片！")
        with open('_qr_direct.png', 'wb') as f:
            f.write(resp.content)
        print("已保存到 _qr_direct.png")
        return resp.content

    else:
        print(f"内容前200字符: {resp.text[:200]}")
        return resp.content


def test_wwqrlogin_api():
    """尝试其他 wwqrlogin 相关的 API"""
    apis = [
        f'{WORK_BASE}/wework_admin/wwqrlogin/mng/login_qrcode',
        f'{WORK_BASE}/wework_admin/wwqrlogin/qrcode',
        f'{WORK_BASE}/wework_admin/wwqrlogin/getqrcode',
    ]

    callback = f'cb_{int(time.time())}'
    redirect = f'{WORK_BASE}/wework_admin/loginpage_wx'

    for url in apis:
        try:
            params = {
                'login_type': 'login_admin',
                'callback': callback,
                'redirect_uri': redirect,
            }
            resp = session.get(url, params=params, timeout=5)
            print(f"\n{url}")
            print(f"  状态: {resp.status_code}, 大小: {len(resp.content)}")
            if resp.content[:8] == b'\x89PNG\r\n\x1a\n':
                print("  ✅ PNG 图片")
            else:
                print(f"  内容: {resp.text[:150]}")
        except Exception as e:
            print(f"\n{url}: {e}")


if __name__ == '__main__':
    print("=== 分析企微管理后台登录流程 ===\n")

    # 先获取登录页面
    test_login_page()

    # 尝试 QR iframe
    test_qr_iframe()

    # 尝试其他 API
    test_wwqrlogin_api()
