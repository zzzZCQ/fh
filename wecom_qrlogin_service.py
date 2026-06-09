# -*- coding: utf-8 -*-
"""
企业微信扫码登录服务 - 通过真实的企微接口获取登录二维码

流程:
1. GET /wework_admin/loginpage_wx - 访问登录页获取 cookie
2. GET /wework_admin/wwqrlogin/mng/get_key?login_type=login_admin - 获取 qrcode_key
3. GET /wework_admin/wwqrlogin/mng/qrcode?qrcode_key=xxx&login_type=login_admin - 获取二维码图片
4. GET /wework_admin/wwqrlogin/mng/check?qrcode_key=xxx&status=xxx - 轮询扫码状态

状态枚举:
- QRCODE_SCAN_NEVER: 等待扫码
- QRCODE_SCAN_ING: 已扫码, 等待确认
- QRCODE_SCAN_SUCC: 扫码成功
- QRCODE_SCAN_FAIL: 扫码失败/取消
"""

import requests
import base64
import random
import time
import json
import threading
import uuid
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timedelta

BASE_URL = 'https://work.weixin.qq.com'
LOGIN_PAGE = f'{BASE_URL}/wework_admin/loginpage_wx'
GET_KEY_URL = f'{BASE_URL}/wework_admin/wwqrlogin/mng/get_key'
QRCODE_URL = f'{BASE_URL}/wework_admin/wwqrlogin/mng/qrcode'
CHECK_URL = f'{BASE_URL}/wework_admin/wwqrlogin/mng/check'

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

COMMON_HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

QRLOGIN_REFERER = f'{BASE_URL}/wework_admin/wwqrlogin/mng/login_qrcode?login_type=login_admin'


class WeComQRLoginSession:
    """单个企微扫码登录会话"""

    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.session: requests.Session = requests.Session()
        self.qrcode_key: Optional[str] = None
        self.qrcode_b64: Optional[str] = None
        self.qrcode_bytes: bytes = b''
        self.created_at: datetime = datetime.now()
        self.expires_at: datetime = self.created_at + timedelta(minutes=5)
        self.status: str = 'pending'  # pending | scanned | success | failed | expired
        self.scan_time: Optional[datetime] = None
        self.auth_code: Optional[str] = None
        self.auth_source: Optional[str] = None
        self.error_msg: Optional[str] = None
        self._lock: threading.Lock = threading.Lock()
        self._polling: bool = False
        self._poll_thread: Optional[threading.Thread] = None

    def create(self) -> Tuple[bool, str]:
        """
        创建企微扫码登录会话 - 走完整的真实企微接口流程
        返回: (成功?, qrcode_base64或错误信息)
        """
        try:
            # 步骤 1: 访问登录页获取 cookie
            resp = self.session.get(LOGIN_PAGE, headers=COMMON_HEADERS, timeout=15)
            if resp.status_code != 200:
                return False, f'访问登录页失败: HTTP {resp.status_code}'

            # 步骤 2: 获取 qrcode_key
            headers = dict(COMMON_HEADERS)
            headers['Referer'] = QRLOGIN_REFERER
            headers['X-Requested-With'] = 'XMLHttpRequest'
            headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'

            params = {'r': str(random.random()), 'login_type': 'login_admin'}
            resp2 = self.session.get(GET_KEY_URL, headers=headers, params=params, timeout=15)

            if resp2.status_code != 200:
                return False, f'获取qrcode_key失败: HTTP {resp2.status_code}'

            try:
                key_data = resp2.json()
            except Exception:
                return False, f'qrcode_key响应不是有效JSON'

            qrcode_key = key_data.get('data', {}).get('qrcode_key')
            if not qrcode_key:
                return False, f'响应中未找到qrcode_key: {resp2.text[:200]}'

            self.qrcode_key = qrcode_key

            # 步骤 3: 获取二维码图片
            params3 = {'qrcode_key': qrcode_key, 'login_type': 'login_admin'}
            resp3 = self.session.get(QRCODE_URL, headers=headers, params=params3, timeout=15)

            if resp3.status_code != 200:
                return False, f'获取二维码失败: HTTP {resp3.status_code}'

            content_type = resp3.headers.get('Content-Type', '')
            if 'image' not in content_type.lower() and resp3.content[:4] != b'\x89PNG':
                # 尝试降级
                txt = resp3.text[:200]
                return False, f'返回的不是图片: {content_type} - {txt}'

            self.qrcode_bytes = resp3.content
            self.qrcode_b64 = base64.b64encode(resp3.content).decode('ascii')
            self.status = 'pending'

            # 启动状态轮询线程
            self._start_polling()

            return True, self.qrcode_b64

        except Exception as e:
            return False, f'创建企微登录会话异常: {str(e)}'

    def _start_polling(self):
        """启动后台状态轮询线程"""
        if self._polling:
            return
        self._polling = True
        self._poll_thread = threading.Thread(target=self._poll_status, daemon=True)
        self._poll_thread.start()

    def _poll_status(self):
        """轮询企微扫码状态"""
        last_status = 'QRCODE_SCAN_NEVER'
        headers = dict(COMMON_HEADERS)
        headers['Referer'] = QRLOGIN_REFERER
        headers['X-Requested-With'] = 'XMLHttpRequest'
        headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'

        max_polls = 60  # 最多轮询约60次 (每次5秒, 约5分钟)
        polls = 0

        while self._polling and polls < max_polls and self.status in ('pending', 'scanned'):
            polls += 1
            try:
                params = {
                    'qrcode_key': self.qrcode_key,
                    'status': last_status,
                    'r': str(random.random()),
                }
                resp = self.session.get(CHECK_URL, headers=headers, params=params, timeout=30)

                if resp.status_code != 200:
                    time.sleep(3)
                    continue

                try:
                    data = resp.json()
                except Exception:
                    time.sleep(3)
                    continue

                # 有错误码 (expired 等)
                result = data.get('result')
                if result:
                    err_code = result.get('errCode')
                    if err_code in (-30071, -31024):
                        with self._lock:
                            self.status = 'expired'
                            self.error_msg = '二维码已过期'
                        break
                    # 其他错误
                    time.sleep(3)
                    continue

                status_data = data.get('data')
                if not status_data:
                    time.sleep(3)
                    continue

                cur_status = status_data.get('status', last_status)
                auth_source = status_data.get('auth_source', '')

                if cur_status == 'QRCODE_SCAN_NEVER':
                    # 仍未扫码, 继续等待
                    pass
                elif cur_status == 'QRCODE_SCAN_ING':
                    # 已扫码, 等待用户确认
                    with self._lock:
                        if self.status != 'scanned':
                            self.status = 'scanned'
                            self.scan_time = datetime.now()
                            self.auth_source = auth_source
                elif cur_status == 'QRCODE_SCAN_SUCC':
                    # 成功! 获取 auth_code
                    auth_code = status_data.get('auth_code') or status_data.get('code')
                    with self._lock:
                        self.status = 'success'
                        self.auth_code = auth_code
                        self.auth_source = auth_source
                        # 记录完整响应, 后续可能需要其他字段
                        self._result_data = status_data
                    break
                elif cur_status == 'QRCODE_SCAN_FAIL':
                    with self._lock:
                        self.status = 'failed'
                        self.error_msg = '用户取消或扫码失败'
                    break
                else:
                    # 未知状态
                    pass

                last_status = cur_status
                time.sleep(2)

            except Exception as e:
                time.sleep(3)
                continue

        # 循环结束, 如果状态仍然是 pending, 标记为 expired
        with self._lock:
            if self.status == 'pending':
                self.status = 'expired'
                self.error_msg = '二维码已过期'

    def get_status(self) -> Dict[str, Any]:
        """获取当前扫码状态"""
        with self._lock:
            result = {
                'session_id': self.session_id,
                'status': self.status,
                'created_at': self.created_at.isoformat(),
                'expires_at': self.expires_at.isoformat(),
                'elapsed_seconds': int((datetime.now() - self.created_at).total_seconds()),
                'qrcode_key_exists': bool(self.qrcode_key),
                'qrcode_size': len(self.qrcode_bytes) if self.qrcode_bytes else 0,
            }
            if self.scan_time:
                result['scan_time'] = self.scan_time.isoformat()
            if self.auth_code:
                result['auth_code'] = self.auth_code
            if self.auth_source:
                result['auth_source'] = self.auth_source
            if self.error_msg:
                result['error'] = self.error_msg
            return result

    def get_result(self) -> Dict[str, Any]:
        """获取扫码结果(用于前端处理登录跳转)"""
        with self._lock:
            if self.status == 'success':
                return {
                    'success': True,
                    'auth_code': self.auth_code,
                    'auth_source': self.auth_source,
                    'status': self.status,
                }
            else:
                return {
                    'success': False,
                    'status': self.status,
                    'message': self.error_msg or '扫码未完成',
                }

    def stop(self):
        """停止轮询"""
        self._polling = False
        try:
            if self._poll_thread and self._poll_thread.is_alive():
                self._poll_thread.join(timeout=2)
        except Exception:
            pass


class QRLoginService:
    """管理多个企微扫码登录会话"""

    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self.sessions: Dict[str, WeComQRLoginSession] = {}
        self._lock = threading.Lock()
        self._cleanup_thread = threading.Thread(target=self._cleanup_expired, daemon=True)
        self._cleanup_thread.start()

    @classmethod
    def get_instance(cls) -> 'QRLoginService':
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _cleanup_expired(self):
        """定期清理过期会话"""
        while True:
            try:
                now = datetime.now()
                with self._lock:
                    expired_ids = [
                        sid for sid, sess in self.sessions.items()
                        if sess.expires_at < now and sess.status not in ('pending', 'scanned')
                    ]
                    # 超过10分钟的会话无论什么状态都清理
                    stale_ids = [
                        sid for sid, sess in self.sessions.items()
                        if (now - sess.created_at).total_seconds() > 1800
                    ]
                    for sid in set(expired_ids + stale_ids):
                        if sid in self.sessions:
                            self.sessions[sid].stop()
                            del self.sessions[sid]
            except Exception:
                pass
            time.sleep(60)

    def create_qrcode(self) -> Tuple[str, str]:
        """
        创建新的扫码登录会话
        返回: (session_id, data_url或错误信息)
        """
        login_session = WeComQRLoginSession()
        success, result = login_session.create()

        with self._lock:
            self.sessions[login_session.session_id] = login_session

        if success:
            return login_session.session_id, f'data:image/png;base64,{result}'
        else:
            return login_session.session_id, f'error:{result}'

    def get_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取指定会话的状态"""
        with self._lock:
            sess = self.sessions.get(session_id)
        if sess:
            return sess.get_status()
        return None

    def get_result(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取指定会话的登录结果"""
        with self._lock:
            sess = self.sessions.get(session_id)
        if sess:
            return sess.get_result()
        return None

    def get_qrcode(self, session_id: str) -> Optional[bytes]:
        """获取指定会话的二维码图片字节"""
        with self._lock:
            sess = self.sessions.get(session_id)
        if sess and sess.qrcode_bytes:
            return sess.qrcode_bytes
        return None


def get_qrlogin_service() -> QRLoginService:
    """获取 QRLoginService 单例"""
    return QRLoginService.get_instance()
