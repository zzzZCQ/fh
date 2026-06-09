# -*- coding: utf-8 -*-
"""
企微账号托管服务层
==================

管理多个账号的并发登录、状态维护、消息收发。

核心数据结构：
    - ActiveSession：一个账号 = 一个 Session（协议实例 + 状态）
    - 服务层持有的 session 以 session_id 为 key
    - 数据持久化到数据库（WecomAccount）

设计目标：
    - 同一用户可托管多个账号
    - 不同账号使用独立的协议实例，互不干扰
    - 扫码阶段：创建 session → 给前端二维码 → 轮询状态 → 登录成功 → 写入 DB
    - 已登录账号：恢复 cookies → 复用 session
"""

import os
import json
import time
import threading
import traceback
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from collections import OrderedDict

from wecom_protocols import (
    BaseProtocol,
    create_protocol,
    get_default_protocol_name,
    get_available_protocols,
    LOGIN_STATUS_PENDING,
    LOGIN_STATUS_SCANNED,
    LOGIN_STATUS_SUCCESS,
    LOGIN_STATUS_ONLINE,
    LOGIN_STATUS_EXPIRED,
    LOGIN_STATUS_FAILED,
    LOGIN_STATUS_OFFLINE,
)


# ============================================================
# Active Session 类
# ============================================================

class ActiveSession:
    """活跃的账号会话（内存态）"""

    def __init__(self, protocol: BaseProtocol, user_id: int, account_id: Optional[int] = None):
        self.protocol = protocol
        self.session_id = protocol.session_id
        self.user_id = user_id
        self.account_id = account_id
        self.qrcode_data_url: Optional[str] = None
        self.created_at = datetime.now()
        self.last_poll_at = datetime.now()
        self.lock = threading.RLock()

    def to_dict(self) -> Dict:
        info = self.protocol.get_login_info() or {}
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'account_id': self.account_id,
            'status': self.protocol.status,
            'name': info.get('name') or info.get('account_name') or info.get('user_id') or '',
            'login_info': info,
            'protocol': self.protocol.protocol_name,
            'has_qrcode': self.qrcode_data_url is not None,
            'created_at': self.created_at.isoformat(),
        }


# ============================================================
# 账号托管服务
# ============================================================

class AccountHostingService:
    """账号托管服务 - 全局单例"""

    def __init__(self, max_sessions_per_user: int = 10):
        self._sessions: "OrderedDict[str, ActiveSession]" = OrderedDict()
        self._user_sessions: Dict[int, List[str]] = {}  # user_id -> list of session_ids
        self._lock = threading.RLock()
        self._max_per_user = max_sessions_per_user
        self._max_total = 200  # 系统最多 200 个活跃 session

    # ---------------- Session 生命周期 ----------------

    def start_login(
        self,
        user_id: int,
        protocol_name: Optional[str] = None,
        account_id: Optional[int] = None,
    ) -> Tuple[bool, str, Optional[ActiveSession]]:
        """开始一个新的登录流程

        Args:
            user_id: 当前系统用户ID
            protocol_name: 使用的协议名，None 时自动选择
            account_id: 如果是已有账号重新登录，传入账号 ID
        Returns:
            (success, message, session)
        """
        protocol_name = protocol_name or get_default_protocol_name()

        # 创建协议实例
        protocol = create_protocol(protocol_name)
        session = ActiveSession(protocol=protocol, user_id=user_id, account_id=account_id)

        # 创建二维码（可能抛出 RuntimeError）
        try:
            ok, err, qr_data = protocol.create_qrcode()
        except Exception as ex:
            # Playwright 不可用等情况会抛异常
            return False, f'协议初始化失败: {ex}', None

        if not ok:
            return False, err or '创建登录二维码失败', None

        session.qrcode_data_url = qr_data

        # 注册 session（同一个用户的 session 列表
        with self._lock:
            # 限制用户 session 注册
            self._sessions[session.session_id] = session
            # 维护按 user_id 的 session 列表
            self._user_sessions.setdefault(user_id, []).append(session.session_id)
            # 限制用户 session 列表
            self._cleanup_old_sessions_locked()
            # 限制用户 session 列表（LRU 驱逐
            self._enforce_limits_locked(user_id)

        return True, '', session

    # ---------------- Session 查询 ----------------

    def get_session(self, session_id: str) -> Optional[ActiveSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def get_user_sessions(self, user_id: int) -> List[ActiveSession]:
        """获取某用户的所有 session"""
        with self._lock:
            ids = self._user_sessions.get(user_id, [])
            return [self._sessions[sid] for sid in ids if sid in self._sessions]

    def poll_status(self, session_id: str) -> Optional[Dict]:
        """查询某 session 的状态（触发轮询时调用）"""
        session = self.get_session(session_id)
        if session is None:
            return None

        with session.lock:
            session.last_poll_at = datetime.now()
            # 触发协议层的状态更新
            status = session.protocol.poll_status()

            info = session.protocol.get_login_info() or {}

            result = {
                'session_id': session_id,
                'status': status,
                'login_info': info,
                'error_msg': session.protocol.error_msg,
                'protocol': session.protocol.protocol_name,
                'account_id': session.account_id,
            }
            return result

    def get_qrcode(self, session_id: str) -> Optional[str]:
        session = self.get_session(session_id)
        if not session:
            return None
        return session.qrcode_data_url

    # ---------------- 消息与联系人 ----------------

    def send_message(self, session_id: str, conversation_id: str, content: str, msg_type: str = 'text') -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        return session.protocol.send_message(conversation_id, content, msg_type)

    def get_contacts(self, session_id: str) -> List[Dict]:
        session = self.get_session(session_id)
        if not session:
            return []
        return list(session.protocol.get_contacts() or [])

    def get_rooms(self, session_id: str) -> List[Dict]:
        session = self.get_session(session_id)
        if not session:
            return []
        return list(session.protocol.get_rooms() or [])

    # ---------------- 持久化与恢复 ----------------

    def close_session(self, session_id: str):
        """关闭并移除 session"""
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is None:
                return
            # 从 user_sessions 中移除
            user_sids = self._user_sessions.get(session.user_id, [])
            if session_id in user_sids:
                user_sids.remove(session_id)

            # 关闭协议
            try:
                session.protocol.close()
            except Exception:
                pass

    # ---------------- 内部工具 ----------------

    def _cleanup_old_sessions_locked(self):
        """移除超过 1 小时未轮询的 session（已持锁调用）"""
        cutoff = time.time() - 3600
        expired = []
        for sid, sess in list(self._sessions.items()):
            if (datetime.now().timestamp() - sess.last_poll_at.timestamp()) > 3600:
                expired.append(sid)
        for sid in expired:
            try:
                sess = self._sessions.pop(sid, None)
                if sess:
                    try:
                        sess.protocol.close()
                    except Exception:
                        pass
                    user_sids = self._user_sessions.get(sess.user_id, [])
                    if sid in user_sids:
                        user_sids.remove(sid)
            except Exception:
                pass

    def _enforce_limits_locked(self, current_user_id: int):
        """按用户限制 session 数量（持锁调用）"""
        # 用户限制
        user_sids = self._user_sessions.get(current_user_id, [])
        # 保留最近的 self._max_per_user 个
        if len(user_sids) > self._max_per_user:
            to_remove = user_sids[:-self._max_per_user]
            for sid in to_remove:
                try:
                    sess = self._sessions.pop(sid, None)
                    if sess:
                        try:
                            sess.protocol.close()
                        except Exception:
                            pass
                except Exception:
                    pass
            self._user_sessions[current_user_id] = user_sids[-self._max_per_user:]

        # 总数量限制
        while len(self._sessions) > self._max_total:
            oldest_sid, oldest_sess = next(iter(self._sessions.items()))
            try:
                self._sessions.pop(oldest_sid)
                try:
                    oldest_sess.protocol.close()
                except Exception:
                    pass
                user_sids = self._user_sessions.get(oldest_sess.user_id, [])
                if oldest_sid in user_sids:
                    user_sids.remove(oldest_sid)
            except Exception:
                pass

    # ---------------- 元信息 ----------------

    def get_available_protocols_info(self) -> List[Dict]:
        """返回给前端展示的协议列表"""
        return get_available_protocols()

    def get_default_protocol(self) -> str:
        return get_default_protocol_name()

    def stats(self) -> Dict:
        with self._lock:
            return {
                'total_sessions': len(self._sessions),
                'total_users': len(self._user_sessions),
                'default_protocol': get_default_protocol_name(),
            }


# ============================================================
# 全局单例
# ============================================================

_global_service: Optional[AccountHostingService] = None
_service_lock = threading.Lock()


def get_hosting_service() -> AccountHostingService:
    """获取全局托管服务单例"""
    global _global_service
    with _service_lock:
        if _global_service is None:
            _global_service = AccountHostingService()
        return _global_service
