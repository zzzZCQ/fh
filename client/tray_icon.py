# -*- coding: utf-8 -*-
"""系统托盘图标"""
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QApplication
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QFont
from PyQt5.QtCore import Qt


class TrayIcon(QSystemTrayIcon):
    """系统托盘图标类"""
    
    def __init__(self, on_open=None, on_history=None, on_settings=None, on_exit=None):
        super().__init__()
        self.on_open = on_open
        self.on_history = on_history
        self.on_settings = on_settings
        self.on_exit = on_exit
        self.menu = None
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        try:
            self.setIcon(self.create_icon('normal'))
            self.setToolTip('通知客户端')
            
            self.menu = QMenu()
            
            self.menu.addAction('打开主界面', self.handle_open)
            self.menu.addAction('历史通知', self.handle_history)
            self.menu.addSeparator()
            self.menu.addAction('设置', self.handle_settings)
            self.menu.addSeparator()
            self.menu.addAction('退出', self.handle_exit)
            
            self.setContextMenu(self.menu)
            self.activated.connect(self.on_activated)
        except Exception as e:
            print(f"初始化托盘图标失败: {e}")
    
    def create_icon(self, status='normal'):
        """创建图标"""
        colors = {
            'normal': (0, 200, 0),
            'new': (0, 150, 255),
            'urgent': (255, 0, 0),
            'offline': (128, 128, 128)
        }
        
        r, g, b = colors.get(status, colors['normal'])
        
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        painter.setBrush(QBrush(QColor(r, g, b)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        
        # 绘制文字
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, 'N')
        
        painter.end()
        
        return QIcon(pixmap)
    
    def on_activated(self, reason):
        """处理托盘图标激活"""
        if reason == QSystemTrayIcon.Trigger:
            self.handle_open()
        elif reason == QSystemTrayIcon.DoubleClick:
            self.handle_open()
    
    def handle_open(self):
        """打开主界面"""
        if self.on_open:
            self.on_open()
    
    def handle_history(self):
        """查看历史"""
        if self.on_history:
            self.on_history()
    
    def handle_settings(self):
        """打开设置"""
        if self.on_settings:
            self.on_settings()
    
    def handle_exit(self):
        """退出程序"""
        if self.on_exit:
            self.on_exit()
    
    def set_status(self, status):
        """设置图标状态"""
        self.setIcon(self.create_icon(status))
    
    def show_message(self, title, message, duration=3000):
        """显示气泡消息"""
        self.showMessage(title, message, QSystemTrayIcon.Information, duration)
    
    def set_has_new(self, has_new=True):
        """设置是否有新通知"""
        if has_new:
            self.set_status('new')
        else:
            self.set_status('normal')
    
    def set_offline(self):
        """设置离线状态"""
        self.set_status('offline')
        self.show_message('连接已断开', '正在尝试重新连接...')
    
    def set_online(self):
        """设置在线状态"""
        self.set_status('normal')
        self.show_message('已连接', '通知客户端已启动')
