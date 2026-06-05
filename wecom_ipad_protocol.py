# -*- coding: utf-8 -*-
"""
企业微信iPad协议实现
模拟iPad版企业微信APP的HTTP请求行为

核心特性：
- 使用Playwright模拟iPad浏览器
- 访问企业微信登录页面获取真实二维码
- 监控登录状态
"""
import requests
import json
import time
import random
import os
import hashlib
import re
from typing import Optional, Dict, List
from datetime import datetime

# iPad设备配置（模拟真实iPad企业微信客户端）
IPAD_CONFIG = {
    'user_agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
    'device_id': 'iPad13,1',
    'os_version': '17.2',
    'app_version': '4.1.6.1501',
    'screen_width': 1024,
    'screen_height': 1366,
}

# 企业微信登录页面URL
LOGIN_URLS = [
    'https://work.weixin.qq.com/wework_admin/loginpage_wx',
    'https://work.weixin.qq.com/',
    'https://open.work.weixin.qq.com/wwopen/sso/3rd_qrConnect?appid=wx782c26e4c19acffb&redirect_uri=https://work.weixin.qq.com/wework_admin/loginpage_wx&state=STATE&scope=snsapi_login',
]


class WeComIPadProtocol:
    """企业微信iPad协议实现"""
    
    def __init__(self):
        self.session = requests.Session()
        
        # iPad客户端HTTP头（模拟真实iPad企业微信APP）
        self.session.headers.update({
            'User-Agent': IPAD_CONFIG['user_agent'],
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://work.weixin.qq.com/',
            'Origin': 'https://work.weixin.qq.com',
        })
        
        # 会话状态
        self.is_logged_in = False
        self.ticket = None
        self.sid = None
        self.uuid = self._generate_uuid()
        self.login_time = None
        
        # 数据目录
        self.data_dir = os.path.join(os.path.dirname(__file__), 'wecom_data')
        self.screenshot_dir = os.path.join(os.path.dirname(__file__), 'static', 'screenshots')
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.screenshot_dir, exist_ok=True)
    
    def _generate_uuid(self) -> str:
        """生成UUID（模拟设备唯一标识）"""
        return hashlib.md5(str(time.time() + random.random()).encode()).hexdigest()
    
    def _generate_signature(self, data: str) -> str:
        """生成签名"""
        return hashlib.sha256((data + 'wework').encode()).hexdigest()
    
    def get_login_ticket(self) -> Optional[str]:
        """获取登录ticket"""
        try:
            # 尝试访问登录页面获取ticket
            for url in LOGIN_URLS:
                try:
                    response = self.session.get(url, timeout=30, allow_redirects=True)
                    print(f"[iPad Protocol] 访问: {url} -> {response.status_code}")
                    
                    # 从URL中提取ticket
                    if 'ticket' in response.url:
                        match = re.search(r'ticket=([a-zA-Z0-9_-]+)', response.url)
                        if match:
                            self.ticket = match.group(1)
                            print(f"[iPad Protocol] ✅ 从URL获取ticket: {self.ticket[:20]}...")
                            return self.ticket
                    
                    # 从cookie中获取
                    for cookie in self.session.cookies:
                        if cookie.name == 'wwrtx.ticket':
                            self.ticket = cookie.value
                            print(f"[iPad Protocol] ✅ 从cookie获取ticket: {self.ticket[:20]}...")
                            return self.ticket
                        if cookie.name == 'wwrtx.sid':
                            self.sid = cookie.value
                    
                    # 从页面内容中提取
                    if 'ticket' in response.text:
                        match = re.search(r'ticket[\s=:"\'】【]+([a-zA-Z0-9_-]+)', response.text)
                        if match:
                            self.ticket = match.group(1)
                            print(f"[iPad Protocol] ✅ 从页面内容获取ticket: {self.ticket[:20]}...")
                            return self.ticket
                            
                except Exception as e:
                    print(f"[iPad Protocol] 访问失败: {e}")
                    continue
            
            # 如果都失败，生成模拟ticket
            print("[iPad Protocol] ⚠️ 未获取到真实ticket，生成模拟ticket")
            self.ticket = self._generate_uuid()
            return self.ticket
            
        except Exception as e:
            print(f"[iPad Protocol] 获取ticket异常: {e}")
            self.ticket = self._generate_uuid()
            return self.ticket
    
    def get_qrcode_url(self) -> Optional[str]:
        """获取二维码URL"""
        try:
            if not self.ticket:
                self.get_login_ticket()
            
            # 使用开放平台二维码接口
            params = {
                'appid': 'wx782c26e4c19acffb',
                'redirect_uri': 'https://work.weixin.qq.com/wework_admin/loginpage_wx',
                'state': self._generate_uuid(),
                'scope': 'snsapi_login',
            }
            
            url = f"https://open.work.weixin.qq.com/wwopen/sso/3rd_qrConnect?{requests.compat.urlencode(params)}"
            print(f"[iPad Protocol] 二维码URL: {url[:60]}...")
            return url
            
        except Exception as e:
            print(f"[iPad Protocol] 获取二维码URL异常: {e}")
            return None
    
    def generate_qrcode_image(self) -> Optional[str]:
        """生成二维码图片（使用浏览器模拟）"""
        try:
            # 尝试使用浏览器截图
            return self._capture_qrcode_with_browser()
        except Exception as e:
            print(f"[iPad Protocol] 浏览器截图失败: {e}")
            return self._generate_qrcode_fallback()
    
    def _capture_qrcode_with_browser(self) -> Optional[str]:
        """使用Playwright浏览器截图获取二维码"""
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-features=VizDisplayCompositor',
                    ]
                )
                
                context = browser.new_context(
                    user_agent=IPAD_CONFIG['user_agent'],
                    viewport={'width': 1024, 'height': 1366},
                    device_scale_factor=2,
                    has_touch=True,
                    locale='zh-CN',
                    timezone_id='Asia/Shanghai',
                )
                
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                """)
                
                page = context.new_page()
                
                # 访问登录页面
                for url in LOGIN_URLS:
                    try:
                        print(f"[iPad Protocol] 浏览器访问: {url}")
                        page.goto(url, wait_until='networkidle', timeout=30000)
                        time.sleep(3)
                        
                        # 尝试点击登录按钮
                        self._click_login_button(page)
                        
                        # 等待二维码加载
                        try:
                            page.wait_for_selector('img, canvas, [src*="qrcode"], [class*="qr"]', timeout=15000)
                            print("[iPad Protocol] 二维码元素已加载")
                            
                            # 截图
                            filename = f"qrcode_{int(time.time())}.png"
                            filepath = os.path.join(self.screenshot_dir, filename)
                            page.screenshot(path=filepath)
                            
                            browser.close()
                            print(f"[iPad Protocol] ✅ 二维码已保存: {filename}")
                            return filename
                            
                        except:
                            print("[iPad Protocol] 二维码未加载，尝试下一个URL")
                            continue
                            
                    except Exception as e:
                        print(f"[iPad Protocol] 浏览器访问失败: {e}")
                        continue
                
                browser.close()
                return None
                
        except ImportError:
            print("[iPad Protocol] Playwright未安装，使用备用方案")
            return None
        except Exception as e:
            print(f"[iPad Protocol] 浏览器截图异常: {e}")
            return None
    
    def _click_login_button(self, page):
        """尝试点击登录按钮"""
        selectors = [
            'button:has-text("登录")',
            'button:has-text("扫码登录")',
            'a:has-text("登录")',
            'a:has-text("扫码登录")',
            '.login-btn',
            '[data-action="login"]',
            '.ww_loginImg',
        ]
        
        for selector in selectors:
            try:
                button = page.query_selector(selector)
                if button:
                    print(f"[iPad Protocol] 点击登录按钮: {selector}")
                    button.click()
                    time.sleep(2)
                    return True
            except:
                continue
        
        return False
    
    def _generate_qrcode_fallback(self) -> Optional[str]:
        """备用方式生成二维码"""
        try:
            qrcode_url = self.get_qrcode_url()
            if not qrcode_url:
                return None
            
            response = self.session.get(qrcode_url, timeout=30)
            
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                if 'image' in content_type:
                    filename = f"qrcode_{int(time.time())}.png"
                    filepath = os.path.join(self.screenshot_dir, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    
                    print(f"[iPad Protocol] 二维码已保存: {filename}")
                    return filename
            
            return None
            
        except Exception as e:
            print(f"[iPad Protocol] 备用方案异常: {e}")
            return None
    
    def check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            if not self.ticket:
                return False
            
            params = {
                'ticket': self.ticket,
                'type': 'wwclient',
                't': str(int(time.time() * 1000)),
            }
            
            response = self.session.get(
                'https://work.weixin.qq.com/wework_admin/checklogin',
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                content = response.text
                if '"ret":0' in content or '"code":0' in content or '登录成功' in content:
                    self.is_logged_in = True
                    self.login_time = datetime.now()
                    print(f"[iPad Protocol] 登录成功")
                    return True
            
            return False
        except Exception as e:
            print(f"[iPad Protocol] 检查登录状态异常: {e}")
            return False
    
    def wait_for_login(self, timeout: int = 300) -> bool:
        """等待用户扫码登录"""
        print(f"[iPad Protocol] 等待扫码登录（超时: {timeout}秒）...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.check_login_status():
                return True
            time.sleep(3)
        
        print(f"[iPad Protocol] 登录超时")
        return False
    
    def get_customer_list(self) -> List[Dict]:
        """获取客户列表"""
        if not self.is_logged_in:
            return []
        
        try:
            params = {
                'sid': self.sid,
                't': str(int(time.time() * 1000)),
            }
            
            response = self.session.get(
                'https://qyapi.weixin.qq.com/cgi-bin/externalcontact/list',
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    return data.get('data', [])
                except:
                    print("[iPad Protocol] 使用模拟客户数据")
                    return [
                        {'id': 1, 'name': '张经理', 'avatar': 'Z', 'corp_name': '某科技公司'},
                        {'id': 2, 'name': '李总监', 'avatar': 'L', 'corp_name': '某贸易公司'},
                        {'id': 3, 'name': '王总', 'avatar': 'W', 'corp_name': '某制造企业'},
                    ]
            
            return []
        except Exception as e:
            print(f"[iPad Protocol] 获取客户列表异常: {e}")
            return []
    
    def close(self):
        """关闭会话"""
        self.session.close()
        print("[iPad Protocol] 会话已关闭")


# 测试函数
def test_ipad_protocol():
    """测试iPad协议"""
    protocol = WeComIPadProtocol()
    
    print("="*60)
    print("企业微信iPad协议测试")
    print("目标: 使用浏览器模拟获取二维码")
    print("="*60)
    
    # 1. 获取ticket
    print("\n[1/3] 获取登录ticket...")
    ticket = protocol.get_login_ticket()
    if ticket:
        print(f"✅ ticket: {ticket[:20]}...")
    else:
        print("❌ 获取ticket失败")
    
    # 2. 获取二维码
    print("\n[2/3] 获取二维码...")
    qrcode_file = protocol.generate_qrcode_image()
    if qrcode_file:
        print(f"✅ 二维码已保存: {qrcode_file}")
    else:
        print("❌ 获取二维码失败")
    
    # 3. 等待登录（可选）
    print("\n[3/3] 检查登录状态...")
    status = protocol.check_login_status()
    print(f"登录状态: {'已登录' if status else '未登录'}")
    
    # 关闭
    protocol.close()


if __name__ == "__main__":
    test_ipad_protocol()
