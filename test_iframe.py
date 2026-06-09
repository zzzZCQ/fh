"""测试企微二维码 iframe URL"""
import requests
import re
import base64

ua = 'Mozilla/5.0 (iPad; CPU OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'

# 先访问主登录页获取 iframe URL
print("=== 1. 获取主登录页 ===")
main_url = 'https://work.weixin.qq.com/wework_admin/loginpage_wx'
resp = requests.get(main_url, timeout=30, headers={'User-Agent': ua})
print(f"状态码: {resp.status_code}")

# 提取 iframe URL
iframe_match = re.search(r"src = \[([^\]]+)]", resp.text)
if iframe_match:
    print(f"找到 src 数组: {iframe_match.group(0)[:200]}")

# 更直接的方式：找 WWQRLogin 函数中的 URL
qr_url_match = re.search(r"location\.protocol[^;]+wework_admin([^'\";]+)", resp.text)
if qr_url_match:
    print(f"找到 URL: {qr_url_match.group(0)[:200]}")

# 找 login_qrcode
login_qr_match = re.search(r"login_qrcode[^\"']+", resp.text)
if login_qr_match:
    print(f"找到 login_qrcode: {login_qr_match.group(0)[:200]}")

# 直接构建 iframe URL
ts = int(__import__('time').time() * 1000)
iframe_url = f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/login_qrcode?login_type=login_admin&redirect_uri=&crossorigin=1&_={ts}'
print(f"\n=== 2. 直接访问 iframe URL ===")
print(f"URL: {iframe_url}")

headers = {
    'User-Agent': ua,
    'Referer': main_url,
    'Accept': 'text/html,application/xhtml+xml,*/*',
}

resp2 = requests.get(iframe_url, timeout=30, headers=headers)
print(f"状态码: {resp2.status_code}")
print(f"内容长度: {len(resp2.text)}")

if resp2.status_code == 200:
    # 检查是否是图片
    if 'image' in resp2.headers.get('Content-Type', '').lower() or len(resp2.content) > 1000:
        print("返回的是图片内容！")
        img_b64 = f'data:image/png;base64,{base64.b64encode(resp2.content).decode()}'
        print(f"图片 base64 长度: {len(img_b64)}")
        # 保存图片
        with open('debug_qrcode.png', 'wb') as f:
            f.write(resp2.content)
        print("图片已保存到 debug_qrcode.png")
    else:
        print(f"返回 HTML，长度: {len(resp2.text)}")
        print("=== HTML 内容前 2000 字符 ===")
        print(resp2.text[:2000])
        # 保存
        with open('debug_iframe.html', 'w', encoding='utf-8') as f:
            f.write(resp2.text)

# 尝试另一个格式
print(f"\n=== 3. 尝试 /wework_admin/loginqr/mng/getqrcode ===")
qr_url2 = f'https://work.weixin.qq.com/wework_admin/loginqr/mng/getqrcode?login_type=login_admin&_={ts}'
resp3 = requests.get(qr_url2, timeout=30, headers=headers)
print(f"状态码: {resp3.status_code}, 长度: {len(resp3.content)}")
print(f"Content-Type: {resp3.headers.get('Content-Type', '')}")
if resp3.status_code == 200 and len(resp3.content) > 500:
    with open('debug_qrcode2.png', 'wb') as f:
        f.write(resp3.content)
    print("图片已保存到 debug_qrcode2.png")
else:
    print(resp3.text[:500] if resp3.text else "无文本内容")
