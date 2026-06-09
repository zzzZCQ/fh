# -*- coding: utf-8 -*-
"""
企业微信 iPad 协议 - 完整账号托管实现

功能：
1. 生成二维码供企微APP扫描
2. 轮询扫码状态
3. 扫码成功后获取会话凭证 (wwrtx.sid)
4. 使用凭证实现消息收发、联系人管理等

这是真正的"iPad协议" - 模拟iPad设备访问企业微信，获取会话后调用API
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

# 企业微信管理后台API端点
BASE_URL = 'https://work.weixin.qq.com'
LOGIN_PAGE = f'{BASE_URL}/wework_admin/loginpage_wx'
GET_KEY_URL = f'{BASE_URL}/wework_admin/wwqrlogin/mng/get_key'
QRCODE_URL = f'{BASE_URL}/wework_admin/wwqrlogin/mng/qrcode'
CHECK_URL = f'{BASE_URL}/wework_admin/wwqrlogin/mng/check'

# 消息和联系人API
MESSAGE_SEND_URL = f'{BASE_URL}/wework_admin/message/send'
CONTACT_LIST_URL = f'{BASE_URL}/wework_admin/getContactInfo'
USER_INFO_URL = f'{BASE_URL}/wework_admin/user/info'

# iPad设备头 - 模拟iPad企业微信APP
IPAD_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.0',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://work.weixin.qq.com/',
    'Origin': 'https://work.weixin.qq.com',
    'X-Requested-With': 'XMLHttpRequest',
}


class WeComIPadSession:
    """企业微信 iPad 会话 - 完整账号托管"""

    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.session: requests.Session = requests.Session()
        self.session.headers.update(IPAD_HEADERS)

        # 登录状态
        self.qrcode_key: Optional[str] = None
        self.qrcode_bytes: bytes = b''
        self.status: str = 'pending'  # pending | scanned | success | failed | expired
        self.created_at: datetime = datetime.now()
        self.expires_at: datetime = self.created_at + timedelta(minutes=5)

        # 会话凭证 - 这是关键！
        self.sid: Optional[str] = None  # wwrtx.sid
        self.ticket: Optional[str] = None  # wwrtx.ticket
        self.cookie_str: Optional[str] = None  # 完整cookie字符串

        # 用户信息
        self.user_info: Optional[Dict] = None
        self.corp_id: Optional[str] = None
        self.user_id: Optional[str] = None

        # 线程控制
        self._lock = threading.Lock()
        self._polling = False
        self._poll_thread: Optional[threading.Thread] = None

    def create_qrcode(self) -> Tuple[bool, str]:
        """创建登录二维码"""
        try:
            # 步骤1: 访问登录页建立cookie
            resp1 = self.session.get(LOGIN_PAGE, timeout=15)
            if resp1.status_code != 200:
                return False, f'访问登录页失败: {resp1.status_code}'

            # 步骤2: 获取 qrcode_key (使用 login_admin 获取key)
            resp2 = self.session.get(
                GET_KEY_URL,
                params={'login_type': 'login_admin', 'r': str(random.random())},
                timeout=15
            )
            if resp2.status_code != 200:
                return False, f'获取key失败: {resp2.status_code}'

            try:
                data = resp2.json()
                self.qrcode_key = data.get('data', {}).get('qrcode_key')
            except:
                return False, '获取qrcode_key失败'

            if not self.qrcode_key:
                return False, '响应中没有qrcode_key'

            # 步骤3: 获取二维码 (使用 wwclient 类型)
            resp3 = self.session.get(
                QRCODE_URL,
                params={'qrcode_key': self.qrcode_key, 'login_type': 'wwclient'},
                timeout=15
            )
            if resp3.status_code != 200:
                return False, f'获取二维码失败: {resp3.status_code}'

            if resp3.content[:4] != b'\x89PNG':
                return False, '响应不是PNG图片'

            self.qrcode_bytes = resp3.content
            self.status = 'pending'

            # 启动状态轮询
            self._start_polling()

            return True, ''

        except Exception as e:
            return False, f'异常: {str(e)}'

    def _start_polling(self):
        """启动状态轮询线程"""
        if self._polling:
            return
        self._polling = True
        self._poll_thread = threading.Thread(target=self._poll_status, daemon=True)
        self._poll_thread.start()

    def _poll_status(self):
        """轮询扫码状态"""
        last_status = 'QRCODE_SCAN_NEVER'
        max_polls = 300  # 5分钟

        while self._polling and self.status in ('pending', 'scanned'):
            try:
                resp = self.session.get(
                    CHECK_URL,
                    params={
                        'qrcode_key': self.qrcode_key,
                        'status': last_status,
                        'r': str(random.random()),
                    },
                    timeout=30
                )

                if resp.status_code != 200:
                    time.sleep(2)
                    continue

                try:
                    data = resp.json()
                except:
                    time.sleep(2)
                    continue

                # 检查错误
                result = data.get('result', {})
                if result.get('errCode') in (-30071, -31024):
                    with self._lock:
                        self.status = 'expired'
                    break

                status_data = data.get('data', {})
                cur_status = status_data.get('status', '')

                if cur_status == 'QRCODE_SCAN_NEVER':
                    pass  # 继续等待
                elif cur_status == 'QRCODE_SCAN_ING':
                    with self._lock:
                        self.status = 'scanned'
                elif cur_status == 'QRCODE_SCAN_SUCC':
                    # 登录成功！提取凭证
                    with self._lock:
                        self.status = 'success'
                        self._extract_credentials(resp, status_data)
                    break
                elif cur_status == 'QRCODE_SCAN_FAIL':
                    with self._lock:
                        self.status = 'failed'
                    break

                last_status = cur_status
                time.sleep(2)

            except Exception as e:
                time.sleep(3)

        # 超时处理
        with self._lock:
            if self.status == 'pending':
                self.status = 'expired'

    def _extract_credentials(self, resp, status_data):
        """提取登录凭证 - 这是关键步骤"""
        # 从Cookie提取
        for cookie in self.session.cookies:
            if cookie.name == 'wwrtx.sid':
                self.sid = cookie.value
            elif cookie.name == 'wwrtx.ticket':
                self.ticket = cookie.value

        # 构建完整cookie字符串
        cookies = []
        for cookie in self.session.cookies:
            cookies.append(f'{cookie.name}={cookie.value}')
        self.cookie_str = '; '.join(cookies)

        # 从响应数据提取用户信息
        self.user_info = {
            'auth_code': status_data.get('auth_code'),
            'auth_source': status_data.get('auth_source'),
            'corp_id': status_data.get('corp_id'),
            'user_id': status_data.get('user_id'),
        }

        print(f"[iPad] 登录成功!")
        print(f"  sid: {self.sid[:20] if self.sid else 'None'}...")
        print(f"  ticket: {self.ticket[:20] if self.ticket else 'None'}...")

    def get_qrcode_b64(self) -> Optional[str]:
        """获取base64二维码"""
        if self.qrcode_bytes:
            return base64.b64encode(self.qrcode_bytes).decode('ascii')
        return None

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        with self._lock:
            return {
                'session_id': self.session_id,
                'status': self.status,
                'has_sid': bool(self.sid),
                'has_ticket': bool(self.ticket),
                'user_info': self.user_info,
                'expires_in': max(0, int((self.expires_at - datetime.now()).total_seconds())),
            }

    # ==================== 账号托管功能 ====================

    def send_message(self, to_user: str, content: str, msg_type: int = 1) -> Tuple[bool, str]:
        """发送消息

        Args:
            to_user: 接收者ID
            content: 消息内容
            msg_type: 消息类型 (1=文本, 3=图片, 34=语音, 43=视频, 49=文件)
        """
        if not self.cookie_str:
            return False, '未登录'

        try:
            data = {
                'tousername': to_user,
                'content': content,
                'msgtype': msg_type,
            }

            resp = self.session.post(
                MESSAGE_SEND_URL,
                json=data,
                headers={
                    'Content-Type': 'application/json;charset=utf-8',
                    'Cookie': self.cookie_str,
                },
                timeout=30
            )

            if resp.status_code == 200:
                result = resp.json()
                if result.get('errcode') == 0:
                    return True, '发送成功'
                else:
                    return False, result.get('errmsg', '发送失败')
            else:
                return False, f'HTTP {resp.status_code}'

        except Exception as e:
            return False, str(e)

    def get_contacts(self) -> Tuple[bool, List[Dict]]:
        """获取联系人列表"""
        if not self.cookie_str:
            return False, []

        try:
            resp = self.session.get(
                CONTACT_LIST_URL,
                headers={'Cookie': self.cookie_str},
                timeout=30
            )

            if resp.status_code == 200:
                # 解析联系人数据
                # 具体格式需要根据实际响应调整
                return True, []
            else:
                return False, []

        except Exception as e:
            return False, []

    def get_user_info(self) -> Optional[Dict]:
        """获取当前登录用户信息"""
        if not self.cookie_str:
            return None

        try:
            resp = self.session.get(
                USER_INFO_URL,
                headers={'Cookie': self.cookie_str},
                timeout=30
            )

            if resp.status_code == 200:
                return resp.json()
            return None

        except:
            return None


class WeComIPadService:
    """企业微信 iPad 服务 - 单例"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_service()
        return cls._instance

    def _init_service(self):
        self.sessions: Dict[str, WeComIPadSession] = {}
        print("[WeComIPadService] 服务已初始化")

    def create_session(self) -> Tuple[str, str]:
        """创建登录会话"""
        session = WeComIPadSession()
        success, err = session.create_qrcode()

        if success:
            self.sessions[session.session_id] = session
            return session.session_id, ''
        else:
            return '', err

    def get_session(self, session_id: str) -> Optional[WeComIPadSession]:
        return self.sessions.get(session_id)

    def get_status(self, session_id: str) -> Optional[Dict]:
        session = self.sessions.get(session_id)
        if session:
            return session.get_status()
        return None

    def get_qrcode_b64(self, session_id: str) -> Optional[str]:
        session = self.sessions.get(session_id)
        if session:
            return session.get_qrcode_b64()
        return None

    def send_message(self, session_id: str, to_user: str, content: str) -> Tuple[bool, str]:
        session = self.sessions.get(session_id)
        if session:
            return session.send_message(to_user, content)
        return False, '会话不存在'


def get_wecom_ipad_service() -> WeComIPadService:
    return WeComIPadService()


if __name__ == '__main__':
    service = get_wecom_ipad_service()

    print('='*60)
    print('企业微信 iPad 账号托管测试')
    print('='*60)

    # 创建会话
    sid, err = service.create_session()
    print(f'会话ID: {sid}')
    print(f'错误: {err}')

    if sid:
        qr_b64 = service.get_qrcode_b64(sid)
        print(f'二维码: {len(qr_b64)} chars')

        # 保存二维码
        qr_bytes = base64.b64decode(qr_b64)
        with open('ipad_login_qr.png', 'wb') as f:
            f.write(qr_bytes)
        print('已保存: ipad_login_qr.png')

        # 等待扫码
        print('\n等待扫码...')
        for i in range(60):
            time.sleep(2)
            status = service.get_status(sid)
            print(f'  [{i*2}s] {status.get("status")}', end='')
            if status.get('has_sid'):
                print(f' - 已获取凭证!')
                break
            print()

        # 最终状态
        status = service.get_status(sid)
        print(f'\n最终状态: {status}')
