# -*- coding: utf-8 -*-
"""设置管理"""
import json
import os
from pathlib import Path


class Settings:
    """设置管理类"""
    
    DEFAULT_SETTINGS = {
        'server_url': 'http://192.168.100.22:5000',
        'user_id': '',
        'username': '',
        'password': '',
        'token': '',
        'auto_start': False,
        'start_minimized': True,
        'volume': 80,
        'sound_enabled': True,
        'normal_duration': 5,
        'important_duration': 10,
        'urgent_duration': 0
    }
    
    def __init__(self):
        self.config_dir = Path.home() / '.notification_client'
        self.config_file = self.config_dir / 'settings.json'
        self.settings = self.load()
    
    def load(self):
        """加载设置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    settings = self.DEFAULT_SETTINGS.copy()
                    settings.update(loaded)
                    return settings
            except:
                return self.DEFAULT_SETTINGS.copy()
        return self.DEFAULT_SETTINGS.copy()
    
    def save(self):
        """保存设置"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=2)
    
    def get(self, key, default=None):
        """获取设置"""
        return self.settings.get(key, default)
    
    def set(self, key, value):
        """设置值"""
        self.settings[key] = value
        self.save()
    
    def is_configured(self):
        """检查是否已配置"""
        return bool(
            self.settings.get('username') 
            and self.settings.get('password')
            and self.settings.get('user_id')
            and self.settings.get('token')
        )
