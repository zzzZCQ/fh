# -*- coding: utf-8 -*-
"""通知窗口"""
import os
import time
import requests
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPixmap, QImage, QPainter, QFont, QColor, QBrush, QPen
from settings import Settings


class NotificationWindow(QWidget):
    """通知窗口类"""
    
    PRIORITY_COLORS = {
        'normal': {'border': '#3498db', 'bg': '#ffffff', 'title': '#2c3e50'},
        'important': {'border': '#f39c12', 'bg': '#fffef0', 'title': '#2c3e50'},
        'urgent': {'border': '#e74c3c', 'bg': '#fff5f5', 'title': '#c0392b'}
    }
    
    def __init__(self, notification_data, on_confirm, on_close):
        super().__init__()
        self.notification_data = notification_data
        self.on_confirm = on_confirm
        self.on_close = on_close
        self.settings = Settings()
        self.downloaded_image = None
        
        self.init_ui()
        self.load_image()
        self.start_auto_hide()
        self.animate_in()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        width = 600
        height = 450
        
        # 获取屏幕几何信息，处理screen()返回None的情况
        screen = self.screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is not None:
            screen_geometry = screen.geometry()
            x = screen_geometry.right() - width - 20
            y = screen_geometry.top() + 20
        else:
            x = 100
            y = 100
        self.setGeometry(x, y, width, height)
        
        container = QWidget(self)
        container.setGeometry(0, 0, width, height)
        
        priority = self.notification_data.get('priority', 'normal')
        colors = self.PRIORITY_COLORS.get(priority, self.PRIORITY_COLORS['normal'])
        
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {colors['bg']};
                border: 3px solid {colors['border']};
                border-radius: 10px;
            }}
            QPushButton {{
                background-color: {colors['border']};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {colors['border']}dd;
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton('✕')
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.handle_close)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(300)
        self.image_label.setStyleSheet("border: none;")
        layout.addWidget(self.image_label)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        confirm_btn = QPushButton('✓ 我已知晓')
        confirm_btn.setFixedSize(150, 40)
        confirm_btn.clicked.connect(self.handle_confirm)
        btn_layout.addWidget(confirm_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        if priority == 'urgent':
            self.start_blink_effect()
    
    def load_image(self):
        """加载通知图片"""
        image_url = self.notification_data.get('image_url')
        if not image_url:
            self.show_placeholder()
            return
        
        if image_url.startswith('http'):
            url = image_url
        else:
            server_url = self.settings.get('server_url', 'http://localhost:5000')
            url = server_url.rstrip('/') + image_url
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                
                scaled_pixmap = pixmap.scaled(
                    560, 350,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
                self.downloaded_image = pixmap
        except Exception as e:
            print(f"加载图片失败: {e}")
            self.show_placeholder()
    
    def show_placeholder(self):
        """显示占位符"""
        self.image_label.setText('通知图片加载中...')
        self.image_label.setStyleSheet("color: gray; font-size: 16px;")
    
    def start_auto_hide(self):
        """启动自动隐藏定时器"""
        priority = self.notification_data.get('priority', 'normal')
        durations = {
            'normal': self.settings.get('normal_duration', 10),
            'important': self.settings.get('important_duration', 30),
            'urgent': self.settings.get('urgent_duration', 0)
        }
        
        duration = durations.get(priority, 5)
        
        if duration > 0:
            self.hide_timer = QTimer()
            self.hide_timer.timeout.connect(self.handle_close)
            self.hide_timer.setSingleShot(True)
            self.hide_timer.start(duration * 1000)
    
    def start_blink_effect(self):
        """紧急通知闪烁效果"""
        self.blink_timer = QTimer()
        self.blink_count = 0
        self.blink_timer.timeout.connect(self.toggle_blink)
        self.blink_timer.start(500)
    
    def toggle_blink(self):
        """切换闪烁状态"""
        self.blink_count += 1
        if self.blink_count > 20:
            self.blink_timer.stop()
            return
        
        current_opacity = self.windowOpacity()
        new_opacity = 0.3 if current_opacity > 0.5 else 1.0
        self.setWindowOpacity(new_opacity)
    
    def animate_in(self):
        """入场动画"""
        self.setWindowOpacity(0)
        
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.start()
    
    def animate_out(self, callback):
        """出场动画"""
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(200)
        self.animation.setStartValue(1)
        self.animation.setEndValue(0)
        self.animation.setEasingCurve(QEasingCurve.InCubic)
        self.animation.finished.connect(callback)
        self.animation.start()
    
    def handle_confirm(self):
        """处理确认按钮"""
        self.stop_timers()
        
        if self.on_confirm:
            self.on_confirm(self.notification_data.get('id'))
        
        self.animate_out(self.close)
    
    def handle_close(self):
        """处理关闭按钮"""
        self.stop_timers()
        
        if self.on_close:
            self.on_close(self.notification_data.get('id'))
        
        self.animate_out(self.close)
    
    def stop_timers(self):
        """停止所有定时器"""
        if hasattr(self, 'hide_timer'):
            self.hide_timer.stop()
        if hasattr(self, 'blink_timer'):
            self.blink_timer.stop()
