"""测试企微登录页实际返回内容"""
import requests

url = 'https://work.weixin.qq.com/wework_admin/loginpage_wx'
ua = 'Mozilla/5.0 (iPad; CPU OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'

resp = requests.get(url, timeout=30, headers={'User-Agent': ua})
print(f"状态码: {resp.status_code}")
print(f"内容长度: {len(resp.text)}")
print(f"Content-Type: {resp.headers.get('Content-Type', '')}")
print()

# 检查二维码相关关键字
html = resp.text
keywords = ['qrcode', 'qr_code', 'qr', 'base64', 'image', 'img', 'login', 'appid', 'uuid', 'wx']
print("关键字出现情况:")
for kw in keywords:
    count = html.lower().count(kw)
    print(f"  {kw}: {count}次")

print()
print("=== HTML 前2000字符 ===")
print(html[:2000])
print()
print("=== HTML 后1000字符 ===")
print(html[-1000:])

# 保存完整HTML
with open('debug_login_page.html', 'w', encoding='utf-8') as f:
    f.write(html)
print()
print("完整HTML已保存到 debug_login_page.html")
