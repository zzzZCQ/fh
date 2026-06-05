
# -*- coding: utf-8 -*-
"""
企业微信iPad浏览器模拟器
使用Playwright模拟iPad浏览器访问企业微信网页版

核心特性：
- 模拟iPad设备（User-Agent、分辨率、触摸支持）
- 访问企业微信管理后台登录页面
- 自动截取二维码并返回
- 监控登录状态
"""
from playwright.sync_api import sync_playwright
import time
import os
import random
from datetime import datetime

# iPad配置
IPAD_CONFIG = {
    'user_agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
    'viewport': {'width': 1024, 'height': 1366},
    'device_scale_factor': 2,
    'has_touch': True,
}

# 企业微信登录页面
LOGIN_URLS = [
    'https://work.weixin.qq.com/',
    'https://work.weixin.qq.com/wework_admin/',
    'https://work.weixin.qq.com/wework_admin/loginpage_wx',
]


class WeComIPadBot:
    """企业微信iPad浏览器模拟器"""
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.is_logged_in = False
        self.login_time = None
        
        # 截图目录
        self.screenshot_dir = os.path.join(os.path.dirname(__file__), 'static', 'screenshots')
        os.makedirs(self.screenshot_dir, exist_ok=True)
    
    def launch(self, headless=False):
        """启动浏览器"""
        try:
            playwright = sync_playwright().start()
            self.browser = playwright.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=VizDisplayCompositor',
                ]
            )
            
            # 创建iPad上下文
            self.context = self.browser.new_context(
                user_agent=IPAD_CONFIG['user_agent'],
                viewport=IPAD_CONFIG['viewport'],
                device_scale_factor=IPAD_CONFIG['device_scale_factor'],
                has_touch=IPAD_CONFIG['has_touch'],
                locale='zh-CN',
                timezone_id='Asia/Shanghai',
            )
            
            # 禁用自动化检测
            self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            self.page = self.context.new_page()
            print("[iPad Bot] ✅ 浏览器启动成功")
            return True
        except Exception as e:
            print(f"[iPad Bot] ❌ 浏览器启动失败: {e}")
            return False
    
    def open_login_page(self):
        """打开企业微信登录页面"""
        print("[iPad Bot] 打开登录页面...")
        
        for url in LOGIN_URLS:
            try:
                print(f"[iPad Bot] 尝试: {url}")
                self.page.goto(url, wait_until='networkidle', timeout=30000)
                self._human_delay(5.0, 8.0)
                
                title = self.page.title()
                print(f"[iPad Bot] 页面标题: {title}")
                
                # 检查是否是404
                if '404' in title or '页面不存在' in title:
                    print(f"[iPad Bot] ✗ 页面不存在")
                    continue
                
                # 尝试查找登录按钮
                self._try_click_login_button()
                
                # 等待二维码加载
                try:
                    self.page.wait_for_selector(
                        'img, canvas, [src*="qrcode"], [class*="qr"]',
                        timeout=20000
                    )
                    print("[iPad Bot] ✅ 登录页面加载成功")
                    return True
                except:
                    print("[iPad Bot] ✗ 二维码未加载，尝试刷新...")
                    self.page.reload()
                    self._human_delay(5.0, 8.0)
                    
                    try:
                        self.page.wait_for_selector(
                            'img, canvas, [src*="qrcode"]',
                            timeout=15000
                        )
                        print("[iPad Bot] ✅ 刷新后二维码加载成功")
                        return True
                    except:
                        continue
            except Exception as e:
                print(f"[iPad Bot] 访问失败: {e}")
                continue
        
        print("[iPad Bot] ❌ 无法打开登录页面")
        return False
    
    def _try_click_login_button(self):
        """尝试点击登录按钮"""
        selectors = [
            'button:has-text("登录")',
            'button:has-text("扫码登录")',
            'a:has-text("登录")',
            'a:has-text("扫码登录")',
            '.login-btn',
            '[data-action="login"]',
        ]
        
        for selector in selectors:
            try:
                button = self.page.query_selector(selector)
                if button:
                    print(f"[iPad Bot] 找到登录按钮: {selector}")
                    button.click()
                    self._human_delay(2.0, 3.0)
                    return True
            except:
                continue
        
        return False
    
    def _human_delay(self, min_sec=2.0, max_sec=5.0):
        """模拟人类操作延迟"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
    def capture_qrcode(self):
        """截取二维码图片"""
        try:
            # 等待二维码元素
            try:
                self.page.wait_for_selector('img, canvas', timeout=10000)
            except:
                pass
            
            # 截取整个页面
            filename = f"qrcode_{int(time.time())}.png"
            filepath = os.path.join(self.screenshot_dir, filename)
            
            self.page.screenshot(path=filepath)
            print(f"[iPad Bot] ✅ 二维码截图已保存: {filename}")
            return filename
        except Exception as e:
            print(f"[iPad Bot] ❌ 截图失败: {e}")
            return None
    
    def check_login_status(self):
        """检查登录状态"""
        try:
            # 检查是否跳转到主页面
            current_url = self.page.url
            title = self.page.title()
            
            # 判断是否登录成功
            if 'login' not in current_url.lower() and 'qrcode' not in current_url.lower():
                self.is_logged_in = True
                self.login_time = datetime.now()
                print(f"[iPad Bot] ✅ 登录成功！当前URL: {current_url}")
                return True
            
            return False
        except Exception as e:
            print(f"[iPad Bot] 检查登录状态失败: {e}")
            return False
    
    def wait_for_login(self, timeout=300):
        """等待用户扫码登录"""
        print(f"[iPad Bot] 等待扫码登录（超时: {timeout}秒）...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.check_login_status():
                return True
            
            # 重新截取二维码（可能已过期）
            self.capture_qrcode()
            self._human_delay(3.0, 5.0)
        
        print("[iPad Bot] ❌ 登录超时")
        return False
    
    def get_customer_list(self):
        """获取客户列表（模拟数据）"""
        if not self.is_logged_in:
            return []
        
        print("[iPad Bot] 获取客户列表...")
        return [
            {'id': 1, 'name': '张经理', 'avatar': 'Z', 'corp_name': '某科技公司'},
            {'id': 2, 'name': '李总监', 'avatar': 'L', 'corp_name': '某贸易公司'},
            {'id': 3, 'name': '王总', 'avatar': 'W', 'corp_name': '某制造企业'},
        ]
    
    def close(self):
        """关闭浏览器"""
        if self.browser:
            self.browser.close()
            print("[iPad Bot] ✅ 浏览器已关闭")


# 测试函数
def test_ipad_bot():
    """测试iPad浏览器模拟器"""
    bot = WeComIPadBot()
    
    print("="*60)
    print("企业微信iPad浏览器模拟器测试")
    print("="*60)
    
    # 1. 启动浏览器
    print("\n[1/4] 启动浏览器...")
    if bot.launch(headless=False):
        print("✅ 浏览器启动成功")
    else:
        print("❌ 浏览器启动失败")
        return
    
    # 2. 打开登录页面
    print("\n[2/4] 打开登录页面...")
    if bot.open_login_page():
        print("✅ 登录页面打开成功")
    else:
        print("❌ 登录页面打开失败")
        bot.close()
        return
    
    # 3. 截取二维码
    print("\n[3/4] 截取二维码...")
    qrcode_file = bot.capture_qrcode()
    if qrcode_file:
        print(f"✅ 二维码已保存: {qrcode_file}")
    else:
        print("❌ 截取二维码失败")
    
    # 4. 等待登录
    print("\n[4/4] 等待扫码登录（60秒）...")
    print("👉 请用手机企业微信扫描二维码")
    success = bot.wait_for_login(timeout=60)
    
    if success:
        print("\n✅ 登录成功！")
        print("✅ 客户列表:", bot.get_customer_list())
    else:
        print("\n❌ 登录失败或超时")
    
    # 关闭浏览器
    bot.close()


if __name__ == "__main__":
    test_ipad_bot()
