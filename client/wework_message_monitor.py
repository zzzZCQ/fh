# -*- coding: utf-8 -*-
"""企业微信聊天消息监控模块 - 监控聊天窗口，检测关键词"""
import threading
import time
import requests
import datetime
import win32gui
import win32con
import win32ui
import win32api
import re
import os
import json
import base64
import uuid
from PIL import Image, ImageEnhance
from settings import Settings


class WeworkMessageMonitor:
    """企业微信聊天消息监控"""

    # 监控关键词列表
    KEYWORDS = [
        '已学习',
        '学习完成',
        '学习了',
        '看完了',
        '听完了',
        '收到',
        '知道了',
        '好的',
    ]

    def __init__(self):
        self.settings = Settings()
        self.running = False
        self.thread = None
        self.client_id = str(uuid.uuid4())
        self.last_heartbeat_time = 0
        self.user_id = self.settings.get('user_id')
        self.user_name = self.settings.get('username', '')
        self.log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wework_message.log')
        self.message_recording_enabled = True  # 默认启用消息监控
        self.screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'message_screenshots')
        os.makedirs(self.screenshot_dir, exist_ok=True)
        self.last_scanned_messages = set()  # 避免重复上报

    def _log(self, message, level='INFO'):
        """记录日志到文件"""
        try:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_line = f'[{timestamp}] [{level}] {message}\n'
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line)
        except Exception:
            pass

    def get_chat_windows(self):
        """获取所有企业微信聊天窗口"""
        chat_windows = []
        try:
            def callback(hwnd, extra):
                if win32gui.IsWindowVisible(hwnd):
                    try:
                        window_text = win32gui.GetWindowText(hwnd)
                        class_name = win32gui.GetClassName(hwnd)
                        # 检查是否是企业微信窗口
                        if '企业微信' in window_text or 'WeChat' in class_name or 'WeWork' in class_name:
                            # 排除主窗口，只看聊天窗口（有联系人名称的）
                            if window_text not in ['企业微信', 'WeChat', 'WeWork'] and len(window_text.strip()) > 0:
                                chat_windows.append({
                                    'hwnd': hwnd,
                                    'title': window_text,
                                    'class_name': class_name
                                })
                    except:
                        pass
                return True
            win32gui.EnumWindows(callback, None)
        except Exception as e:
            self._log(f'获取聊天窗口失败: {e}', 'ERROR')
        return chat_windows

    def capture_window(self, hwnd):
        """截图指定窗口"""
        try:
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top

            # 使用传统的Bit