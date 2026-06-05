# -*- coding: utf-8 -*-
"""
企业微信 Hook 智能封装
自动检测并使用真实 ntwork 库，如果不存在则使用模拟版本
"""

import os
import sys

# 自动检测 ntwork 是否可用
try:
    import ntwork
    NTWORK_AVAILABLE = True
    print("[WeComWrapper] 检测到 ntwork 库，使用真实企业微信 API")
except ImportError:
    NTWORK_AVAILABLE = False
    print("[WeComWrapper] 未检测到 ntwork 库，使用模拟模式")


class WeComWrapper:
    """企业微信智能封装"""
    
    def __init__(self):
        self._instance = None
        self._use_mock = not NTWORK_AVAILABLE
        self._login_status = False
        self._login_info = None
        
        if self._use_mock:
            print("[WeComWrapper] 初始化模拟模式")
        else:
            print("[WeComWrapper] 初始化真实 ntwork 模式")
            self._init_ntwork()
    
    def _init_ntwork(self):
        """初始化真实的 ntwork 实例"""
        try:
            self._instance = ntwork.WeWork()
            print("[WeComWrapper] ntwork 实例创建成功")
        except Exception as e:
            print(f"[WeComWrapper] ntwork 初始化失败: {e}")
            print("[WeComWrapper] 将使用模拟模式")
            self._use_mock = True
    
    def open(self, smart: bool = True) -> bool:
        """打开企业微信"""
        if self._use_mock:
            print("[WeComWrapper][模拟] 打开企业微信")
            return True
        
        try:
            self._instance.open(smart=smart)
            print("[WeComWrapper] 企业微信已打开")
            return True
        except Exception as e:
            print(f"[WeComWrapper] 打开企业微信失败: {e}")
            return False
    
    def wait_login(self, timeout: int = 300) -> bool:
        """等待登录"""
        if self._use_mock:
            print("[WeComWrapper][模拟] 等待登录...")
            # 模拟登录状态
            import time
            time.sleep(1)
            self._login_status = True
            self._login_info = {
                "user_id": "mock_user_123",
                "name": "模拟用户",
                "corp_name": "模拟企业",
                "mobile": "13800138000"
            }
            print("[WeComWrapper][模拟] 登录成功！")
            return True
        
        try:
            print("[WeComWrapper] 等待登录...")
            self._instance.wait_login(timeout=timeout)
            self._login_status = True
            self._login_info = self._instance.get_login_info()
            print("[WeComWrapper] 登录成功！")
            return True
        except Exception as e:
            print(f"[WeComWrapper] 登录失败: {e}")
            return False
    
    @property
    def login_status(self) -> bool:
        """登录状态"""
        if self._use_mock:
            return self._login_status
        try:
            return self._instance.login_status
        except:
            return False
    
    def get_login_info(self) -> dict:
        """获取登录信息"""
        if self._use_mock:
            return self._login_info or {
                "user_id": "demo_user",
                "name": "演示用户",
                "corp_name": "演示企业"
            }
        
        try:
            return self._instance.get_login_info()
        except Exception as e:
            print(f"[WeComWrapper] 获取登录信息失败: {e}")
            return {}
    
    def get_inner_contacts(self) -> list:
        """获取内部联系人"""
        if self._use_mock:
            print("[WeComWrapper][模拟] 获取内部联系人")
            return [
                {"user_id": "user1", "name": "张三", "mobile": "13800138001"},
                {"user_id": "user2", "name": "李四", "mobile": "13800138002"},
            ]
        
        try:
            return self._instance.get_inner_contacts()
        except Exception as e:
            print(f"[WeComWrapper] 获取内部联系人失败: {e}")
            return []
    
    def get_external_contacts(self) -> list:
        """获取外部联系人"""
        if self._use_mock:
            print("[WeComWrapper][模拟] 获取外部联系人")
            return [
                {"external_userid": "ext1", "name": "客户A", "corp_name": "科技公司"},
                {"external_userid": "ext2", "name": "客户B", "corp_name": "贸易公司"},
            ]
        
        try:
            return self._instance.get_external_contacts()
        except Exception as e:
            print(f"[WeComWrapper] 获取外部联系人失败: {e}")
            return []
    
    def get_rooms(self) -> list:
        """获取群列表"""
        if self._use_mock:
            print("[WeComWrapper][模拟] 获取群列表")
            return [
                {"room_id": "room1", "name": "销售群", "member_count": 10},
                {"room_id": "room2", "name": "技术群", "member_count": 8},
            ]
        
        try:
            return self._instance.get_rooms()
        except Exception as e:
            print(f"[WeComWrapper] 获取群列表失败: {e}")
            return []
    
    def send_text(self, conversation_id: str, content: str) -> bool:
        """发送文本消息"""
        if self._use_mock:
            print(f"[WeComWrapper][模拟] 发送消息到 {conversation_id}: {content}")
            return True
        
        try:
            self._instance.send_text(conversation_id=conversation_id, content=content)
            return True
        except Exception as e:
            print(f"[WeComWrapper] 发送消息失败: {e}")
            return False
    
    def send_image(self, conversation_id: str, image_path: str) -> bool:
        """发送图片"""
        if self._use_mock:
            print(f"[WeComWrapper][模拟] 发送图片到 {conversation_id}")
            return True
        
        try:
            self._instance.send_image(conversation_id=conversation_id, image_path=image_path)
            return True
        except Exception as e:
            print(f"[WeComWrapper] 发送图片失败: {e}")
            return False
    
    def send_file(self, conversation_id: str, file_path: str) -> bool:
        """发送文件"""
        if self._use_mock:
            print(f"[WeComWrapper][模拟] 发送文件到 {conversation_id}")
            return True
        
        try:
            self._instance.send_file(conversation_id=conversation_id, file_path=file_path)
            return True
        except Exception as e:
            print(f"[WeComWrapper] 发送文件失败: {e}")
            return False
    
    def msg_register(self, msg_type: int):
        """消息注册装饰器"""
        def decorator(func):
            if not self._use_mock and self._instance:
                self._instance.msg_register(msg_type)(func)
            return func
        return decorator
    
    def on(self, msg_type: int, callback):
        """注册消息回调"""
        if not self._use_mock and self._instance:
            self._instance.on(msg_type, callback)
    
    def close(self):
        """关闭"""
        if not self._use_mock and self._instance:
            try:
                ntwork.exit_()
                print("[WeComWrapper] ntwork 已退出")
            except:
                pass
        print("[WeComWrapper] 已关闭")


# 全局实例
_wrapper_instance = None

def get_wework_wrapper() -> WeComWrapper:
    """获取全局企业微信封装实例"""
    global _wrapper_instance
    if _wrapper_instance is None:
        _wrapper_instance = WeComWrapper()
    return _wrapper_instance


# 测试函数
def test_wrapper():
    """测试智能封装"""
    print("="*60)
    print("企业微信智能封装测试")
    print(f"模式: {'真实模式' if NTWORK_AVAILABLE else '模拟模式'}")
    print("="*60)
    
    wrapper = WeComWrapper()
    
    # 1. 初始化
    print("\n[1/4] 初始化")
    print(f"✓ 初始化完成，使用{'真实' if not wrapper._use_mock else '模拟'}模式")
    
    # 2. 打开企业微信
    print("\n[2/4] 打开企业微信")
    if wrapper.open(smart=True):
        print("✓ 企业微信已打开")
    else:
        print("✗ 打开失败")
        return
    
    # 3. 等待登录
    print("\n[3/4] 等待登录")
    if wrapper.wait_login(timeout=5):
        print("✓ 登录成功")
        login_info = wrapper.get_login_info()
        print(f"  用户: {login_info.get('name')}")
        print(f"  企业: {login_info.get('corp_name')}")
    else:
        print("✗ 登录失败")
        if not wrapper._use_mock:
            print("  (模拟模式下自动登录成功)")
    
    # 4. 获取数据
    print("\n[4/4] 获取联系人数据")
    inner_contacts = wrapper.get_inner_contacts()
    print(f"✓ 内部联系人: {len(inner_contacts)}")
    
    external_contacts = wrapper.get_external_contacts()
    print(f"✓ 外部联系人: {len(external_contacts)}")
    
    rooms = wrapper.get_rooms()
    print(f"✓ 群: {len(rooms)}")
    
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)
    
    # 发送测试消息（仅在真实模式下）
    if not wrapper._use_mock:
        print("\n💡 提示：安装企业微信 4.0.8.6027 版本可以使用完整功能")
    else:
        print("\n💡 提示：安装 ntwork 库和企业微信 4.0.8.6027 版本可以使用真实功能")
        print("   安装命令：pip install ntwork")
    
    wrapper.close()


if __name__ == "__main__":
    test_wrapper()

