# -*- coding: utf-8 -*-
"""
企微登录 key 生成逻辑分析
通过分析登录页面的 JS，找到 key 的生成方式
"""
import requests
import re
import json
import hashlib
import time

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
})

def fetch_login_page():
    """获取企微登录页面"""
    url = 'https://open.work.weixin.qq.com/wwopen/sso/qConnect?appid=wx782c26e4c19acffb&redirect_uri=https://work.weixin.qq.com/wework_admin/loginpage_wx&scope=snsapi_login'
    resp = session.get(url, timeout=10, allow_redirects=True)
    print(f"页面状态: {resp.status_code}")
    print(f"最终 URL: {resp.url}")
    print(f"页面大小: {len(resp.text)} bytes")

    # 保存页面
    with open('_login_page_analysis.html', 'w', encoding='utf-8') as f:
        f.write(resp.text)
    print("已保存页面到 _login_page_analysis.html")

    return resp.text, resp.url


def extract_js_urls(html):
    """提取页面中的 JS 文件 URL"""
    # 查找 script src
    js_urls = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html)
    # 查找 link href (css)
    css_urls = re.findall(r'<link[^>]+href=["\']([^"\']+)["\']', html)

    print(f"\n找到 {len(js_urls)} 个 JS, {len(css_urls)} 个 CSS")

    # 特别关注 seajs 相关的
    seajs_urls = [u for u in js_urls if 'sea' in u.lower() or 'login' in u.lower() or 'sso' in u.lower()]
    print(f"可能是登录相关的 JS: {seajs_urls[:10]}")

    return js_urls


def download_and_search_js(js_urls):
    """下载 JS 文件并搜索 key 生成逻辑"""
    os.makedirs('_js_analysis', exist_ok=True)

    for url in js_urls[:20]:  # 限制数量
        try:
            if url.startswith('//'):
                url = 'https:' + url
            elif not url.startswith('http'):
                url = 'https://open.work.weixin.qq.com' + url

            fname = url.split('/')[-1].split('?')[0]
            if len(fname) > 50:
                fname = fname[:50]

            resp = session.get(url, timeout=10)
            fpath = f'_js_analysis/{fname}'
            with open(fpath, 'w', encoding='utf-8', errors='ignore') as f:
                f.write(resp.text)

            # 搜索 key 相关代码
            content = resp.text
            keywords = ['key', 'uuid', 'qrconnect', 'wwopen', 'appid', 'login', 'redirect']
            found = [kw for kw in keywords if kw.lower() in content.lower()]

            if found:
                print(f"\n{fname}: 包含 {found}")
                # 搜索 key 生成相关的代码模式
                for pattern in [r'key["\s]*[:=]["\s]*([a-zA-Z0-9_-]{20,})',
                               r'window\.settings\s*=\s*\{[^}]+\}',
                               r'QRConnect[^;]+',
                               r'qrImg[^;]+']:
                    matches = re.findall(pattern, content)
                    if matches:
                        print(f"  模式 {pattern}: {matches[:3]}")

        except Exception as e:
            print(f"下载失败 {url}: {e}")


def search_api_endpoints():
    """搜索可能生成 key 的 API"""
    # 企微可能有专门的 key 生成 API
    potential_urls = [
        'https://open.work.weixin.qq.com/wwopen/sso/qrKey',
        'https://open.work.weixin.qq.com/wwopen/sso/qrLogin',
        'https://open.work.weixin.qq.com/wwopen/sso/getKey',
        'https://open.work.weixin.qq.com/wwopen/sso/qConnect',
    ]

    for url in potential_urls:
        try:
            resp = session.get(url, timeout=5)
            print(f"\n{url}")
            print(f"  状态: {resp.status_code}")
            print(f"  大小: {len(resp.content)}")
            if resp.status_code == 200 and len(resp.content) < 1000:
                print(f"  内容: {resp.text[:200]}")
        except Exception as e:
            print(f"\n{url}: {e}")


def analyze_api_responses():
    """分析已知的 API 响应"""
    # 企微登录相关的 API
    apis = [
        # 第三方扫码登录
        ('https://open.work.weixin.qq.com/wwopen/sso/qConnect', {
            'appid': 'wx782c26e4c19acffb',
            'redirect_uri': 'https://work.weixin.qq.com/wework_admin/loginpage_wx',
            'scope': 'snsapi_login',
            'state': 'state',
            'login_type': 's/login',
            'href': '',
            'style': '',
            's': '',
        }),
        # 二维码图片
        ('https://open.work.weixin.qq.com/wwopen/sso/qrImg', {
            'key': 'test_key_1234567890123456789012345678',
            'mod': '0',
        }),
        # 轮询状态
        ('https://open.work.weixin.qq.com/wwopen/sso/l/qrConnect', {
            'key': 'test_key_1234567890123456789012345678',
            'statusCode': '',
            'lastStatus': '',
            'redirect_uri': 'https://work.weixin.qq.com',
            'appid': '',
            '_': int(time.time() * 1000),
        }),
    ]

    for url, params in apis:
        try:
            resp = session.get(url, params=params, timeout=5)
            print(f"\n{url}")
            print(f"  状态: {resp.status_code}")
            print(f"  类型: {resp.headers.get('Content-Type', 'unknown')}")
            print(f"  大小: {len(resp.content)}")

            # 如果是 JSON
            if 'json' in resp.headers.get('Content-Type', '').lower():
                try:
                    data = resp.json()
                    print(f"  JSON: {json.dumps(data, ensure_ascii=False)[:200]}")
                except:
                    print(f"  文本: {resp.text[:200]}")
            else:
                print(f"  前100字节: {resp.content[:100].hex() if resp.content else 'empty'}")

        except Exception as e:
            print(f"\n{url}: {e}")


if __name__ == '__main__':
    print("=== 企微登录 key 分析 ===")

    html, final_url = fetch_login_page()
    js_urls = extract_js_urls(html)
    download_and_search_js(js_urls)
    search_api_endpoints()
    analyze_api_responses()
