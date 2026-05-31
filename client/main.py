# -*- coding: utf-8 -*-
"""通知客户端主程序"""
import sys
import os
import winsound
import winreg
import subprocess
import ctypes
import requests
from packaging import version as version_parser
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

# 版本号
CLIENT_VERSION = "1.0.1"

# 互斥锁，防止同一台电脑上运行多个客户端实例
MUTEX_NAME = "Global\\WeworkNotificationClientMutex"
mutex = None

def create_mutex():
    """创建命名互斥锁"""
    try:
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
        if mutex:
            if ctypes.get_last_error() == 0:
                return mutex
            else:
                # 已经有实例在运行了
                kernel32.CloseHandle(mutex)
                return None
        return None
    except Exception as e:
        print(f"创建互斥锁失败: {e}")
        return None

def release_mutex(mutex_handle):
    """释放互斥锁"""
    try:
        if mutex_handle:
            ctypes.windll.kernel32.ReleaseMutex(mutex_handle)
            ctypes.windll.kernel32.CloseHandle(mutex_handle)
    except Exception as e:
        print(f"释放互斥锁失败: {e}")

from settings import Settings
from tray_icon import TrayIcon
from notification_window import NotificationWindow
from websocket_client import WebSocketClient
from history_window import HistoryWindow
from wework_monitor import WeworkCallMonitor


class NotificationSignals(QObject):
    """信号类，用于跨线程通信"""
    notification_received = pyqtSignal(dict)
    connected = pyqtSignal()
    disconnected = pyqtSignal(str)
    auth_failed = pyqtSignal(str)


class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('登录设置')
        self.setFixedSize(400, 350)
        
        layout = QVBoxLayout()
        
        # 服务器地址（只读）
        layout.addWidget(QLabel('服务器地址:'))
        self.server_input = QLineEdit()
        self.server_input.setText(self.settings.get('server_url', 'http://192.168.100.22:5000'))
        self.server_input.setReadOnly(True)
        self.server_input.setStyleSheet('background-color: #f0f0f0;')
        layout.addWidget(self.server_input)
        
        layout.addWidget(QLabel('用户名:'))
        self.username_input = QLineEdit()
        self.username_input.setText(str(self.settings.get('username', '')))
        self.username_input.setPlaceholderText('请输入您的用户名')
        layout.addWidget(self.username_input)
        
        layout.addWidget(QLabel('密码:'))
        self.password_input = QLineEdit()
        self.password_input.setText(str(self.settings.get('password', '')))
        self.password_input.setPlaceholderText('请输入您的密码')
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_input)
        
        layout.addWidget(QLabel(f'音量 ({self.settings.get("volume", 80)}%):'))
        self.volume_slider = QComboBox()
        for v in [0, 20, 40, 60, 80, 100]:
            self.volume_slider.addItem(f'{v}%', v)
        self.volume_slider.setCurrentIndex(self.settings.get('volume', 80) // 20)
        layout.addWidget(self.volume_slider)
        
        # 开机自启动选项
        self.autostart_checkbox = QPushButton('设置开机自启动')
        self.autostart_checkbox.setCheckable(True)
        self.autostart_checkbox.setChecked(self.is_autostart_enabled())
        self.autostart_checkbox.clicked.connect(self.toggle_autostart)
        layout.addWidget(self.autostart_checkbox)
        
        save_btn = QPushButton('保存并连接')
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        self.setLayout(layout)
    
    def is_autostart_enabled(self):
        """检查是否启用开机自启动"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r"Software\Microsoft\Windows\CurrentVersion\Run", 
                               0, winreg.KEY_READ)
            value, _ = winreg.QueryValueEx(key, "NotificationClient")
            winreg.CloseKey(key)
            return True
        except:
            return False
    
    def toggle_autostart(self, checked):
        """切换开机自启动"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r"Software\Microsoft\Windows\CurrentVersion\Run", 
                               0, winreg.KEY_WRITE)
            
            if checked:
                exe_path = sys.executable
                script_path = os.path.abspath(__file__)
                winreg.SetValueEx(key, "NotificationClient", 0, winreg.REG_SZ, 
                                f'"{exe_path}" "{script_path}"')
                QMessageBox.information(self, '提示', '已启用开机自启动！')
            else:
                try:
                    winreg.DeleteValue(key, "NotificationClient")
                except:
                    pass
                QMessageBox.information(self, '提示', '已禁用开机自启动！')
            
            winreg.CloseKey(key)
        except Exception as e:
            QMessageBox.warning(self, '错误', f'设置失败: {str(e)}')
    
    def save_settings(self):
        """保存设置"""
        import requests
        
        server_url = self.server_input.text()
        username = self.username_input.text()
        password = self.password_input.text()
        
        # 先验证登录
        try:
            url = f"{server_url}/api/broadcast/auth"
            data = {
                'username': username,
                'password': password
            }
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    # 登录成功
                    self.settings.set('server_url', server_url)
                    self.settings.set('username', username)
                    self.settings.set('password', password)
                    self.settings.set('user_id', result.get('user_id', ''))
                    self.settings.set('token', result.get('token', ''))
                    self.settings.save()
                    QMessageBox.information(self, '提示', '设置已保存！登录成功！')
                    self.accept()
                else:
                    QMessageBox.warning(self, '错误', f'登录失败: {result.get("error", "未知错误")}')
            else:
                QMessageBox.warning(self, '错误', f'请求失败: {response.status_code}')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'网络错误: {str(e)}')


class MainWindow:
    """主窗口类"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.settings = Settings()
        self.notification_windows = []
        self.history_window = None
        self.is_exiting = False
        self.tray = None
        
        # 创建信号对象
        self.signals = NotificationSignals()
        self.signals.notification_received.connect(self._on_notification_ui)
        self.signals.connected.connect(self._on_connect_ui)
        self.signals.disconnected.connect(self._on_disconnect_ui)
        self.signals.auth_failed.connect(self._on_auth_failed_ui)
        
        # 先初始化托盘（必须在任何UI操作之前）
        self.init_tray()
        
        # 检查版本
        if not self.check_version():
            # 版本检查失败，不启动
            return
        
        if not self.settings.is_configured():
            # 未配置时显示设置窗口
            self.show_settings()
        
        self.init_websocket()
        self.init_wework_monitor()
        
        self.play_sound('start')
        
        # 检查是否已配置，没有配置则不启动连接
        if self.settings.is_configured():
            self.tray.show_message('已启动', f'通知客户端 v{CLIENT_VERSION} 已在后台运行')
        else:
            self.tray.show_message('未配置', '请点击托盘图标设置登录信息')
    
    def check_version(self):
        """检查客户端版本"""
        try:
            server_url = self.settings.get('server_url', 'http://192.168.100.22:5000')
            api_url = f"{server_url.rstrip('/')}/wework/api/version"
            
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    server_version = data.get('server_version', '1.0.0')
                    min_version = data.get('min_supported_version', '1.0.0')
                    release_date = data.get('release_date', '')
                    
                    # 检查版本
                    try:
                        client_ver = version_parser.parse(CLIENT_VERSION)
                        min_ver = version_parser.parse(min_version)
                        
                        if client_ver < min_ver:
                            QMessageBox.critical(
                                None, 
                                "版本过旧", 
                                f"客户端版本 v{CLIENT_VERSION} 过旧！\n"
                                f"最低支持版本: v{min_version}\n"
                                f"服务器版本: v{server_version}\n"
                                f"发布日期: {release_date}\n\n"
                                f"请联系管理员获取新版本！"
                            )
                            return False
                        
                        print(f"[版本检查] 客户端: v{CLIENT_VERSION}, 服务器: v{server_version}")
                    except Exception as e:
                        print(f"[版本检查] 版本解析失败: {e}")
            else:
                print(f"[版本检查] 获取版本信息失败: {response.status_code}")
        except Exception as e:
            print(f"[版本检查] 连接服务器失败: {e}")
        
        return True
    
    def init_tray(self):
        """初始化托盘"""
        self.tray = TrayIcon(
            on_open=self.on_open,
            on_history=self.on_history,
            on_settings=self.show_settings,
            on_exit=self.on_exit
        )
        self.tray.show()
    
    def init_websocket(self):
        """初始化WebSocket"""
        if not self.settings.is_configured():
            return
            
        self.ws_client = WebSocketClient(
            on_notification=self.on_notification,
            on_connect=self.on_connect,
            on_disconnect=self.on_disconnect,
            on_auth_failed=self.on_auth_failed
        )
        self.ws_client.start()
    
    def init_wework_monitor(self):
        """初始化企微通话监控"""
        self.wework_monitor = WeworkCallMonitor()
        self.wework_monitor.start()
    
    # ========== Socket线程回调 - 发送信号 ==========
    def on_notification(self, data):
        """收到新通知（Socket线程）"""
        print(f"收到通知: {data.get('title', '无标题')}")
        self.signals.notification_received.emit(data)
    
    def on_connect(self):
        """连接成功（Socket线程）"""
        print("WebSocket连接成功")
        self.signals.connected.emit()
    
    def on_disconnect(self, reason):
        """断开连接（Socket线程）"""
        print(f"WebSocket断开: {reason}")
        self.signals.disconnected.emit(reason)
    
    def on_auth_failed(self, reason):
        """认证失败（Socket线程）"""
        print(f"认证失败: {reason}")
        self.signals.auth_failed.emit(reason)
    
    # ========== UI线程槽函数 - 执行UI操作 ==========
    def _on_notification_ui(self, data):
        """处理通知（UI线程）"""
        priority = data.get('priority', 'normal')
        self.play_sound(priority)
        
        self.tray.show_message('新通知', data.get('title', '您有一条新通知'))
        self.tray.set_status('new')
        
        self.show_notification_window(data)
    
    def _on_connect_ui(self):
        """连接成功（UI线程）"""
        self.tray.set_status('normal')
    
    def _on_disconnect_ui(self, reason):
        """断开连接（UI线程）"""
        self.tray.set_offline()
        
        # 5秒后尝试重新连接
        if not self.is_exiting:
            QTimer.singleShot(5000, self.reconnect)
    
    def reconnect(self):
        """重新连接"""
        if not self.is_exiting and self.settings.is_configured():
            if hasattr(self, 'ws_client'):
                self.ws_client.stop()
            self.ws_client = WebSocketClient(
                on_notification=self.on_notification,
                on_connect=self.on_connect,
                on_disconnect=self.on_disconnect,
                on_auth_failed=self.on_auth_failed
            )
            self.ws_client.start()
    
    def _on_auth_failed_ui(self, reason):
        """认证失败（UI线程）"""
        self.tray.set_offline()
        self.tray.show_message('认证失败', '请检查用户名和密码')
    
    def show_notification_window(self, data):
        """显示通知窗口"""
        window = NotificationWindow(
            data,
            on_confirm=self.on_confirm,
            on_close=self.on_close
        )
        window.show()
        self.notification_windows.append(window)
    
    def on_confirm(self, notification_id):
        """确认通知"""
        # 先通过API确认
        self.confirm_notification_via_api(notification_id)
        
        if hasattr(self, 'ws_client') and self.ws_client:
            self.ws_client.send_confirm(notification_id)
        self.tray.set_status('normal')
        print(f"已确认通知: {notification_id}")
    
    def confirm_notification_via_api(self, notification_id):
        """通过API确认通知"""
        try:
            import requests
            server_url = self.settings.get('server_url', 'http://192.168.100.22:5000')
            user_id = self.settings.get('user_id', '')
            token = self.settings.get('token', '')
            
            if not user_id or not token:
                print('未配置用户信息')
                return
            
            url = f"{server_url}/api/broadcast/user/confirm"
            data = {
                'user_id': user_id,
                'token': token,
                'notification_id': notification_id
            }
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print('API确认成功')
                else:
                    print('API确认失败:', result.get('error'))
        except Exception as e:
            print('API确认出错:', str(e))
    
    def on_close(self, notification_id):
        """关闭通知"""
        self.tray.set_status('normal')
        print(f"已关闭通知: {notification_id}")
    
    def on_open(self):
        """打开主界面"""
        self.show_history()
    
    def on_history(self):
        """查看历史"""
        self.show_history()
    
    def show_history(self):
        """显示历史通知窗口"""
        if not self.settings.is_configured():
            QMessageBox.information(None, '提示', '请先配置登录信息')
            return
        
        server_url = self.settings.get('server_url', 'http://192.168.100.22:5000')
        user_id = self.settings.get('user_id', '')
        token = self.settings.get('token', '')
        
        if not user_id or not token:
            QMessageBox.information(None, '提示', '请先完成登录配置')
            return
        
        if not self.history_window:
            self.history_window = HistoryWindow(server_url, user_id, token)
            self.history_window.show()
        else:
            self.history_window.raise_()
            self.history_window.activateWindow()
            self.history_window.load_notifications()
    
    def show_settings(self):
        """显示设置对话框"""
        dialog = SettingsDialog(self.settings)
        result = dialog.exec_()
        
        # 设置保存后，重新初始化WebSocket
        if result == QDialog.Accepted:
            if hasattr(self, 'ws_client'):
                self.ws_client.stop()
            self.init_websocket()
    
    def on_exit(self):
        """退出程序"""
        self.is_exiting = True
        
        if self.history_window:
            self.history_window.close()
        if hasattr(self, 'ws_client'):
            self.ws_client.stop()
        if hasattr(self, 'wework_monitor'):
            self.wework_monitor.stop()
        
        # 释放互斥锁
        global mutex
        if mutex:
            release_mutex(mutex)
        
        self.app.quit()
    
    def play_sound(self, sound_type):
        """播放声音"""
        if not self.settings.get('sound_enabled', True):
            return
        
        sound_map = {
            'normal': winsound.MB_ICONASTERISK,
            'important': winsound.MB_ICONHAND,
            'urgent': winsound.MB_ICONWARNING,
            'start': winsound.MB_ICONASTERISK
        }
        
        winsound.MessageBeep(sound_map.get(sound_type, winsound.MB_ICONASTERISK))
    
    def run(self):
        """运行应用"""
        # 设置为静默模式（无窗口）
        self.app.setQuitOnLastWindowClosed(False)
        sys.exit(self.app.exec_())


if __name__ == '__main__':
    # 先尝试获取互斥锁
    mutex = create_mutex()
    if not mutex:
        # 已经有实例在运行了
        app = QApplication(sys.argv)
        QMessageBox.warning(None, "警告", "客户端已经在运行中！\n同一台电脑上只能运行一个客户端实例。")
        sys.exit(1)
    
    try:
        window = MainWindow()
        window.run()
    finally:
        # 释放互斥锁
        if mutex:
            release_mutex(mutex)
