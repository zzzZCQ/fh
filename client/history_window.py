# -*- coding: utf-8 -*-
"""历史通知列表窗口"""
import sys
import requests
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame,
    QMessageBox, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap


class LoadNotificationsThread(QThread):
    """加载通知的线程"""
    loaded = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, server_url, user_id, token):
        super().__init__()
        self.server_url = server_url
        self.user_id = user_id
        self.token = token
    
    def run(self):
        try:
            url = f"{self.server_url}/api/broadcast/user/notifications"
            params = {
                'user_id': self.user_id,
                'token': self.token
            }
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.loaded.emit(data.get('notifications', []))
                else:
                    self.error.emit(data.get('error', '加载失败'))
            else:
                self.error.emit(f'请求失败: {response.status_code}')
        except Exception as e:
            self.error.emit(f'网络错误: {str(e)}')


class NotificationItemWidget(QFrame):
    """单个通知项"""
    
    def __init__(self, notification_data, server_url, user_id, token, parent=None):
        super().__init__(parent)
        self.notification = notification_data
        self.server_url = server_url
        self.user_id = user_id
        self.token = token
        self.init_ui()
    
    def init_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet('''
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 12px;
                margin: 4px;
            }
            QFrame:hover {
                background-color: #f5f5f5;
            }
        ''')
        
        layout = QVBoxLayout()
        
        # 标题和状态
        title_layout = QHBoxLayout()
        
        title_label = QLabel(self.notification.get('title', '无标题'))
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        
        # 重要性标签
        priority = self.notification.get('priority', 'normal')
        priority_color = {
            'normal': 'blue',
            'important': '#ff9800',
            'urgent': '#f44336'
        }.get(priority, 'blue')
        priority_text = {
            'normal': '普通',
            'important': '重要',
            'urgent': '紧急'
        }.get(priority, '普通')
        
        priority_label = QLabel(priority_text)
        priority_label.setStyleSheet(f'''
            color: white;
            background-color: {priority_color};
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
        ''')
        title_layout.addWidget(priority_label)
        
        # 确认状态
        if self.notification.get('is_confirmed'):
            confirmed_label = QLabel('✓ 已确认')
            confirmed_label.setStyleSheet('color: #4CAF50; font-weight: bold;')
            title_layout.addWidget(confirmed_label)
        
        layout.addLayout(title_layout)
        
        # 内容
        content = self.notification.get('content', '')
        if len(content) > 100:
            content = content[:100] + '...'
        
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet('color: #666;')
        layout.addWidget(content_label)
        
        # 时间
        sent_time = self.notification.get('sent_time', '')
        if sent_time:
            time_label = QLabel(f'发送时间: {sent_time[:19].replace("T", " ")}')
            time_label.setStyleSheet('color: #999; font-size: 11px;')
            layout.addWidget(time_label)
        
        # 按钮区
        button_layout = QHBoxLayout()
        
        # 确认按钮（如果还没确认）
        if not self.notification.get('is_confirmed'):
            self.confirm_btn = QPushButton('我已知晓')
            self.confirm_btn.setStyleSheet('''
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 6px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            ''')
            self.confirm_btn.clicked.connect(self.confirm_notification)
            button_layout.addWidget(self.confirm_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def confirm_notification(self):
        """确认通知"""
        try:
            url = f"{self.server_url}/api/broadcast/user/confirm"
            data = {
                'user_id': self.user_id,
                'token': self.token,
                'notification_id': self.notification.get('id')
            }
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.notification['is_confirmed'] = True
                    # 重新初始化UI
                    for i in reversed(range(self.layout().count())):
                        item = self.layout().itemAt(i)
                        if item:
                            widget = item.widget()
                            if widget:
                                widget.setParent(None)
                    self.init_ui()
                    QMessageBox.information(self, '成功', '确认成功!')
                else:
                    QMessageBox.warning(self, '失败', result.get('error', '确认失败'))
            else:
                QMessageBox.warning(self, '失败', f'请求失败: {response.status_code}')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'网络错误: {str(e)}')


class HistoryWindow(QMainWindow):
    """历史通知窗口"""
    
    def __init__(self, server_url, user_id, token):
        super().__init__()
        self.server_url = server_url
        self.user_id = user_id
        self.token = token
        self.notifications = []
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle('通知历史')
        self.setMinimumSize(600, 700)
        
        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        
        # 标题
        title_label = QLabel('历史通知')
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(16)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 刷新按钮
        refresh_btn = QPushButton('刷新列表')
        refresh_btn.setStyleSheet('''
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        ''')
        refresh_btn.clicked.connect(self.load_notifications)
        layout.addWidget(refresh_btn)
        
        # 滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.addStretch()
        self.content_widget.setLayout(self.content_layout)
        
        scroll_area.setWidget(self.content_widget)
        layout.addWidget(scroll_area)
        
        central_widget.setLayout(layout)
        
        # 加载通知
        self.load_notifications()
    
    def load_notifications(self):
        """加载通知"""
        # 先显示加载中
        for i in reversed(range(self.content_layout.count() - 1)):
            widget = self.content_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        loading_label = QLabel('加载中...')
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet('color: #999; padding: 40px;')
        self.content_layout.insertWidget(0, loading_label)
        
        # 启动线程加载
        self.load_thread = LoadNotificationsThread(
            self.server_url,
            self.user_id,
            self.token
        )
        self.load_thread.loaded.connect(self.on_notifications_loaded)
        self.load_thread.error.connect(self.on_load_error)
        self.load_thread.start()
    
    def on_notifications_loaded(self, notifications):
        """通知加载完成"""
        # 清除加载标签
        for i in reversed(range(self.content_layout.count() - 1)):
            widget = self.content_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        self.notifications = notifications
        
        if not notifications:
            empty_label = QLabel('暂无通知')
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet('color: #999; padding: 40px;')
            self.content_layout.insertWidget(0, empty_label)
            return
        
        # 添加通知项
        for notification in notifications:
            item_widget = NotificationItemWidget(
                notification,
                self.server_url,
                self.user_id,
                self.token
            )
            self.content_layout.insertWidget(self.content_layout.count() - 1, item_widget)
    
    def on_load_error(self, error_msg):
        """加载出错"""
        for i in reversed(range(self.content_layout.count() - 1)):
            widget = self.content_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        error_label = QLabel(f'加载失败: {error_msg}')
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet('color: #f44336; padding: 40px;')
        self.content_layout.insertWidget(0, error_label)
