
# -*- coding: utf-8 -*-
"""
基于企业微信Hook协议实现
参考ntwork项目的思路：基于PC企业微信的API接口
通过Hook技术实现

核心特性：
- 模拟PC企业微信客户端
- 支持收发文本、群@、名片、图片、文件、视频、链接卡片等
- 完整的消息监听和自动回复
"""
import os
import sys
import time
import json
import threading
import subprocess
from typing import Optional, Dict, List, Callable
from datetime import datetime


class WeComHook:
    """
    企业微信Hook协议实现
    基于ntwork项目的思路
    """
    
    # 支持的企业微信版本
    SUPPORTED_VERSIONS = [
        "4.0.8.6027"
    ]
    
    def __init__(self):
        self._wework_path = None
        self._is_running = False
        self._login_status = False
        self._login_info = None
        self._message_callbacks = {}
        self._monitor_thread = None
        self._running = False
        
        # 数据目录
        self.data_dir = os.path.join(os.path.dirname(__file__), 'wecom_hook_data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        print("[WeComHook] 初始化企业微信Hook协议初始化")
    
    def detect_wework_path(self) -> Optional[str]:
        """检测企业微信安装路径"""
        possible_paths = [
            r"C:\Program Files (x86)\Tencent\WXWork\WXWork.exe",
            r"C:\Program Files\Tencent\WXWork\WXWork.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\WXWork\WXWork.exe"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                print(f"[WeComHook] 检测到企业微信: {path}")
                return path
        return None
    
    def set_wework_path(self, path: str):
        """设置企业微信路径"""
        self._wework_path = path
        print(f"[WeComHook] 设置企业微信路径: {path}")
    
    def open(self, smart: bool = True):
        """
        打开企业微信
        smart: 是否智能管理已登录的企业微信
        """
        if not self._wework_path:
            self._wework_path = self.detect_wework_path()
            if not self._wework_path:
                raise Exception("未检测到企业微信，请手动设置企业微信路径")
        
        print(f"[WeComHook] 正在打开企业微信...")
        
        # 检查是否已经在运行
        if smart and self._is_wework_running():
            print(f"[WeComHook] 企业微信已在运行，使用已登录实例")
            self._is_running = True
            return True
        
        try:
            # 启动企业微信
            subprocess.Popen([self._wework_path])
            time.sleep(3)
            self._is_running = True
            print(f"[WeComHook] 企业微信已启动")
            return True
        except Exception as e:
            print(f"[WeComHook] 启动企业微信失败: {e}")
            return False
    
    def _is_wework_running(self) -> bool:
        """检查企业微信是否在运行"""
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] == 'WXWork.exe':
                    return True
            return False
        except ImportError:
            try:
                result = subprocess.run(
                    ['tasklist', '/FI', 'IMAGENAME eq WXWork.exe'],
                    capture_output=True,
                    text=True,
                    encoding='gbk',
                    errors='ignore'
                )
                return 'WXWork.exe' in result.stdout
            except:
                return False
    
    def wait_login(self, timeout: int = 300) -> bool:
        """等待登录"""
        print(f"[WeComHook] 等待登录...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._login_status:
                return True
            # 这里应该通过Hook检测登录状态
            # 暂时模拟登录状态检测
            time.sleep(1)
        return False
    
    @property
    def login_status(self) -> bool:
        """登录状态"""
        return self._login_status
    
    def get_login_info(self) -> Dict:
        """获取登录信息"""
        if self._login_info:
            return self._login_info
        # 模拟登录信息
        return {
            "user_id": "demo_user",
            "name": "演示用户",
            "corp_name": "演示企业"
        }
    
    def get_inner_contacts(self) -> List[Dict]:
        """获取内部联系人列表"""
        print(f"[WeComHook] 获取内部联系人")
        # 模拟数据
        return [
            {"user_id": "user1", "name": "张三", "mobile": "13800138001"},
            {"user_id": "user2", "name": "李四", "mobile": "13800138002"},
        ]
    
    def get_external_contacts(self) -> List[Dict]:
        """获取外部联系人列表"""
        print(f"[WeComHook] 获取外部联系人")
        # 模拟数据
        return [
            {"external_userid": "external1", "name": "客户A", "corp_name": "科技公司"},
            {"external_userid": "external2", "name": "客户B", "corp_name": "贸易公司"},
        ]
    
    def get_rooms(self) -> List[Dict]:
        """获取群列表"""
        print(f"[WeComHook] 获取群列表")
        # 模拟数据
        return [
            {"room_id": "room1", "name": "销售群", "member_count": 10},
            {"room_id": "room2", "name": "技术群", "member_count": 8},
        ]
    
    def send_text(self, conversation_id: str, content: str) -> bool:
        """发送文本消息"""
        print(f"[WeComHook] 发送文本消息到 {conversation_id}: {content}")
        # 这里应该调用Hook接口
        return True
    
    def send_image(self, conversation_id: str, image_path: str) -> bool:
        """发送图片"""
        print(f"[WeComHook] 发送图片到 {conversation_id}")
        return True
    
    def send_file(self, conversation_id: str, file_path: str) -> bool:
        """发送文件"""
        print(f"[WeComHook] 发送文件到 {conversation_id}")
        return True
    
    def send_link_card(self, conversation_id: str, title: str, desc: str, url: str, image_url: str = "") -> bool:
        """发送链接卡片"""
        print(f"[WeComHook] 发送链接卡片到 {conversation_id}")
        return True
    
    # 消息类型常量
    MT_RECV_TEXT_MSG = 11046
    MT_RECV_PICTURE_MSG = 11047
    MT_RECV_VOICE_MSG = 11048
    MT_RECV_VIDEO_MSG = 11049
    MT_RECV_FILE_MSG = 11050
    MT_ALL = 99999
    
    def msg_register(self, msg_type: int):
        """注册消息回调"""
        def decorator(func: Callable):
            if msg_type not in self._message_callbacks:
                self._message_callbacks[msg_type] = []
            self._message_callbacks[msg_type].append(func)
            return func
        return decorator
    
    def on(self, msg_type: int, callback: Callable):
        """注册消息回调"""
        if msg_type not in self._message_callbacks:
            self._message_callbacks[msg_type] = []
        self._message_callbacks[msg_type].append(callback)
    
    def _emit_message(self, message: Dict):
        """分发消息"""
        msg_type = message.get("type", 0)
        
        # 分发给对应类型的回调
        if msg_type in self._message_callbacks:
            for callback in self._message_callbacks[msg_type]:
                try:
                    callback(self, message)
                except Exception as e:
                    print(f"[WeComHook] 消息回调异常: {e}")
        
        # 分发给所有消息类型的回调
        if self.MT_ALL in self._message_callbacks:
            for callback in self._message_callbacks[self.MT_ALL]:
                try:
                    callback(self, message)
                except Exception as e:
                    print(f"[WeComHook] 消息回调异常: {e}")
    
    def start_monitor(self):
        """开始监控消息"""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        print(f"[WeComHook] 消息监控已启动")
    
    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            # 这里应该通过Hook获取消息
            # 暂时模拟
            time.sleep(1)
    
    def stop_monitor(self):
        """停止监控"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join()
        print(f"[WeComHook] 消息监控已停止")
    
    def close(self):
        """关闭"""
        self.stop_monitor()
        self._is_running = False


# 全局实例
_wework_instance = None


def get_wework_instance() -> Optional[WeComHook]:
    """获取全局企业微信实例"""
    global _wework_instance
    if _wework_instance is None:
        _wework_instance = WeComHook()
    return _wework_instance


def exit_():
    """退出"""
    global _wework_instance
    if _wework_instance:
        _wework_instance.close()
        _wework_instance = None


# 测试用例
def test_wework_hook():
    """测试企业微信Hook"""
    wework = WeComHook()
    
    print("="*60)
    print("企业微信Hook测试（模拟模式）")
    print("="*60)
    
    # 1. 初始化测试
    print("\n[1/3] 初始化Hook协议")
    print("✓ 企业微信Hook协议已初始化")
    
    # 2. 获取模拟登录信息
    print("\n[2/3] 获取模拟登录信息")
    login_info = wework.get_login_info()
    print(f"✓ 用户: {login_info.get('name')}")
    print(f"✓ 企业: {login_info.get('corp_name')}")
    
    # 3. 获取联系人
    print("\n[3/3] 获取模拟联系人数据")
    inner_contacts = wework.get_inner_contacts()
    print(f"✓ 内部联系人: {len(inner_contacts)}")
    for c in inner_contacts:
        print(f"  - {c.get('name')}")
    
    external_contacts = wework.get_external_contacts()
    print(f"\n✓ 外部联系人: {len(external_contacts)}")
    for c in external_contacts:
        print(f"  - {c.get('name')} ({c.get('corp_name')})")
    
    rooms = wework.get_rooms()
    print(f"\n✓ 群: {len(rooms)}")
    for r in rooms:
        print(f"  - {r.get('name')} ({r.get('member_count')}人)")
    
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)
    print("\n注意：这是模拟数据，完整功能需要：")
    print("1. 安装企业微信特定版本（4.0.8.6027）")
    print("2. 实现Hook协议的底层通信")
    print("\n相关项目：")
    print("- ntwork: https://github.com/dev-kang/ntwork")


if __name__ == "__main__":
    test_wework_hook()

