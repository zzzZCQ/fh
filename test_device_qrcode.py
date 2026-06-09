# -*- coding: utf-8 -*-
"""测试企业微信设备登录二维码 API"""
import requests
import json

# 这是官方文档中的设备登录二维码接口
# 需要企业的 corpid 和 corpsecret

# 测试使用公开的测试数据（实际使用需要企业自己的凭证）
CORP_ID = 'ww7f0d208d43a9a388'  # 示例企业ID
CORP_SECRET = ''  # 需要企业自己的 secret

def test_device_qrcode():
    # 1. 获取 access_token
    token_url = f'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CORP_ID}&corpsecret={CORP_SECRET}'
    try:
        resp = requests.get(token_url, timeout=15)
        data = resp.json()
        if data.get('access_token'):
            access_token = data['access_token']
            print(f'获取 access_token 成功')
            
            # 2. 获取设备登录二维码
            qr_url = f'https://qyapi.weixin.qq.com/cgi-bin/login/qrcode?access_token={access_token}'
            qr_data = {
                'action_name': 'QRCODE_TYPE_LOGIN',
                'action_info': {
                    'scene': {
                        'scene_str': 'test_device_login'
                    }
                }
            }
            qr_resp = requests.post(qr_url, json=qr_data, timeout=15)
            qr_result = qr_resp.json()
            print(f'二维码响应: {json.dumps(qr_result, ensure_ascii=False)}')
            
            if qr_result.get('ticket'):
                # 3. 获取二维码图片
                img_url = f'https://qyapi.weixin.qq.com/cgi-bin/showqrcode?ticket={qr_result["ticket"]}'
                img_resp = requests.get(img_url, timeout=15)
                if img_resp.content[:4] == b'\x89PNG':
                    with open('d:/fh/test_device_qr.png', 'wb') as f:
                        f.write(img_resp.content)
                    print('设备登录二维码已保存')
        else:
            print(f'获取 access_token 失败: {data.get("errmsg")}')
    except Exception as e:
        print(f'错误: {e}')

if __name__ == '__main__':
    test_device_qrcode()
    
    # 同时测试企业微信网页版的二维码
    print('\n=== 测试企业微信网页版二维码 ===')
    session = requests.Session()
    ua = 'Mozilla/5.0 (iPad; CPU OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'
    
    # 访问企业微信网页版登录页
    resp = session.get('https://work.weixin.qq.com/wework_admin/loginpage_wx', headers={'User-Agent': ua}, timeout=15)
    print(f'登录页状态: {resp.status_code}')
    
    # 查找 iframe
    import re
    iframe_match = re.search(r'<iframe[^>]*src=["\']([^"\']+)["\']', resp.text)
    if iframe_match:
        iframe_url = iframe_match.group(1)
        if not iframe_url.startswith('http'):
            iframe_url = 'https://work.weixin.qq.com' + iframe_url
        print(f'iframe URL: {iframe_url}')
        
        # 访问 iframe
        iframe_resp = session.get(iframe_url, headers={'User-Agent': ua}, timeout=15)
        print(f'iframe 状态: {iframe_resp.status_code}')
        
        # 检查是否是图片
        if iframe_resp.content[:4] == b'\x89PNG':
            print('iframe 返回的是 PNG 图片')
            with open('d:/fh/test_web_qr.png', 'wb') as f:
                f.write(iframe_resp.content)
            print('网页版二维码已保存')