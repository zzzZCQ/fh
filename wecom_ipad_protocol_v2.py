# -*- coding: utf-8 -*-
"""
企业微信 iPad 协议 V2 - 纯 HTTP 实现（无需 Playwright）
======================================================

核心原理（逆向 iPad APP 通信协议）：
1. 访问企微登录页，获取登录二维码（base64 PNG）
2. 轮询检查扫码状态（pending → scanned → success）
3. 扫码确认后，从 cookie/响应中提取 session 凭证（wwrtx.sid / uin / skey 等）
4. 持凭证调用企微 API 发消息、获取联系人/群

为什么不用 Playwright：
- DOM 选择器脆弱，企微页面改版即失效
- 占用大量内存，每个账号一个浏览器实例
- 无法跨服务器部署

纯 HTTP 方案优势：
- 轻量，可并发无限账号
- 不依赖浏览器，只依赖 requests 库
- 凭证直接获取，不受前端页面结构影响
"""

import os
import sys
import time
import json
import re
import threading
import random
import hashlib
import base64
import urllib.parse
from typing import Optional, Dict, List, Callable, Any, Tuple
from datetime import datetime


# ============================================================
# 常量
# ============================================================

# iPad 设备信息（逆向自真实 iPad 企业微信 APP）
IPAD_DEVICE_INFO = {
    'device_name': 'iPad Pro',
    'device_model': 'iPad13,1',
    'os_version': '17.5.1',
    'app_version': '4.1.8.2612',       # 需与企微版本同步更新
    'wechat_version': '8.0.48',
    'screen_width': 1024,
    'screen_height': 1366,
    'scale': 2.0,
}

# iPad Safari UA（模拟真实 iPad 客户端）
IPAD_UA = (
    f"Mozilla/5.0 (iPad; CPU OS {IPAD_DEVICE_INFO['os_version']} like Mac OS X) "
    f"AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
    f"Mobile/15E148 Safari/604.1"
)

# 企微 iPad APP UA
IPAD_APP_UA = (
    f"Mozilla/5.0 (iPad; CPU OS {IPAD_DEVICE_INFO['os_version']} like Mac OS X) "
    f"AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    f"MicroMessenger/{IPAD_DEVICE_INFO['wechat_version']} "
    f"NetType/WIFI Language/zh_CN"
)

# 消息类型
MESSAGE_TYPES = {
    'text': 1,
    'image': 3,
    'voice': 34,
    'video': 43,
    'file': 49,
    'emotion': 47,
}

# 登录状态
LOGIN_STATUS_PENDING = 'pending'
LOGIN_STATUS_SCANNED = 'scanned'
LOGIN_STATUS_SUCCESS = 'success'
LOGIN_STATUS_EXPIRED = 'expired'
LOGIN_STATUS_FAILED = 'failed'


# ============================================================
# 工具函数
# ============================================================

def _gen_device_id() -> str:
    """生成 iPad 设备标识（16位 e 开头）"""
    return f"e{hashlib.md5(str(time.time()).encode()).hexdigest()[:15]}"


def _gen_uuid() -> str:
    """生成 UUID"""
    return hashlib.md5(f"{time.time()}{random.randint(1000, 9999)}".encode()).hexdigest()


def _gen_msg_id() -> str:
    """生成消息 ID"""
    return f"{int(time.time() * 1000)}{random.randint(100000, 999999)}"


def _gen_client_msg_id() -> str:
    """生成客户端消息 ID"""
    return f"{int(time.time() * 1000)}{random.randint(1000, 9999)}"


# ============================================================
# SyncKey
# ============================================================

class SyncKey:
    """同步密钥"""

    def __init__(self, data: Optional[Dict] = None):
        self.keys: List[Dict] = []
        self.list_str: str = ''
        if data:
            self._from_dict(data)

    def _from_dict(self, data: Dict):
        self.keys = data.get('List', [])
        self.list_str = '|'.join(f"{k['Key']}_{k['Val']}" for k in self.keys)

    def to_dict(self) -> Dict:
        return {'Count': len(self.keys), 'List': self.keys}


# ============================================================
# 企业微信 iPad 协议 V2
# ============================================================

class WeComIPadProtocolV2:
    """
    企业微信 iPad 协议 V2（纯 HTTP 实现）

    与 V1（Playwright）的区别：
    - V1: 启动浏览器模拟操作网页，依赖 DOM 结构
    - V2: 直接调用企微 API，凭证驱动，不依赖前端页面

    登录流程（完整）：
    Step 1: GET https://work.weixin.qq.com/wework_admin/loginpage_wx
            → 从 HTML 中提取二维码 base64 PNG

    Step 2: 轮询 GET https://work.weixin.qq.com/wework_admin/loginpage_wx?fun=login&uuid=xxx&cd=&ralateUid=
            → 检测 QR 扫码状态（pending/scanned/success）

    Step 3: 扫码确认后，从 Cookie + 后续请求中提取：
            wwrtx.sid / wwrtx.vid / skey / pass_ticket / uin

    Step 4: 持凭证调用 API（发消息、获取联系人等）
    """

    # 企微 API 端点
    _BASE_URL = 'https://work.weixin.qq.com'
    _API_BASE = 'https://qyapi.weixin.qq.com'
    _CDN_BASE = 'https://file.work.weixin.qq.com'

    def __init__(self):
        self._reset()

        import requests
        self._requests = requests.Session()

        # iPad Safari UA（用于扫码登录页）
        self._requests.headers.update({
            'User-Agent': IPAD_UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://work.weixin.qq.com/',
        })

        # 状态
        self._login_uuid: str = ''
        self._login_page_html: str = ''
        self._qrcode_key: str = ''  # wwclient 类型登录的 key
        self._poll_thread: Optional[threading.Thread] = None
        self._poll_running: bool = False
        self._poll_lock = threading.Lock()

        # 回调
        self._callbacks: Dict[int, List[Callable]] = {}
        self._sync_thread: Optional[threading.Thread] = None
        self._sync_running: bool = False

        print(f'[iPad V2] 初始化完成，设备ID: {self.device_id}')

    def _reset(self):
        self.is_login = False
        self.uin: Optional[str] = None
        self.wxid: Optional[str] = None
        self.user_name: Optional[str] = None
        self.skey: Optional[str] = None
        self.sid: Optional[str] = None
        self.sync_key = SyncKey()
        self.pass_ticket: Optional[str] = None
        self.device_id = _gen_device_id()
        self.uuid = _gen_uuid()
        self.status = LOGIN_STATUS_PENDING
        self.error_msg: str = ''
        self.login_info: Dict = {}
        self._cookies: Dict[str, str] = {}
        self._raw_cookies: List[Dict] = []

    # ==================== Step 1: 获取二维码 ====================

    def fetch_qrcode(self) -> Tuple[bool, str, Optional[str]]:
        """
        Step 1: 获取登录二维码

        Returns:
            (success, error_msg, qrcode_base64_png)
            qrcode_base64_png: data:image/png;base64,xxxx 格式
        """
        self._reset()
        self.status = LOGIN_STATUS_PENDING

        try:
            # 企微扫码登录页（iPad 视角）
            login_url = 'https://work.weixin.qq.com/wework_admin/loginpage_wx'

            resp = self._requests.get(login_url, timeout=30)
            if resp.status_code != 200:
                return False, f'访问登录页失败: HTTP {resp.status_code}', None

            html = resp.text
            self._login_page_html = html

            # 从 HTML 中提取二维码（data:image/png;base64,... 格式）
            qrcode = self._extract_qrcode_from_html(html)
            if qrcode:
                print(f'[iPad V2] 提取到二维码，长度: {len(qrcode)}')
                uuid_match = re.search(r'uuid["\s:=]+["\']?([a-zA-Z0-9_-]+)', html)
                if uuid_match:
                    self._login_uuid = uuid_match.group(1)
                    print(f'[iPad V2] 登录 UUID: {self._login_uuid}')
                return True, '', qrcode

            # 企微新版：二维码在 iframe 中动态加载（已验证可行，优先尝试）
            qrcode_iframe = self._extract_qrcode_from_iframe()
            if qrcode_iframe:
                return True, '', qrcode_iframe

            # 备用：企微新版使用 JS 生成二维码，需要从 JS 提取
            qrcode_js = self._extract_qrcode_from_js(html, resp.cookies)
            if qrcode_js:
                return True, '', qrcode_js

            # 企微新版：二维码通过 AJAX 获取
            qrcode_ajax = self._fetch_qrcode_ajax()
            if qrcode_ajax:
                return True, '', qrcode_ajax

            # 调试：保存页面内容以便分析
            self._debug_save_html(html)

            return False, '未能提取登录二维码，请稍后重试。已保存调试日志。', None

        except Exception as e:
            self.error_msg = str(e)
            print(f'[iPad V2] 获取二维码异常: {e}')
            return False, str(e), None

    def _debug_save_html(self, html: str):
        """保存登录页面 HTML 用于调试分析"""
        try:
            import os
            debug_dir = os.path.join(os.path.dirname(__file__), 'debug')
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            filename = f'login_page_{int(time.time())}.html'
            filepath = os.path.join(debug_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f'[iPad V2] 登录页面已保存到: {filepath}')
            # 打印关键信息
            print('[iPad V2] === 页面分析 ===')
            print(f'页面长度: {len(html)} 字符')
            # 搜索可能的二维码相关内容
            qr_related = ['qrcode', 'QRCode', 'qr_code', 'qrImage', 'qrimage', 'login_qr']
            for keyword in qr_related:
                count = html.lower().count(keyword.lower())
                if count > 0:
                    print(f'包含 "{keyword}": {count} 次')
        except Exception as e:
            print(f'[iPad V2] 保存调试文件失败: {e}')

    def _extract_qrcode_from_html(self, html: str) -> Optional[str]:
        """从 HTML 中提取 base64 二维码（多种策略）"""
        print('[iPad V2] 尝试从 HTML 提取二维码...')

        # 策略1: 直接匹配 data:image PNG/JPG base64
        patterns = [
            r'data:image/(png|jpeg|jpg);base64,([A-Za-z0-9+/=]{1000,})',
            r'"qrcode"\s*[=:]\s*["\'](data:image/[^"\']+base64,[^"\']+)["\']',
            r'"qr_image"\s*[=:]\s*["\'](data:image/[^"\']+base64,[^"\']+)["\']',
            r'"img"\s*[=:]\s*["\'](data:image/[^"\']+base64,[^"\']+)["\']',
            r'src=["\'](data:image/(png|jpg|jpeg);base64,[A-Za-z0-9+/=]{1000,})["\']',
            r'<img[^>]+src=["\'](data:image/(png|jpg);base64,[^"\']+)["\']',
        ]
        for p in patterns:
            m = re.search(p, html, re.IGNORECASE)
            if m:
                data = m.group(1) if len(m.groups()) == 1 else m.group(2)
                if data and len(data) > 500:
                    if not data.startswith('data:image/'):
                        data = f'data:image/png;base64,{data}'
                    print(f'[iPad V2] 策略1成功，二维码长度: {len(data)}')
                    return data

        # 策略2: 匹配二维码图片 URL 然后下载
        url_patterns = [
            r'qrcode["\s]*[=:]\s*["\']([^"\']+)["\']',
            r'qrimg["\s]*[=:]\s*["\']([^"\']+)["\']',
            r'qrCodeUrl["\s]*[=:]\s*["\']([^"\']+)["\']',
            r'qr_url["\s]*[=:]\s*["\']([^"\']+)["\']',
            r'qrcodeUrl["\s]*[=:]\s*["\']([^"\']+)["\']',
            r'scanqrcode["\s]*[=:]\s*["\']([^"\']+)["\']',
        ]
        for p in url_patterns:
            m = re.search(p, html, re.IGNORECASE)
            if m:
                qr_url = m.group(1)
                try:
                    if not qr_url.startswith('http'):
                        if qr_url.startswith('//'):
                            qr_url = 'https:' + qr_url
                        elif qr_url.startswith('/'):
                            qr_url = self._BASE_URL + qr_url
                    print(f'[iPad V2] 策略2尝试下载: {qr_url[:50]}...')
                    img_resp = self._requests.get(qr_url, timeout=15)
                    if img_resp.status_code == 200 and len(img_resp.content) > 500:
                        return f'data:image/png;base64,{base64.b64encode(img_resp.content).decode()}'
                except Exception as e:
                    print(f'[iPad V2] 策略2失败: {e}')

        # 策略3: 匹配 script 标签中的 JSON 数据
        script_pattern = r'<script[^>]*>([\s\S]*?)</script>'
        for script in re.findall(script_pattern, html):
            if 'qrcode' in script.lower() or 'qr' in script.lower():
                json_match = re.search(r'({[^{}]*qrcode[^}]*})', script)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                        if 'qrcode' in data:
                            qr = data['qrcode']
                            if qr.startswith('data:image') or (len(qr) > 500 and 'base64' not in qr):
                                if not qr.startswith('data:image'):
                                    qr = f'data:image/png;base64,{qr}'
                                print('[iPad V2] 策略3成功')
                                return qr
                    except Exception:
                        pass

        print('[iPad V2] HTML 提取失败')
        return None

    def _extract_qrcode_from_js(self, html: str, cookies) -> Optional[str]:
        """企微新版：二维码通过 JS API 获取，尝试调用"""
        print('[iPad V2] 尝试从 JS API 获取二维码...')
        try:
            appid_match = re.search(r'appid["\s:=]+["\']([^"\']+)["\']', html)
            appid = appid_match.group(1) if appid_match else 'wx782c26e4c19acffb'

            ts = int(time.time() * 1000)

            endpoints = [
                f'https://work.weixin.qq.com/wework_admin/loginqr/qrcode?appid={appid}&_={ts}',
                f'https://work.weixin.qq.com/wework_admin/loginqr/getqrcode?appid={appid}&_={ts}',
                f'https://work.weixin.qq.com/wework_admin/loginpage_wx?fun=new&lang=zh_CN&f=json&ajax=1&_={ts}',
                f'https://work.weixin.qq.com/wework_admin/loginqr/getqrcode?r={ts}&qq=0',
                f'https://work.weixin.qq.com/cgi-bin/loginqr?login_type=pc&uuid=&redirect_url=&state=webwx&_={ts}',
                f'https://work.weixin.qq.com/wwopen/sso/3rd_qr?appid={appid}&redirect_uri=&state={self.device_id}&_={ts}',
                f'https://work.weixin.qq.com/wework_admin/wework_qrcode?action=get_qrcode&random={ts}',
            ]

            for qr_url in endpoints:
                try:
                    print(f'[iPad V2] 尝试: {qr_url[:60]}...')
                    headers = {
                        'Referer': 'https://work.weixin.qq.com/wework_admin/loginpage_wx',
                        'User-Agent': IPAD_UA,
                        'X-Requested-With': 'XMLHttpRequest',
                    }
                    resp = self._requests.get(qr_url, timeout=15, cookies=cookies, headers=headers)
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            if data.get('qrcode'):
                                print('[iPad V2] JS API 获取成功')
                                return data['qrcode']
                            if data.get('image'):
                                return data['image']
                            if data.get('url') and data['url'].startswith('data:image'):
                                return data['url']
                        except Exception:
                            # 不是 JSON，检查是否是真正的图片
                            content = resp.content
                            content_type = resp.headers.get('Content-Type', '').lower()
                            if len(content) > 500:
                                # 检查是否是真正的图片（PNG 或 JPG）
                                is_png = content[:8] == b'\x89PNG\r\n\x1a\n'
                                is_jpg = content[:2] == b'\xff\xd8'
                                if is_png or is_jpg or 'image' in content_type:
                                    return f'data:image/png;base64,{base64.b64encode(content).decode()}'
                                # 如果是 HTML，尝试从中提取
                                content_str = content.decode('utf-8', errors='ignore')
                                if '<html' in content_str[:100]:
                                    qrcode = self._extract_qrcode_from_html(content_str)
                                    if qrcode:
                                        return qrcode
                except Exception as e:
                    print(f'[iPad V2] 尝试失败: {e}')

        except Exception as e:
            print(f'[iPad V2] JS 二维码提取失败: {e}')
        return None

    def _fetch_qrcode_ajax(self) -> Optional[str]:
        """通过 AJAX 接口获取二维码（尝试多种端点）"""
        print('[iPad V2] 尝试 AJAX 获取二维码...')
        ts = int(time.time() * 1000)

        endpoints = [
            f'https://work.weixin.qq.com/wework_admin/loginqr/getqrcode?r={ts}&qq=0',
            f'https://work.weixin.qq.com/cgi-bin/loginqr?login_type=pc&uuid=&redirect_url=&state=webwx&_={ts}',
            f'https://work.weixin.qq.com/wework_admin/loginpage_wx?fun=new&lang=zh_CN',
            f'https://work.weixin.qq.com/wework_admin/wework_qrcode?action=get_qrcode&random={ts}',
            f'https://work.weixin.qq.com/wwopen/sso/3rd_qr?appid=wx782c26e4c19acffb&redirect_uri=&state={self.device_id}&_={ts}',
            f'https://open.work.weixin.qq.com/wwopen/sso/3rd_qr?appid=wx782c26e4c19acffb&redirect_uri=&state={self.device_id}&_={ts}',
        ]

        headers = {
            'User-Agent': IPAD_UA,
            'Referer': 'https://work.weixin.qq.com/wework_admin/loginpage_wx',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

        for url in endpoints:
            try:
                print(f'[iPad V2] AJAX尝试: {url[:60]}...')
                resp = self._requests.get(url, timeout=15, headers=headers)
                if resp.status_code == 200:
                    content = resp.content
                    if len(content) > 500:
                        try:
                            data = resp.json()
                            if data.get('qrcode'):
                                print('[iPad V2] AJAX 获取成功')
                                return data['qrcode']
                            if data.get('image'):
                                return data['image']
                            if data.get('url') and data['url'].startswith('data:image'):
                                return data['url']
                        except Exception:
                            content_type = resp.headers.get('Content-Type', '')
                            if len(content) > 500:
                                # 检查是否是真正的图片（PNG 或 JPG）
                                is_png = content[:8] == b'\x89PNG\r\n\x1a\n'
                                is_jpg = content[:2] == b'\xff\xd8'
                                if is_png or is_jpg or 'image' in content_type:
                                    return f'data:image/png;base64,{base64.b64encode(content).decode()}'
            except Exception as e:
                print(f'[iPad V2] AJAX尝试失败: {e}')

        try:
            mobile_url = 'https://open.work.weixin.qq.com/wwopen/sso/3rd_qr'
            print(f'[iPad V2] 尝试移动端接口: {mobile_url}')
            resp = self._requests.get(mobile_url, timeout=15, headers=headers)
            if resp.status_code == 200:
                html = resp.text
                patterns = [
                    r'data:image/(png|jpg);base64,([A-Za-z0-9+/=]{1000,})',
                    r'"qrcode"\s*[=:]\s*["\'](data:image/[^"\']+)["\']',
                ]
                for p in patterns:
                    m = re.search(p, html)
                    if m:
                        print('[iPad V2] 移动端接口获取成功')
                        return m.group(1) if len(m.groups()) == 1 else m.group(2)
        except Exception as e:
            print(f'[iPad V2] 移动端接口失败: {e}')

        return None

    def _extract_qrcode_from_iframe(self) -> Optional[str]:
        """
        从 iframe 获取二维码（企业微信客户端登录，非管理后台）

        正确流程：
        1. 先获取 login_admin 的 qrcode_key
        2. 用这个 key 获取 wwclient 类型的二维码
        3. 保存 key 用于后续轮询检查
        """
        print('[iPad V2] 尝试从 iframe 获取二维码...')
        try:
            ts = int(time.time() * 1000)
            headers = {
                'User-Agent': IPAD_UA,
                'Referer': 'https://work.weixin.qq.com/wework_admin/loginpage_wx',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'zh-CN,zh;q=0.9',
            }

            # Step 1: 获取 qrcode_key (使用 login_admin 获取 key)
            key_url = f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/get_key?login_type=login_admin&r={ts}'
            key_resp = self._requests.get(key_url, timeout=15, headers=headers)
            if key_resp.status_code != 200:
                print(f'[iPad V2] 获取 qrcode_key 失败: HTTP {key_resp.status_code}')
                return None

            try:
                key_data = key_resp.json()
                qrcode_key = key_data.get('data', {}).get('qrcode_key')
            except Exception:
                qrcode_key = None

            if not qrcode_key:
                print(f'[iPad V2] 未获取到 qrcode_key')
                return None

            # 保存 qrcode_key 用于后续轮询
            self._qrcode_key = qrcode_key
            print(f'[iPad V2] 获取到 qrcode_key: {qrcode_key[:20]}...')

            # Step 2: 使用 qrcode_key 获取 wwclient 类型的二维码
            qr_url = f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/qrcode?qrcode_key={qrcode_key}&login_type=wwclient'
            headers['Accept'] = 'image/png,image/*;q=0.9,*/*;q=0.8'
            qr_resp = self._requests.get(qr_url, timeout=15, headers=headers)

            if qr_resp.status_code == 200 and len(qr_resp.content) > 500:
                content = qr_resp.content
                # 检查是否是真正的图片
                is_png = content[:8] == b'\x89PNG\r\n\x1a\n'
                is_jpg = content[:2] == b'\xff\xd8'
                if is_png or is_jpg:
                    qrcode_data = f'data:image/png;base64,{base64.b64encode(content).decode()}'
                    print(f'[iPad V2] 二维码获取成功，大小: {len(content)} 字节')
                    return qrcode_data
                else:
                    print(f'[iPad V2] 返回不是图片')
                    content_str = content.decode('utf-8', errors='ignore')
                    if '<html' in content_str[:100]:
                        return self._extract_qrcode_from_html(content_str)

            print(f'[iPad V2] 获取二维码失败')
        except Exception as e:
            print(f'[iPad V2] iframe 获取异常: {e}')

        return None

    # ==================== Step 2: 轮询扫码状态 ====================

    def start_poll_login(self):
        """启动后台轮询线程（检测扫码 + 确认）"""
        with self._poll_lock:
            if self._poll_running:
                return
            self._poll_running = True

        self._poll_thread = threading.Thread(target=self._poll_login_loop, daemon=True)
        self._poll_thread.start()

    def _poll_login_loop(self):
        """轮询登录状态"""
        start_time = time.time()

        try:
            while self._poll_running:
                elapsed = time.time() - start_time
                if elapsed > 300:  # 5 分钟超时
                    with self._poll_lock:
                        self.status = LOGIN_STATUS_EXPIRED
                        self.error_msg = '二维码 5 分钟内未扫码，已过期'
                    print('[iPad V2] 登录超时')
                    break

                if self.status in (LOGIN_STATUS_SUCCESS, LOGIN_STATUS_FAILED):
                    break

                # 调用登录检查 API
                new_status, login_data = self._check_login_status()
                with self._poll_lock:
                    self.status = new_status

                if new_status == LOGIN_STATUS_SCANNED:
                    print('[iPad V2] 已扫码，等待确认...')
                elif new_status == LOGIN_STATUS_SUCCESS:
                    self._on_login_success(login_data)
                    print(f'[iPad V2] ✅ 登录成功: {self.login_info.get("name", "未知")}')
                    break

                time.sleep(2)

        except Exception as e:
            print(f'[iPad V2] 轮询异常: {e}')
        finally:
            self._poll_running = False

    def _check_login_status(self) -> Tuple[str, Dict]:
        """
        检查扫码登录状态（使用 wwqrlogin/mng/check 接口）

        Returns:
            (status, login_data)
        """
        try:
            # 如果没有 qrcode_key，无法轮询
            if not self._qrcode_key:
                # 降级：尝试通过 cookies 判断
                return self._check_login_status_by_cookies()

            ts = time.time()
            check_url = f'https://work.weixin.qq.com/wework_admin/wwqrlogin/mng/check?qrcode_key={self._qrcode_key}&status=QRCODE_SCAN_NEVER&r={ts}'

            headers = {
                'User-Agent': IPAD_UA,
                'Referer': 'https://work.weixin.qq.com/wework_admin/loginpage_wx',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
            }

            resp = self._requests.get(check_url, timeout=15, headers=headers)
            all_cookies = dict(self._requests.cookies)
            self._raw_cookies = [{'name': k, 'value': v} for k, v in all_cookies.items()]

            if resp.status_code != 200:
                return LOGIN_STATUS_PENDING, {}

            # 解析响应
            try:
                data = resp.json()
                retcode = data.get('retcode', -1)
                errmsg = data.get('errmsg', '')

                # 从响应中提取凭证
                if 'login_info' in data:
                    login_info = data.get('login_info', {})
                    self.uin = login_info.get('uin') or self.uin
                    self.wxid = login_info.get('wxid') or self.wxid

                # 解析状态
                # retcode: 0 = 已扫码待确认, 403 = 扫码后取消, 其他 = 继续等待
                if retcode == 0:
                    # 已扫码，检查是否已确认（通过 cookie 判断）
                    if self._check_cookies_for_login(all_cookies):
                        return LOGIN_STATUS_SUCCESS, {'login_info': data.get('login_info', {})}
                    return LOGIN_STATUS_SCANNED, {}
                elif retcode == 403 or '取消' in errmsg:
                    return LOGIN_STATUS_FAILED, {}
                elif retcode == -1 or errmsg == 'waiting':
                    return LOGIN_STATUS_PENDING, {}
                else:
                    # 其他状态，继续等待
                    return LOGIN_STATUS_PENDING, {}

            except Exception as e:
                print(f'[iPad V2] 解析 check 响应失败: {e}')
                # 降级：通过 cookies 判断
                return self._check_login_status_by_cookies()

        except Exception as e:
            print(f'[iPad V2] 检查登录状态异常: {e}')
            return LOGIN_STATUS_PENDING, {}

    def _check_login_status_by_cookies(self) -> Tuple[str, Dict]:
        """通过 cookies 判断登录状态（降级方案）"""
        try:
            all_cookies = dict(self._requests.cookies)
            self._raw_cookies = [{'name': k, 'value': v} for k, v in all_cookies.items()]

            # 检查 cookie 中是否出现关键凭证
            has_sid = any('sid' in k.lower() for k in all_cookies.keys())
            has_vid = any('vid' in k.lower() or 'uin' in k.lower() for k in all_cookies.keys())
            has_skey = any('skey' in k.lower() or 'key' in k.lower() for k in all_cookies.keys())

            # 更新凭证
            for k, v in all_cookies.items():
                if k == 'wwrtx.sid':
                    self.sid = v
                elif k == 'wwrtx.vid':
                    self.uin = v
                elif k == 'wwrtx.ticket':
                    self.pass_ticket = v
                elif k == 'ww_skey':
                    self.skey = v
                elif k == 'pass_ticket':
                    self.pass_ticket = v

            if has_sid or has_skey:
                if has_vid or self.uin:
                    return LOGIN_STATUS_SUCCESS, {}

            return LOGIN_STATUS_PENDING, {}
        except Exception:
            return LOGIN_STATUS_PENDING, {}

    def _check_cookies_for_login(self, cookies: Dict) -> bool:
        """检查 cookies 中是否包含登录凭证"""
        has_sid = any('sid' in k.lower() for k in cookies.keys())
        has_vid = any('vid' in k.lower() or 'uin' in k.lower() for k in cookies.keys())
        has_skey = any('skey' in k.lower() or 'key' in k.lower() for k in cookies.keys())
        return (has_sid or has_skey) and (has_vid or self.uin)

    def _parse_login_success_page(self, html: str, cookies: Dict) -> Optional[Dict]:
        """解析登录成功后的页面，提取用户信息"""
        data = {}

        # 提取 skey
        skey_m = re.search(r'skey["\s:=]+["\']([a-zA-Z0-9@_-]+)["\']', html)
        if skey_m:
            self.skey = skey_m.group(1)
            data['skey'] = self.skey

        # 提取 uin
        uin_m = re.search(r'"Uin"\s*:\s*"?(\d+)"?', html)
        if uin_m:
            self.uin = uin_m.group(1)
            data['uin'] = self.uin

        # 提取 wxid / user_name
        wxid_m = re.search(r'"UserName"\s*:\s*"([^"]+)"', html)
        if wxid_m:
            self.wxid = wxid_m.group(1)
            self.user_name = self.wxid
            data['wxid'] = self.wxid

        # 从 cookie 补充
        for k, v in cookies.items():
            if k == 'wwrtx.vid':
                data['user_id'] = v
                self.uin = v
            elif k == 'wxuin':
                data['user_id'] = v
            elif k == 'ww_skey':
                self.skey = v

        # 获取用户信息（通过 API）
        if self.skey and self.sid:
            self._fetch_user_info_from_api(data)

        if data:
            self.is_login = True
            data.setdefault('name', data.get('user_id') or self.wxid or '企微账号')
            self.login_info = data

        return data if data else None

    def _fetch_user_info_from_api(self, data: Dict):
        """登录成功后，通过 API 获取详细用户信息"""
        try:
            params = {
                'access_token': self._get_access_token(),
            }
            resp = self._requests.get(
                f'{self._API_BASE}/cgi-bin/user/get',
                params=params,
                timeout=15,
            )
            if resp.status_code == 200:
                rd = resp.json()
                if rd.get('errcode') == 0:
                    data['corp_name'] = rd.get('corpname', '企业微信')
        except Exception as e:
            print(f'[iPad V2] 获取用户信息 API 失败: {e}')

    def _get_access_token(self) -> Optional[str]:
        """从 cookie 中提取 access_token（简化版）"""
        # 企微的 access_token 通常需要单独获取
        # 简化：优先使用已有的凭证
        return self.skey

    def _on_login_success(self, login_data: Dict):
        """登录成功回调"""
        self.is_login = True
        self.status = LOGIN_STATUS_SUCCESS

        # 从 cookie 再次提取
        all_cookies = dict(self._requests.cookies)
        for k, v in all_cookies.items():
            if k == 'wwrtx.sid':
                self.sid = v
            elif k == 'wwrtx.vid':
                self.uin = v
            elif k == 'wwrtx.ticket':
                self.pass_ticket = v
            elif k == 'ww_skey':
                self.skey = v
            elif k == 'pass_ticket':
                self.pass_ticket = v

        # 构建登录信息
        self.login_info = {
            'name': login_data.get('name') or login_data.get('wxid') or login_data.get('user_id') or self.wxid or '企微账号',
            'user_id': self.uin or login_data.get('user_id') or '',
            'wxid': self.wxid or '',
            'corp_name': login_data.get('corp_name') or '企业微信',
            'skey': self.skey or '',
            'sid': self.sid or '',
            'device_id': self.device_id,
        }

        self._cookies = dict(all_cookies)
        self._raw_cookies = [{'name': k, 'value': v} for k, v in all_cookies.items()]

        print(f'[iPad V2] 登录凭证: uin={self.uin}, skey={self.skey[:8] if self.skey else "N/A"}...')

    def get_login_status(self) -> str:
        """获取当前登录状态（供外部轮询调用）"""
        with self._poll_lock:
            return self.status

    def get_login_info(self) -> Dict:
        return self.login_info or {}

    def get_cookies(self) -> List[Dict]:
        """获取当前 cookies（用于持久化）"""
        return self._raw_cookies

    def load_cookies(self, cookies: List[Dict]):
        """从持久化数据加载 cookies"""
        if not cookies:
            return False
        self._raw_cookies = cookies
        self._cookies = {c['name']: c['value'] for c in cookies}

        # 恢复关键字段
        for c in cookies:
            name, value = c.get('name', ''), c.get('value', '')
            if name == 'wwrtx.sid':
                self.sid = value
            elif name == 'wwrtx.vid':
                self.uin = value
            elif name == 'wwrtx.ticket':
                self.pass_ticket = value
            elif name == 'ww_skey':
                self.skey = value
            elif name == 'pass_ticket':
                self.pass_ticket = value

        if self.sid and self.skey:
            self.is_login = True
            self.status = LOGIN_STATUS_SUCCESS
            return True
        return False

    # ==================== Step 3: 发消息 ====================

    def send_text_message(self, to_user: str, content: str) -> bool:
        """
        发送文本消息

        通过企微管理后台消息 API（基于 cookie 认证）
        """
        if not self.is_login:
            print('[iPad V2] 未登录，无法发送消息')
            return False

        try:
            # 企微消息发送 API
            # 注意：这里使用的是企业微信网页版 API，不是企微 API 接口
            msg_id = _gen_msg_id()

            payload = {
                'BaseRequest': {
                    'Uin': int(self.uin or 0),
                    'Sid': self.sid or '',
                    'Skey': self.skey or '',
                    'DeviceID': self.device_id,
                },
                'Msg': {
                    'Type': MESSAGE_TYPES['text'],
                    'Content': content,
                    'FromUserName': self.wxid or '',
                    'ToUserName': to_user,
                    'LocalID': msg_id,
                    'ClientMsgId': msg_id,
                },
                'Scene': 0,
            }

            # 构造带 cookie 的请求
            self._requests.headers.update({
                'User-Agent': IPAD_APP_UA,
                'Referer': 'https://work.weixin.qq.com/wework_admin/frame',
                'Content-Type': 'application/json; charset=UTF-8',
            })

            params = {'pass_ticket': self.pass_ticket or ''}
            url = f'{self._BASE_URL}/cgi-bin/micromsg-bin/webwxsendmsg'

            resp = self._requests.post(url, params=params, json=payload, timeout=15)
            if resp.status_code == 200:
                try:
                    rd = resp.json()
                    if rd.get('BaseResponse', {}).get('Ret') == 0:
                        print(f'[iPad V2] ✅ 消息发送成功 -> {to_user}: {content[:30]}')
                        return True
                    else:
                        print(f'[iPad V2] 消息发送失败: {rd}')
                except Exception:
                    pass

            return False

        except Exception as e:
            print(f'[iPad V2] 发送消息异常: {e}')
            return False

    # 通过企微应用消息 API（备用）
    def send_message_via_app(self, to_user: str, content: str, agentid: int = 1000000) -> bool:
        """通过企业微信应用消息接口发送（需要 access_token）"""
        if not self.is_login:
            return False
        try:
            # 简化版：使用企微 API 发消息
            url = f'{self._API_BASE}/cgi-bin/message/send'
            params = {'access_token': self.skey or ''}
            payload = {
                'touser': to_user,
                'msgtype': 'text',
                'agentid': agentid,
                'text': {'content': content},
            }
            resp = self._requests.post(url, params=params, json=payload, timeout=15)
            if resp.status_code == 200:
                rd = resp.json()
                return rd.get('errcode') == 0
        except Exception as e:
            print(f'[iPad V2] 应用消息发送失败: {e}')
        return False

    # ==================== Step 4: 联系人/群 ====================

    def get_contact_list(self) -> List[Dict]:
        """获取联系人/客户列表"""
        if not self.is_login:
            return []

        try:
            self._requests.headers['User-Agent'] = IPAD_APP_UA
            params = {
                'r': int(time.time() * 1000),
                'seq': 0,
                'skey': self.skey or '',
            }
            url = f'{self._BASE_URL}/cgi-bin/micromsg-bin/webwxgetcontact'
            resp = self._requests.get(url, params=params, timeout=20)

            if resp.status_code == 200:
                rd = resp.json()
                if rd.get('BaseResponse', {}).get('Ret') == 0:
                    members = rd.get('MemberList', [])
                    return [
                        {
                            'id': m.get('UserName', ''),
                            'name': m.get('NickName', ''),
                            'remark': m.get('RemarkName', ''),
                            'corp_name': m.get('CorpName', ''),
                            'conversation_id': m.get('UserName', ''),
                        }
                        for m in members
                        if m.get('NickName')
                    ]
        except Exception as e:
            print(f'[iPad V2] 获取联系人失败: {e}')
        return []

    def get_room_list(self) -> List[Dict]:
        """获取群列表"""
        if not self.is_login:
            return []

        try:
            self._requests.headers['User-Agent'] = IPAD_APP_UA
            params = {
                'r': int(time.time() * 1000),
                'skey': self.skey or '',
            }
            url = f'{self._BASE_URL}/cgi-bin/micromsg-bin/webwxgetsessionlist'
            resp = self._requests.get(url, params=params, timeout=15)

            if resp.status_code == 200:
                rd = resp.json()
                if rd.get('BaseResponse', {}).get('Ret') == 0:
                    sessions = rd.get('SessionList', [])
                    return [
                        {
                            'id': s.get('SessionId', ''),
                            'name': s.get('NickName', ''),
                            'member_count': 0,
                            'conversation_id': s.get('SessionId', ''),
                        }
                        for s in sessions
                    ]
        except Exception as e:
            print(f'[iPad V2] 获取群列表失败: {e}')
        return []

    # ==================== 消息同步（长轮询） ====================

    def start_message_sync(self):
        """启动消息同步（后台长轮询）"""
        if self._sync_running:
            return
        self._sync_running = True
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()
        print('[iPad V2] 消息同步线程已启动')

    def _sync_loop(self):
        """同步循环"""
        while self._sync_running:
            if not self.is_login:
                time.sleep(10)
                continue

            try:
                result = self._sync_check()
                retcode = result.get('retcode', -1)

                if retcode == 0:
                    # 正常，继续轮询
                    time.sleep(5)
                elif retcode == 2:
                    # 有新消息，同步获取
                    messages = self._sync_messages()
                    for msg in messages:
                        self._handle_message(msg)
                elif retcode in (1100, 1102, '1100', '1102'):
                    # 退出/登出
                    print(f'[iPad V2] 会话失效: {retcode}')
                    self.is_login = False
                    break
                else:
                    time.sleep(5)

            except Exception as e:
                print(f'[iPad V2] 同步异常: {e}')
                time.sleep(5)

        self._sync_running = False

    def _sync_check(self) -> Dict:
        """同步检查"""
        if not self.is_login:
            return {'retcode': -1}

        try:
            if not self.sync_key.list_str:
                # 首次同步需要先获取 sync_key
                self._init_sync_key()

            params = {
                'r': int(time.time() * 1000),
                'sid': self.sid or '',
                'uin': self.uin or 0,
                'skey': self.skey or '',
                'deviceid': self.device_id,
                'synckey': self.sync_key.list_str,
                '_': int(time.time() * 1000),
            }
            url = f'{self._BASE_URL}/cgi-bin/micromsg-bin/synccheck'
            resp = self._requests.get(url, params=params, timeout=30)

            text = resp.text
            m = re.search(r'window\.synccheck\s*=\s*\{retcode:"(\d+)",selector:"(\d+)"\}', text)
            if m:
                return {'retcode': int(m.group(1)), 'selector': int(m.group(2))}
            return {'retcode': -1}
        except Exception as e:
            print(f'[iPad V2] sync_check 异常: {e}')
            return {'retcode': -1}

    def _init_sync_key(self):
        """初始化同步密钥"""
        try:
            params = {
                'r': int(time.time() * 1000),
                'skey': self.skey or '',
            }
            url = f'{self._BASE_URL}/cgi-bin/micromsg-bin/webwxsync'
            payload = {
                'BaseRequest': {
                    'Uin': int(self.uin or 0),
                    'Sid': self.sid or '',
                    'Skey': self.skey or '',
                    'DeviceID': self.device_id,
                },
                'SyncKey': self.sync_key.to_dict(),
                'rr': int(time.time() * -1000),
            }
            resp = self._requests.post(url, params=params, json=payload, timeout=20)
            if resp.status_code == 200:
                rd = resp.json()
                if rd.get('BaseResponse', {}).get('Ret') == 0 and 'SyncKey' in rd:
                    self.sync_key._from_dict(rd['SyncKey'])
                    print(f'[iPad V2] SyncKey 初始化完成: {len(self.sync_key.keys)} 个 key')
        except Exception as e:
            print(f'[iPad V2] 初始化 SyncKey 失败: {e}')

    def _sync_messages(self) -> List[Dict]:
        """同步消息"""
        try:
            params = {
                'sid': self.sid or '',
                'skey': self.skey or '',
                'pass_ticket': self.pass_ticket or '',
            }
            payload = {
                'BaseRequest': {
                    'Uin': int(self.uin or 0),
                    'Sid': self.sid or '',
                    'Skey': self.skey or '',
                    'DeviceID': self.device_id,
                },
                'SyncKey': self.sync_key.to_dict(),
                'rr': int(time.time() * -1000),
            }
            url = f'{self._BASE_URL}/cgi-bin/micromsg-bin/webwxsync'
            resp = self._requests.post(url, params=params, json=payload, timeout=20)
            if resp.status_code == 200:
                rd = resp.json()
                if rd.get('BaseResponse', {}).get('Ret') == 0:
                    if 'SyncKey' in rd:
                        self.sync_key._from_dict(rd['SyncKey'])
                    return rd.get('AddMsgList', [])
        except Exception as e:
            print(f'[iPad V2] 同步消息失败: {e}')
        return []

    def _handle_message(self, msg: Dict):
        """处理收到的消息"""
        msg_type = msg.get('MsgType', 0)
        content = msg.get('Content', '')
        from_user = msg.get('FromUserName', '')
        print(f'[iPad V2] 收到消息 type={msg_type} from={from_user}: {str(content)[:50]}')

        # 分发给注册回调
        if msg_type in self._callbacks:
            for cb in self._callbacks[msg_type]:
                try:
                    cb(msg)
                except Exception as e:
                    print(f'[iPad V2] 消息回调异常: {e}')

    def on_message(self, msg_type: int, callback: Callable):
        """注册消息回调"""
        self._callbacks.setdefault(msg_type, []).append(callback)

    def stop_message_sync(self):
        self._sync_running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=2)
        print('[iPad V2] 消息同步已停止')

    # ==================== 生命周期 ====================

    def logout(self):
        self.stop_message_sync()
        self._poll_running = False
        self.is_login = False
        self._reset()
        print('[iPad V2] 已登出')

    def close(self):
        self.logout()
        try:
            self._requests.close()
        except Exception:
            pass
