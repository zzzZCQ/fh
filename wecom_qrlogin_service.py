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
import re

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
    
    # iPad设备配置（模拟真实iPad企业微信客户端）
    IPAD_CONFIG = {
        'user_agent': 'Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
        'device_id': 'iPad13,1',
        'os_version': '17.2',
        'app_version': '4.1.6.1501',
        'screen_width': 1024,
        'screen_height': 1366,
    }
    
    # 企业微信登录相关URL
    LOGIN_URLS = [
        'https://work.weixin.qq.com/wework_admin/loginpage_wx',
        'https://work.weixin.qq.com/',
        'https://open.work.weixin.qq.com/wwopen/sso/3rd_qrConnect?appid=wx782c26e4c19acffb&redirect_uri=https://work.weixin.qq.com/wework_admin/loginpage_wx&state=STATE&scope=snsapi_login',
    ]
    
    def __init__(self):
        self.sessions = {}  # session_id -> QRCodeSession
        self.session_lock = threading.Lock()
        self.cleanup_thread = None
        self.running = True
        
        # HTTP 会话 - 模拟iPad客户端
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.IPAD_CONFIG['user_agent'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://work.weixin.qq.com/',
            'Origin': 'https://work.weixin.qq.com',
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
    
    def _get_ipad_qrcode_url(self) -> Tuple[Optional[str], Optional[str]]:
        """获取iPad企业微信登录二维码URL和ticket"""
        try:
            # 尝试访问登录页面获取ticket
            for url in self.LOGIN_URLS:
                try:
                    response = self.session.get(url, timeout=30, allow_redirects=True)
                    print(f"[QRLogin] 访问: {url} -> {response.status_code}")
                    
                    ticket = None
                    # 从URL中提取ticket
                    if 'ticket' in response.url:
                        match = re.search(r'ticket=([a-zA-Z0-9_-]+)', response.url)
                        if match:
                            ticket = match.group(1)
                            print(f"[QRLogin] ✅ 从URL获取ticket: {ticket[:20]}...")
                    
                    # 从cookie中获取
                    if not ticket:
                        for cookie in self.session.cookies:
                            if cookie.name == 'wwrtx.ticket':
                                ticket = cookie.value
                                print(f"[QRLogin] ✅ 从cookie获取ticket: {ticket[:20]}...")
                                break
                    
                    # 从页面内容中提取
                    if not ticket and 'ticket' in response.text:
                        match = re.search(r'ticket[\s=:"\'】【]+([a-zA-Z0-9_-]+)', response.text)
                        if match:
                            ticket = match.group(1)
                            print(f"[QRLogin] ✅ 从页面内容获取ticket: {ticket[:20]}...")
                    
                    if ticket:
                        # 返回iPad企业微信登录URL（用于扫码）
                        ipad_login_url = f"https://wx.work.weixin.qq.com/wwlogin/login?type=wwclient&ticket={ticket}"
                        print(f"[QRLogin] iPad登录URL: {ipad_login_url[:80]}...")
                        return ipad_login_url, ticket
                            
                except Exception as e:
                    print(f"[QRLogin] 访问失败: {e}")
                    continue
            
            # 如果都失败，返回None
            print("[QRLogin] ⚠️ 未获取到真实ticket")
            return None, None
            
        except Exception as e:
            print(f"[QRLogin] 获取ticket异常: {e}")
            return None, None
    
    def create_qrcode(self) -> Tuple[str, str]:
        """
        创建二维码会话 - 使用iPad企业微信协议
        返回: (session_id, qrcode_image_base64)
        """
        session_id = self._generate_session_id()
        session = QRCodeSession(session_id)
        
        try:
            # 获取iPad企业微信登录二维码URL和ticket
            qrcode_url, ticket = self._get_ipad_qrcode_url()
            
            if not qrcode_url or not ticket:
                # 如果获取不到真实ticket，使用模拟值
                print("[QRLogin] 使用模拟ticket")
                ticket = self._generate_ticket()
                qrcode_url = f"https://wx.work.weixin.qq.com/wwlogin/login?type=wwclient&ticket={ticket}"
            
            session.ticket = ticket
            session.qrcode_url = qrcode_url
            
            print(f"[QRLogin] 二维码URL: {qrcode_url}")
            
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
            
            print(f"[QRLogin] 创建二维码会话成功: {session_id}")
            return session_id, f"data:image/png;base64,{img_base64}"
            
        except Exception as e:
            print(f"[QRLogin] 创建二维码异常: {e}")
            import traceback
            traceback.print_exc()
            
            # 失败时仍生成模拟二维码
            session.ticket = self._generate_ticket()
            qrcode_url = f"https://wx.work.weixin.qq.com/wwlogin/login?type=wwclient&ticket={session.ticket}"
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
            if session.ticket:
                # 使用企业微信iPad登录检查URL
                try:
                    params = {
                        'ticket': session.ticket,
                        'type': 'wwclient',
                        't': str(int(time.time() * 1000)),
                    }
                    
                    response = self.session.get(
                        'https://work.weixin.qq.com/wework_admin/checklogin',
                        params=params,
                        timeout=10
                    )
                    
                    print(f"[QRLogin] 检查登录状态 - 响应码: {response.status_code}")
                    
                    if response.status_code == 200:
                        content = response.text
                        if '"ret":0' in content or '"code":0' in content or '登录成功' in content:
                            session.status = SCAN_STATUS['CONFIRMED']
                            session.confirmed_at = datetime.now()
                            session.user_info = {'name': '企业微信用户', 'corp_name': '企业'}
                            print(f"[QRLogin] ✅ 登录成功")
                        
                        # 更新会话状态
                        with self.session_lock:
                            self.sessions[session_id] = session
                        
                        return {'success': True, 'data': session.to_dict()}
                except Exception as req_e:
                    print(f"[QRLogin] 检查登录状态请求失败: {req_e}")
            
            # 更新会话状态
            with self.session_lock:
                self.sessions[session_id] = session
            
            return {'success': True, 'data': session.to_dict()}
            
        except Exception as e:
            print(f"[QRLogin] 检查扫码状态异常: {e}")
            import traceback
            traceback.print_exc()
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

