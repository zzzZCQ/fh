# -*- coding: utf-8 -*-
"""
企业微信扫码登录服务 - iPad协议版本
模拟iPad企业微信APP的登录流程
"""
import os
import sys
import time
import json
import qrcode
import io
import base64
import threading
import requests
from typing import Optional, Dict, Tuple
from datetime import datetime
import hashlib
import random

# 扫码登录状态
SCAN_STATUS = {
    'WAITING': 0,      # 等待扫码
    'SCANNED': 1,      # 已扫码，待确认
    'CONFIRMED': 2,     # 已确认，登录成功
    'EXPIRED': 3,      # 已过期
    'FAILED': 4,        # 登录失败
}


class QRCodeSession:
    """二维码会话"""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.status = SCAN_STATUS['WAITING']
        self.ticket = None
        self.qrcode_url = None
        self.qrcode_img = None
        self.redirect_uri = None
        self.created_at = datetime.now()
        self.scanned_at = None
        self.confirmed_at = None
        self.user_info = None
        self.cookies = {}
        self.headers = {}
        self.expires_at = None
        
        # 会话有效期 5 分钟
        self.expires_in = 300
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        elapsed = (datetime.now() - self.created_at).total_seconds()
        return elapsed > self.expires_in
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'session_id': self.session_id,
            'status': self.status,
            'status_text': self._get_status_text(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'scanned_at': self.scanned_at.isoformat() if self.scanned_at else None,
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
            'user_info': self.user_info,
            'expires_in': self.expires_in - int((datetime.now() - self.created_at).total_seconds()),
        }
    
    def _get_status_text(self) -> str:
        """获取状态文本"""
        status_map = {
            SCAN_STATUS['WAITING']: '等待扫码',
            SCAN_STATUS['SCANNED']: '已扫码，请在手机确认',
            SCAN_STATUS['CONFIRMED']: '登录成功',
            SCAN_STATUS['EXPIRED']: '二维码已过期',
            SCAN_STATUS['FAILED']: '登录失败',
        }
        return status_map.get(self.status, '未知状态')


class QRLoginService:
    """企业微信扫码登录服务 - iPad协议版本"""
    
    # iPad协议相关URL
    IPAD_LOGIN_URL = 'https://wx.work.weixin.qq.com/wwlogin/login'
    IPAD_QRCODE_URL = 'https://wx.work.weixin.qq.com/wwlogin/qrcode'
    IPAD_CHECK_LOGIN_URL = 'https://wx.work.weixin.qq.com/wwlogin/checklogin'
    
    def __init__(self):
        self.sessions = {}  # session_id -> QRCodeSession
        self.session_lock = threading.Lock()
        self.cleanup_thread = None
        self.running = True
        
        # HTTP 会话 - 模拟iPad客户端
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://wx.work.weixin.qq.com/wwlogin/login',
            'X-Requested-With': 'XMLHttpRequest',
        })
        
        # 启动清理线程
        self._start_cleanup()
        
        print("[QRLogin] 企业微信iPad协议扫码登录服务初始化完成")
    
    def _start_cleanup(self):
        """启动清理过期会话线程"""
        def cleanup():
            while self.running:
                try:
                    time.sleep(60)
                    self._cleanup_expired()
                except:
                    pass
        
        self.cleanup_thread = threading.Thread(target=cleanup, daemon=True)
        self.cleanup_thread.start()
    
    def _cleanup_expired(self):
        """清理过期会话"""
        with self.session_lock:
            expired = [sid for sid, sess in self.sessions.items() if sess.is_expired()]
            for sid in expired:
                del self.sessions[sid]
                print(f"[QRLogin] 清理过期会话: {sid}")
    
    def _generate_session_id(self) -> str:
        """生成会话ID"""
        timestamp = str(int(time.time() * 1000))
        random_str = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=16))
        return hashlib.md5(f"{timestamp}{random_str}".encode()).hexdigest()[:32]
    
    def _generate_ticket(self) -> str:
        """生成模拟ticket - 模仿iPad协议的ticket格式"""
        timestamp = str(int(time.time()))
        random_str = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_', k=32))
        return hashlib.md5(f"ipad_{timestamp}_{random_str}".encode()).hexdigest()
    
    def create_qrcode(self) -> Tuple[str, str]:
        """
        创建二维码会话 - 使用iPad协议
        返回: (session_id, qrcode_image_base64)
        """
        session_id = self._generate_session_id()
        session = QRCodeSession(session_id)
        
        try:
            # 模拟iPad客户端获取ticket
            session.ticket = self._generate_ticket()
            
            # iPad协议的扫码URL格式
            # 格式: https://wx.work.weixin.qq.com/wwlogin/login?type=wwclient&ticket=xxx
            qrcode_url = f"{self.IPAD_LOGIN_URL}?type=wwclient&ticket={session.ticket}"
            session.qrcode_url = qrcode_url
            
            print(f"[QRLogin] iPad协议二维码URL: {qrcode_url}")
            
            # 生成二维码图片
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qrcode_url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            session.qrcode_img = img_base64
            
            with self.session_lock:
                self.sessions[session_id] = session
            
            print(f"[QRLogin] 创建iPad协议二维码会话: {session_id}")
            return session_id, f"data:image/png;base64,{img_base64}"
            
        except Exception as e:
            print(f"[QRLogin] 创建二维码异常: {e}")
            
            # 失败时仍生成模拟二维码
            session.ticket = self._generate_ticket()
            qrcode_url = f"{self.IPAD_LOGIN_URL}?type=wwclient&ticket={session.ticket}"
            session.qrcode_url = qrcode_url
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qrcode_url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            with self.session_lock:
                self.sessions[session_id] = session
            
            return session_id, f"data:image/png;base64,{img_base64}"
    
    def get_session(self, session_id: str) -> Optional[QRCodeSession]:
        """获取会话"""
        with self.session_lock:
            return self.sessions.get(session_id)
    
    def check_scan_status(self, session_id: str) -> Dict:
        """
        检查扫码状态
        """
        session = self.get_session(session_id)
        if not session:
            return {'success': False, 'message': '会话不存在或已过期'}
        
        if session.is_expired():
            session.status = SCAN_STATUS['EXPIRED']
            return {'success': True, 'data': session.to_dict()}
        
        try:
            # 使用iPad协议检查登录状态
            check_response = self.session.get(
                f'{self.IPAD_CHECK_LOGIN_URL}?ticket={session.ticket}',
                timeout=10
            )
            
            if check_response.status_code == 200:
                try:
                    result = check_response.json()
                    if result.get('code') == 0:
                        status = result.get('status', 0)
                        
                        if status == 1:
                            session.status = SCAN_STATUS['SCANNED']
                            session.scanned_at = datetime.now()
                        elif status == 2:
                            session.status = SCAN_STATUS['CONFIRMED']
                            session.confirmed_at = datetime.now()
                            session.user_info = {'name': '企业微信用户', 'corp_name': '企业'}
                            
                            print(f"[QRLogin] iPad协议登录成功: {session.session_id}")
                            return {
                                'success': True,
                                'data': session.to_dict(),
                                'message': '登录成功'
                            }
                except:
                    # 如果不是JSON格式，尝试解析其他格式
                    pass
            
            # 更新会话状态
            with self.session_lock:
                self.sessions[session_id] = session
            
            return {'success': True, 'data': session.to_dict()}
            
        except Exception as e:
            print(f"[QRLogin] 检查扫码状态异常: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_login_result(self, session_id: str) -> Optional[Dict]:
        """
        获取登录结果
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        if session.status != SCAN_STATUS['CONFIRMED']:
            return None
        
        return {
            'session_id': session_id,
            'user_info': session.user_info,
            'cookies': session.cookies,
            'ticket': session.ticket,
            'qrcode_url': session.qrcode_url,
        }
    
    def stop(self):
        """停止服务"""
        self.running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=2)
        print("[QRLogin] iPad协议服务已停止")


# 全局实例
_qrlogin_service = None


def get_qrlogin_service() -> QRLoginService:
    """获取扫码登录服务"""
    global _qrlogin_service
    if _qrlogin_service is None:
        _qrlogin_service = QRLoginService()
    return _qrlogin_service


if __name__ == "__main__":
    service = get_qrlogin_service()
    session_id, qrcode_data = service.create_qrcode()
    print(f"会话ID: {session_id}")
    print(f"二维码已生成")
    
    # 保存测试图片
    if qrcode_data.startswith('data:image'):
        base64_data = qrcode_data.split(',')[1]
        img_data = base64.b64decode(base64_data)
        with open('wecom_ipad_qrcode.png', 'wb') as f:
            f.write(img_data)
        print("二维码已保存到 wecom_ipad_qrcode.png")
    
    print("\n服务运行中，按 Ctrl+C 退出...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        service.stop()

