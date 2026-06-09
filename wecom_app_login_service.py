# -*- coding: utf-8 -*-
"""
企业微信 iPad/APP 客户端扫码登录服务

真实iPad协议流程 (wx.work.weixin.qq.com):
1. GET open.work.weixin.qq.com/wwopen/sso/3rd_qrConnect - 获取授权页面
2. 从页面中提取二维码URL
3. GET 二维码URL - 获取二维码图片
4. 轮询检查登录状态

注意: 
- work.weixin.qq.com 是管理后台端点，扫码后会登录管理后台
- wx.work.weixin.qq.com 是iPad企微APP端点，扫码后登录APP客户端

login_type 说明:
- wwclient: 企微 APP 客户端登录（iPad/手机），可用企微APP扫码
- login_admin: 企微管理后台登录

状态枚举:
- pending: 等待扫码
- scanned: 已扫码, 等待确认
- success: 扫码成功
- failed: 扫码失败/取消
- expired: 二维码已过期
"""

import requests
import base64
import random
import time
import json
import threading
import uuid
import hashlib
import re
from typing import Tuple, Optional, Dict, Any, List
from datetime import datetime, timedelta

# === 使用真正的iPad协议端点 ===
# wx.work.weixin.qq.com 是iPad企微APP的真实端点
IPAD_BASE_URL = 'https://wx.work.weixin.qq.com'
IPAD_AUTH_URL = 'https://open.work.weixin.qq.com/wwopen/sso/3rd_qrConnect'
IPAD_CHECK_URL = 'https://wx.work.weixin.qq.com/wwlogin/wwlogin/checklogin'

# 管理后台端点（备用）
ADMIN_BASE_URL = 'https://work.weixin.qq.com'
ADMIN_LOGIN_PAGE = f'{ADMIN_BASE_URL}/wework_admin/loginpage_wx'
ADMIN_GET_KEY_URL = f'{ADMIN_BASE_URL}/wework_admin/wwqrlogin/mng/get_key'
ADMIN_QRCODE_URL = f'{ADMIN_BASE_URL}/wework_admin/wwqrlogin/mng/qrcode'
ADMIN_CHECK_URL = f'{ADMIN_BASE_URL}/wework_admin/wwqrlogin/mng/check'

# iPad协议专用Header
IPAD_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.0',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://wx.work.weixin.qq.com/',
    'X-Requested-With': 'XMLHttpRequest',
}

# 管理后台Header
ADMIN_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://work.weixin.qq.com/',
    'X-Requested-With': 'XMLHttpRequest',
}

DEFAULT_LOGIN_TYPE = 'wwclient'


class WeComAppLoginSession:
    """企微 APP 客户端扫码登录会话"""

    def __init__(self, login_type: str = DEFAULT_LOGIN_TYPE):
        self.session_id = str(uuid.uuid4())
        self.login_type = login_type
        self.session: requests.Session = requests.Session()
        self.qrcode_key: Optional[str] = None
        self.qrcode_bytes: bytes = b''
        self.created_at: datetime = datetime.now()
        self.expires_at: datetime = self.created_at + timedelta(minutes=5)
        self.status: str = 'pending'    # pending | scanned | success | failed | expired
        self.scan_time: Optional[datetime] = None
        self.auth_code: Optional[str] = None
        self.auth_source: Optional[str] = None
        self.redirect_url: Optional[str] = None
        self.error_msg: Optional[str] = None
        self._lock = threading.Lock()
        self._polling = False
        self._poll_thread: Optional[threading.Thread] = None
        self._last_check_response: Optional[Dict[str, Any]] = None
        # iPad协议专用
        self._uuid: str = hashlib.md5(str(time.time()).encode()).hexdigest()
        self._callback_url: Optional[str] = None

    def _generate_uuid(self) -> str:
        """生成UUID"""
        return hashlib.md5(f"{time.time()}{random.randint(1000,9999)}".encode()).hexdigest()

    def create(self) -> Tuple[bool, str]:
        """
        创建企微 APP 扫码登录会话
        返回: (成功?, 错误信息或空字符串)
        """
        try:
            if self.login_type == 'wwclient':
                # 使用真正的iPad协议
                return self._create_ipad_session()
            else:
                # 使用管理后台协议
                return self._create_admin_session()

        except Exception as e:
            return False, f'创建登录会话异常: {str(e)}'

    def _create_ipad_session(self) -> Tuple[bool, str]:
        """使用iPad协议创建会话"""
        try:
            self._uuid = self._generate_uuid()
            
            # 构造授权URL - 这是iPad企微APP的真实授权URL
            auth_params = {
                'appid': 'wx782c26e4c19acffb',
                'redirect_uri': 'https://wx.work.weixin.qq.com/wwlogin/wwlogin.html',
                'fun': 'new',
                'lang': 'zh_CN',
                '_': str(int(time.time() * 1000)),
                'state': self._uuid,
            }
            
            # 访问授权页面获取二维码
            resp = self.session.get(IPAD_AUTH_URL, params=auth_params, headers=IPAD_HEADERS, timeout=15, allow_redirects=True)
            if resp.status_code != 200:
                return False, f'访问授权页面失败: HTTP {resp.status_code}'

            # 从响应中提取二维码信息
            # 检查是否有ticket（已登录状态）
            if 'ticket=' in resp.url:
                match = re.search(r'ticket=([a-zA-Z0-9_-]+)', resp.url)
                if match:
                    self.auth_code = match.group(1)
                    self.status = 'success'
                    return True, ''

            # 解析页面获取二维码URL
            content = resp.text
            
            # 尝试多种方式提取二维码URL
            qrcode_url = None
            
            # 方式1: 查找 qrcodeUrl
            match = re.search(r'qrcodeUrl\s*[:=]\s*["\']([^"\']+)["\']', content)
            if match:
                qrcode_url = match.group(1)
            
            # 方式2: 查找 img src 包含 qrcode
            if not qrcode_url:
                match = re.search(r'<img[^>]*src=["\']([^"\']*qrcode[^"\']*)["\']', content)
                if match:
                    qrcode_url = match.group(1)
            
            # 方式3: 使用iframe中的URL
            if not qrcode_url:
                match = re.search(r'<iframe[^>]*src=["\']([^"\']+)["\']', content)
                if match:
                    iframe_url = match.group(1)
                    if not iframe_url.startswith('http'):
                        iframe_url = 'https://open.work.weixin.qq.com' + iframe_url
                    # 访问iframe获取二维码
                    iframe_resp = self.session.get(iframe_url, headers=IPAD_HEADERS, timeout=15)
                    match2 = re.search(r'qrcodeUrl\s*[:=]\s*["\']([^"\']+)["\']', iframe_resp.text)
                    if match2:
                        qrcode_url = match2.group(1)

            if not qrcode_url:
                # 如果无法从页面提取，使用备用方案
                return self._create_ipad_fallback_session()

            # 获取二维码图片
            if not qrcode_url.startswith('http'):
                qrcode_url = 'https://open.work.weixin.qq.com' + qrcode_url
            
            qr_resp = self.session.get(qrcode_url, headers=IPAD_HEADERS, timeout=15)
            if qr_resp.status_code != 200:
                return False, f'获取二维码失败: HTTP {qr_resp.status_code}'
            
            if qr_resp.content[:4] != b'\x89PNG':
                # 如果不是PNG，尝试备用方案
                return self._create_ipad_fallback_session()

            self.qrcode_bytes = qr_resp.content
            self.qrcode_key = self._uuid  # 使用UUID作为key
            self.status = 'pending'

            # 启动后台状态轮询
            self._start_polling()

            return True, ''

        except Exception as e:
            return False, f'iPad协议创建会话失败: {str(e)}'

    def _create_ipad_fallback_session(self) -> Tuple[bool, str]:
        """iPad协议备用方案 - 使用管理后台的wwclient类型"""
        try:
            # 先用login_admin获取key
            resp = self.session.get(ADMIN_LOGIN_PAGE, headers=ADMIN_HEADERS, timeout=15)
            if resp.status_code != 200:
                return False, f'访问登录页失败: HTTP {resp.status_code}'

            key_params = {
                'login_type': 'login_admin',
                'r': str(random.random()),
            }
            resp2 = self.session.get(ADMIN_GET_KEY_URL, headers=ADMIN_HEADERS, params=key_params, timeout=15)
            if resp2.status_code != 200:
                return False, f'获取 qrcode_key 失败: HTTP {resp2.status_code}'

            try:
                key_json = resp2.json()
            except Exception:
                return False, f'qrcode_key 响应不是有效JSON'

            self.qrcode_key = key_json.get('data', {}).get('qrcode_key')
            if not self.qrcode_key:
                return False, '响应中没有 qrcode_key'

            # 使用wwclient生成二维码
            qr_params = {
                'qrcode_key': self.qrcode_key,
                'login_type': 'wwclient',
            }
            resp3 = self.session.get(ADMIN_QRCODE_URL, headers=ADMIN_HEADERS, params=qr_params, timeout=15)
            if resp3.status_code != 200:
                return False, f'获取二维码失败: HTTP {resp3.status_code}'

            content_type = resp3.headers.get('Content-Type', '')
            if 'image' not in content_type.lower() and resp3.content[:4] != b'\x89PNG':
                return False, '二维码响应不是图片'

            self.qrcode_bytes = resp3.content
            self.status = 'pending'
            self._start_polling()

            return True, ''

        except Exception as e:
            return False, f'备用方案失败: {str(e)}'

    def _create_admin_session(self) -> Tuple[bool, str]:
        """使用管理后台协议创建会话"""
        try:
            # 步骤1: 访问登录页获取cookie
            resp = self.session.get(ADMIN_LOGIN_PAGE, headers=ADMIN_HEADERS, timeout=15)
            if resp.status_code != 200:
                return False, f'访问登录页失败: HTTP {resp.status_code}'

            # 步骤2: 获取 qrcode_key
            key_params = {
                'login_type': self.login_type,
                'r': str(random.random()),
            }
            resp2 = self.session.get(ADMIN_GET_KEY_URL, headers=ADMIN_HEADERS, params=key_params, timeout=15)
            if resp2.status_code != 200:
                return False, f'获取 qrcode_key 失败: HTTP {resp2.status_code}'

            try:
                key_json = resp2.json()
            except Exception:
                return False, f'qrcode_key 响应不是有效JSON: {resp2.text[:200]}'

            self.qrcode_key = key_json.get('data', {}).get('qrcode_key')
            if not self.qrcode_key:
                return False, f'响应中没有 qrcode_key: {resp2.text[:200]}'

            # 步骤3: 获取二维码图片
            qr_params = {
                'qrcode_key': self.qrcode_key,
                'login_type': self.login_type,
            }
            resp3 = self.session.get(ADMIN_QRCODE_URL, headers=ADMIN_HEADERS, params=qr_params, timeout=15)
            if resp3.status_code != 200:
                return False, f'获取二维码失败: HTTP {resp3.status_code}'

            content_type = resp3.headers.get('Content-Type', '')
            if 'image' not in content_type.lower() and resp3.content[:4] != b'\x89PNG':
                return False, f'二维码响应不是图片: {content_type[:100]}'

            self.qrcode_bytes = resp3.content
            self.status = 'pending'

            # 启动后台状态轮询
            self._start_polling()

            return True, ''

        except Exception as e:
            return False, f'创建登录会话异常: {str(e)}'

    def _start_polling(self):
        """启动后台扫码状态轮询"""
        if self._polling:
            return
        self._polling = True
        self._poll_thread = threading.Thread(target=self._poll_status, daemon=True)
        self._poll_thread.start()

    def _poll_status(self):
        """轮询扫码状态"""
        last_status = 'QRCODE_SCAN_NEVER'
        headers = IPAD_HEADERS if self.login_type == 'wwclient' else ADMIN_HEADERS
        check_url = ADMIN_CHECK_URL  # 统一使用管理后台的check接口

        max_polls = 300
        polls = 0

        while self._polling and polls < max_polls and self.status in ('pending', 'scanned'):
            polls += 1
            try:
                params = {
                    'qrcode_key': self.qrcode_key,
                    'status': last_status,
                    'r': str(random.random()),
                }
                resp = self.session.get(check_url, headers=headers, params=params, timeout=30)

                if resp.status_code != 200:
                    time.sleep(2)
                    continue

                try:
                    data = resp.json()
                except Exception:
                    time.sleep(2)
                    continue

                self._last_check_response = data

                result = data.get('result')
                if result:
                    err_code = result.get('errCode')
                    if err_code in (-30071, -31024):
                        with self._lock:
                            self.status = 'expired'
                            self.error_msg = '二维码已过期'
                        break
                    time.sleep(2)
                    continue

                status_data = data.get('data')
                if not status_data:
                    time.sleep(2)
                    continue

                cur_status = status_data.get('status', last_status)
                auth_source = status_data.get('auth_source', '')

                if cur_status == 'QRCODE_SCAN_NEVER':
                    pass
                elif cur_status == 'QRCODE_SCAN_ING':
                    with self._lock:
                        if self.status != 'scanned':
                            self.status = 'scanned'
                            self.scan_time = datetime.now()
                            self.auth_source = auth_source
                elif cur_status == 'QRCODE_SCAN_SUCC':
                    with self._lock:
                        self.status = 'success'
                        self.auth_code = status_data.get('auth_code') or status_data.get('code') or status_data.get('wx_code')
                        self.auth_source = auth_source
                        self._result_data = dict(status_data)
                    break
                elif cur_status == 'QRCODE_SCAN_FAIL':
                    with self._lock:
                        self.status = 'failed'
                        self.error_msg = '用户取消了登录'
                    break

                last_status = cur_status
                time.sleep(2)

            except Exception:
                time.sleep(3)
                continue

        with self._lock:
            if self.status == 'pending':
                self.status = 'expired'
                self.error_msg = '二维码已过期'

    def get_status(self) -> Dict[str, Any]:
        """获取当前会话状态"""
        with self._lock:
            return {
                'session_id': self.session_id,
                'status': self.status,
                'login_type': self.login_type,
                'elapsed_seconds': int((datetime.now() - self.created_at).total_seconds()),
                'expires_in': int((self.expires_at - datetime.now()).total_seconds()),
                'qrcode_size': len(self.qrcode_bytes),
                'auth_source': self.auth_source,
                'auth_code': self.auth_code,
                'error': self.error_msg,
                'scan_time': self.scan_time.isoformat() if self.scan_time else None,
            }

    def get_qrcode_b64(self) -> Optional[str]:
        """获取 base64 编码的二维码图片"""
        if self.qrcode_bytes:
            return base64.b64encode(self.qrcode_bytes).decode('ascii')
        return None

    def get_result(self) -> Dict[str, Any]:
        """获取最终的登录结果"""
        with self._lock:
            if self.status == 'success':
                return {
                    'success': True,
                    'status': self.status,
                    'auth_code': self.auth_code,
                    'auth_source': self.auth_source,
                    'login_type': self.login_type,
                }
            else:
                return {
                    'success': False,
                    'status': self.status,
                    'error': self.error_msg,
                }

    def close(self):
        """关闭会话"""
        self._polling = False


class WeComAppLoginService:
    """企微 APP 客户端扫码登录服务 - 单例"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_service()
        return cls._instance

    def _init_service(self):
        self.sessions: Dict[str, WeComAppLoginSession] = {}
        self._cleanup_thread = threading.Thread(target=self._cleanup_expired_sessions, daemon=True)
        self._cleanup_thread.start()
        print("[WeComAppLoginService] 服务已初始化")

    def _cleanup_expired_sessions(self):
        """定期清理过期会话"""
        while True:
            try:
                now = datetime.now()
                expired_ids = []
                for session_id, session in self.sessions.items():
                    if now > session.expires_at or session.status in ('success', 'failed', 'expired'):
                        session.close()
                        expired_ids.append(session_id)
                
                for session_id in expired_ids:
                    del self.sessions[session_id]
                
                if expired_ids:
                    print(f"[WeComAppLoginService] 清理过期会话: {len(expired_ids)}")
            except Exception:
                pass
            time.sleep(60)

    def create_session(self, login_type: str = DEFAULT_LOGIN_TYPE) -> Tuple[str, str]:
        """创建登录会话"""
        session = WeComAppLoginSession(login_type=login_type)
        success, err = session.create()
        
        if success:
            self.sessions[session.session_id] = session
            return session.session_id, ''
        else:
            return '', err

    def get_session(self, session_id: str) -> Optional[WeComAppLoginSession]:
        """获取会话"""
        return self.sessions.get(session_id)

    def get_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        session = self.sessions.get(session_id)
        if session:
            return session.get_status()
        return None

    def get_qrcode_b64(self, session_id: str) -> Optional[str]:
        """获取二维码 base64"""
        session = self.sessions.get(session_id)
        if session:
            return session.get_qrcode_b64()
        return None

    def get_qrcode_bytes(self, session_id: str) -> Optional[bytes]:
        """获取二维码原始字节"""
        session = self.sessions.get(session_id)
        if session:
            return session.qrcode_bytes
        return None

    def get_result(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取登录结果"""
        session = self.sessions.get(session_id)
        if session:
            return session.get_result()
        return None

    def close_session(self, session_id: str):
        """关闭会话"""
        session = self.sessions.get(session_id)
        if session:
            session.close()
            del self.sessions[session_id]


def get_wecom_app_login_service() -> WeComAppLoginService:
    """获取登录服务实例"""
    return WeComAppLoginService()


if __name__ == '__main__':
    # 测试
    service = get_wecom_app_login_service()
    
    print('='*60)
    print('测试 iPad 企微APP登录服务')
    print('='*60)
    
    # 测试 wwclient 类型（iPad企微APP）
    print('\n[1] 测试 wwclient (iPad企微APP客户端)')
    sid, err = service.create_session(login_type='wwclient')
    print(f'  session_id: {sid}')
    print(f'  error: {err}')
    
    if sid:
        qr_b64 = service.get_qrcode_b64(sid)
        status = service.get_status(sid)
        print(f'  二维码大小: {status.get("qrcode_size", 0)} bytes')
        print(f'  状态: {status.get("status")}')
        
        # 保存二维码
        qr_bytes = service.get_qrcode_bytes(sid)
        if qr_bytes:
            with open('ipad_wwclient_qrcode.png', 'wb') as f:
                f.write(qr_bytes)
            print('  已保存: ipad_wwclient_qrcode.png')
    
    # 测试 login_admin 类型（管理后台）
    print('\n[2] 测试 login_admin (管理后台)')
    sid2, err2 = service.create_session(login_type='login_admin')
    print(f'  session_id: {sid2}')
    print(f'  error: {err2}')
    
    if sid2:
        qr_b64 = service.get_qrcode_b64(sid2)
        status = service.get_status(sid2)
        print(f'  二维码大小: {status.get("qrcode_size", 0)} bytes')
        print(f'  状态: {status.get("status")}')
        
        qr_bytes = service.get_qrcode_bytes(sid2)
        if qr_bytes:
            with open('admin_qrcode.png', 'wb') as f:
                f.write(qr_bytes)
            print('  已保存: admin_qrcode.png')
    
    print('\n测试完成!')