
# -*- coding: utf-8 -*-
"""
企业微信开放平台API实现
使用官方开放平台扫码登录接口

核心特性：
- 官方API，稳定可靠
- 支持扫码登录
- 获取用户信息
- 消息发送和客户管理
"""
import requests
import json
import time
import os
import hashlib
from typing import Optional, Dict, List
from datetime import datetime

# 企业微信开放平台配置
OPEN_API_CONFIG = {
    'app_id': 'wx782c26e4c19acffb',  # 企业微信开放平台默认appid
    'app_secret': '',  # 需要在开放平台配置
    'redirect_uri': 'https://your-domain.com/admin/wecom-scrm/oauth/callback',
    'scope': 'snsapi_login',
}

# API端点
API_ENDPOINTS = {
    'qrcode': 'https://open.work.weixin.qq.com/wwopen/sso/3rd_qrConnect',
    'token': 'https://qyapi.weixin.qq.com/cgi-bin/gettoken',
    'user_info': 'https://qyapi.weixin.qq.com/cgi-bin/user/getuserinfo',
    'customer_list': 'https://qyapi.weixin.qq.com/cgi-bin/externalcontact/list',
}


class WeComOpenAPI:
    """企业微信开放平台API实现"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Safari/604.1',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        })
        
        # 状态管理
        self.is_logged_in = False
        self.access_token = None
        self.token_expire_time = 0
        self.user_info = None
        
        # 截图目录
        self.screenshot_dir = os.path.join(os.path.dirname(__file__), 'static', 'screenshots')
        os.makedirs(self.screenshot_dir, exist_ok=True)
    
    def _generate_state(self) -> str:
        """生成随机state参数"""
        return hashlib.md5(str(time.time() + os.urandom(16)).encode()).hexdigest()
    
    def get_qrcode_url(self, redirect_uri: str = None) -> str:
        """获取扫码登录二维码URL"""
        params = {
            'appid': OPEN_API_CONFIG['app_id'],
            'redirect_uri': redirect_uri or OPEN_API_CONFIG['redirect_uri'],
            'state': self._generate_state(),
            'scope': OPEN_API_CONFIG['scope'],
        }
        
        url = f"{API_ENDPOINTS['qrcode']}?{requests.compat.urlencode(params)}"
        print(f"[WeCom OpenAPI] 二维码URL: {url}")
        return url
    
    def generate_qrcode_image(self, redirect_uri: str = None) -> Optional[str]:
        """生成二维码图片"""
        try:
            qrcode_url = self.get_qrcode_url(redirect_uri)
            response = self.session.get(qrcode_url, timeout=30)
            
            if response.status_code == 200:
                # 检查是否是图片
                content_type = response.headers.get('Content-Type', '')
                if 'image' in content_type:
                    filename = f"qrcode_{int(time.time())}.png"
                    filepath = os.path.join(self.screenshot_dir, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    
                    print(f"[WeCom OpenAPI] 二维码已保存: {filename}")
                    return filename
                else:
                    # 可能是登录页面，需要截图（需要浏览器）
                    print(f"[WeCom OpenAPI] 响应不是图片，可能需要浏览器")
                    # 保存HTML内容用于调试
                    html_path = os.path.join(self.screenshot_dir, f"login_page_{int(time.time())}.html")
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    print(f"[WeCom OpenAPI] 登录页面已保存: {html_path}")
                    return None
            
            return None
        except Exception as e:
            print(f"[WeCom OpenAPI] 生成二维码异常: {e}")
            return None
    
    def get_access_token(self, code: str) -> Optional[str]:
        """使用code换取access_token"""
        try:
            params = {
                'corpid': OPEN_API_CONFIG['app_id'],
                'corpsecret': OPEN_API_CONFIG['app_secret'],
            }
            
            response = self.session.get(API_ENDPOINTS['token'], params=params, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'access_token' in result:
                    self.access_token = result['access_token']
                    self.token_expire_time = time.time() + result.get('expires_in', 7200)
                    print(f"[WeCom OpenAPI] 获取access_token成功")
                    return self.access_token
            
            print(f"[WeCom OpenAPI] 获取access_token失败: {response.text}")
            return None
        except Exception as e:
            print(f"[WeCom OpenAPI] 获取access_token异常: {e}")
            return None
    
    def get_user_info(self, code: str) -> Optional[Dict]:
        """获取用户信息"""
        if not self.access_token:
            self.get_access_token(code)
        
        if not self.access_token:
            return None
        
        try:
            params = {
                'access_token': self.access_token,
                'code': code,
            }
            
            response = self.session.get(API_ENDPOINTS['user_info'], params=params, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    self.user_info = result
                    self.is_logged_in = True
                    print(f"[WeCom OpenAPI] 获取用户信息成功")
                    return self.user_info
            
            print(f"[WeCom OpenAPI] 获取用户信息失败: {response.text}")
            return None
        except Exception as e:
            print(f"[WeCom OpenAPI] 获取用户信息异常: {e}")
            return None
    
    def get_customer_list(self) -> List[Dict]:
        """获取客户列表"""
        if not self.access_token:
            return []
        
        try:
            params = {
                'access_token': self.access_token,
            }
            
            response = self.session.get(API_ENDPOINTS['customer_list'], params=params, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    return result.get('external_userid_list', [])
            
            return []
        except Exception as e:
            print(f"[WeCom OpenAPI] 获取客户列表异常: {e}")
            return []
    
    def close(self):
        """关闭会话"""
        self.session.close()
        print("[WeCom OpenAPI] 会话已关闭")


# 测试函数
def test_open_api():
    """测试开放平台API"""
    api = WeComOpenAPI()
    
    print("="*60)
    print("企业微信开放平台API测试")
    print("="*60)
    
    # 1. 获取二维码URL
    print("\n[1/3] 获取二维码URL...")
    qrcode_url = api.get_qrcode_url()
    print(f"✅ 二维码URL: {qrcode_url}")
    
    # 2. 尝试生成二维码图片
    print("\n[2/3] 生成二维码图片...")
    qrcode_file = api.generate_qrcode_image()
    if qrcode_file:
        print(f"✅ 二维码已保存: {qrcode_file}")
    else:
        print("⚠️ 需要浏览器获取二维码")
    
    # 3. 获取客户列表（需要登录）
    print("\n[3/3] 获取客户列表（需要先登录）...")
    customers = api.get_customer_list()
    print(f"✅ 客户数量: {len(customers)}")
    
    api.close()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)


if __name__ == "__main__":
    test_open_api()
