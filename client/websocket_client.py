# -*- coding: utf-8 -*-
"""Socket.IO客户端"""
import threading
import time
import requests
import socketio

from settings import Settings


class WebSocketClient:
    """Socket.IO客户端类"""
    
    def __init__(self, on_notification=None, on_connect=None, on_disconnect=None, on_auth_failed=None):
        self.settings = Settings()
        self.on_notification = on_notification
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.on_auth_failed = on_auth_failed
        self.sio = None
        self.running = False
        self.thread = None
    
    def authenticate(self):
        """认证获取token"""
        username = self.settings.get('username')
        password = self.settings.get('password')
        
        if not username or not password:
            return None
        
        server_url = self.settings.get('server_url', 'http://192.168.100.22:5000')
        auth_url = f"{server_url}/api/broadcast/auth"
        
        try:
            response = requests.post(auth_url, json={
                'username': username,
                'password': password
            }, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.settings.set('user_id', data['user_id'])
                    self.settings.set('token', data['token'])
                    return data
                else:
                    return None
        except Exception as e:
            print(f"认证失败: {e}")
            return None
    
    def start(self):
        """启动Socket.IO连接"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """停止Socket.IO连接"""
        self.running = False
        if self.sio:
            try:
                self.sio.disconnect()
            except:
                pass
        if self.thread:
            self.thread.join(timeout=2)
    
    def _run(self):
        """运行Socket.IO连接（在线程中）"""
        while self.running:
            try:
                print(f"========== 开始一轮连接 ==========")
                auth_result = self.authenticate()
                if not auth_result:
                    if self.on_auth_failed:
                        self.on_auth_failed('用户名或密码错误')
                    time.sleep(10)
                    continue
                
                user_id = self.settings.get('user_id')
                token = self.settings.get('token')
                
                if not user_id or not token:
                    if self.on_disconnect:
                        self.on_disconnect('认证失败')
                    time.sleep(5)
                    continue
                
                server_url = self.settings.get('server_url', 'http://192.168.100.22:5000')
                connect_url = f"{server_url}?user_id={user_id}&token={token}"
                print(f"准备连接到: {connect_url}")
                
                # 创建新的socketio客户端，禁用自动重连（由应用层控制）
                self.sio = socketio.Client(
                    logger=False, 
                    engineio_logger=False,
                    reconnection=False  # 禁用自动重连
                )
                
                @self.sio.on('connect')
                def on_connect():
                    print(f"Socket.IO已连接")
                    if self.on_connect:
                        self.on_connect()
                
                @self.sio.on('disconnect')
                def on_disconnect():
                    print(f"Socket.IO已断开")
                    if self.on_disconnect:
                        self.on_disconnect('连接断开')
                
                @self.sio.on('error')
                def on_error(data):
                    print(f"Socket.IO错误: {data}")
                
                @self.sio.on('connected')
                def on_connected(data):
                    print(f"已连接: {data.get('username', 'Unknown')}")
                
                @self.sio.on('new_notification')
                def on_new_notification(data):
                    print(f"收到通知: {data.get('title', '无标题')}")
                    if self.on_notification:
                        self.on_notification(data)
                
                @self.sio.on('confirm_success')
                def on_confirm_success(data):
                    print(f"确认成功: 通知 {data.get('notification_id')}")
                
                @self.sio.on('receipt_confirmed')
                def on_receipt_confirmed(data):
                    print(f"收到确认: 通知 {data.get('notification_id')}")
                
                print(f"正在连接服务端...")
                self.sio.connect(
                    connect_url,
                    transports=['polling']  # 使用轮询，避免WebSocket兼容性问题
                )
                print(f"连接成功，进入等待状态...")
                
                self.sio.wait()
                print(f"sio.wait() 返回")
                
            except Exception as e:
                print(f"Socket.IO错误: {e}")
                if self.on_disconnect:
                    self.on_disconnect(str(e))
            
            if self.running:
                # 连接失败后等待5秒再重试
                print(f"等待5秒后重新连接...")
                time.sleep(5)
    
    def send_confirm(self, notification_id):
        """发送确认"""
        if self.sio:
            try:
                self.sio.emit('confirm_notification', {
                    'notification_id': notification_id,
                    'user_id': self.settings.get('user_id')
                })
                return True
            except Exception as e:
                print(f"发送确认失败: {e}")
                return False
        return False
    
    def send_received(self, notification_id):
        """发送已收到标记"""
        if self.sio:
            try:
                self.sio.emit('mark_received', {
                    'notification_id': notification_id,
                    'user_id': self.settings.get('user_id')
                })
                return True
            except Exception as e:
                print(f"发送收到标记失败: {e}")
                return False
        return False