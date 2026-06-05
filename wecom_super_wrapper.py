# -*- coding: utf-8 -*-
"""
企业微信超级智能封装
支持多种库的自动检测和切换：
1. wxwork_pc_api - 功能最强大
2. ntwork - 成熟稳定
3. 模拟模式 - 无需依赖
"""

import os
import sys
import time
import json
from typing import Optional, Dict, List, Callable, Any

# 自动检测可用库
LIBS_AVAILABLE = {
    'wxwork_pc_api': False,
    'ntwork': False
}

# 1. 检测 wxwork_pc_api
try:
    # 这个库通常需要导入 wxwork 模块
    import wxwork
    LIBS_AVAILABLE['wxwork_pc_api'] = True
    print("[SuperWrapper] 检测到 wxwork_pc_api 库")
except ImportError:
    pass

# 2. 检测 ntwork
try:
    import ntwork
    LIBS_AVAILABLE['ntwork'] = True
    print("[SuperWrapper] 检测到 ntwork 库")
except ImportError:
    pass


class WeComSuperWrapper:
    """企业微信超级智能封装 - 支持多种库"""
    
    # 库优先级
    PREFERRED_LIBS = ['wxwork_pc_api', 'ntwork', 'mock']
    
    # 消息类型常量（统一接口）
    MT_RECV_TEXT_MSG = 1
    MT_RECV_IMAGE_MSG = 2
    MT_RECV_VOICE_MSG = 3
    MT_RECV_VIDEO_MSG = 4
    MT_RECV_FILE_MSG = 5
    MT_RECV_CARD_MSG = 6
    MT_RECV_LINK_MSG = 7
    MT_ALL = 99999
    
    def __init__(self, preferred_lib: Optional[str] = None):
        """
        初始化超级封装
        :param preferred_lib: 优先使用的库，如果不指定则自动选择
        """
        self._instance = None
        self._use_lib = None
        self._login_status = False
        self._login_info = None
        self._callbacks = {}
        
        # 选择合适的库
        self._select_lib(preferred_lib)
        
        print(f"[SuperWrapper] 初始化完成，使用库: {self._use_lib}")
    
    def _select_lib(self, preferred_lib: Optional[str]):
        """选择合适的库"""
        libs = self.PREFERRED_LIBS
        
        # 如果指定了优先库，调整顺序
        if preferred_lib and preferred_lib in libs:
            libs.remove(preferred_lib)
            libs.insert(0, preferred_lib)
        
        # 按优先级选择可用的库
        for lib in libs:
            if lib == 'wxwork_pc_api' and LIBS_AVAILABLE['wxwork_pc_api']:
                try:
                    self._init_wxwork_pc_api()
                    self._use_lib = 'wxwork_pc_api'
                    return
                except Exception as e:
                    print(f"[SuperWrapper] wxwork_pc_api 初始化失败: {e}")
                    continue
            elif lib == 'ntwork' and LIBS_AVAILABLE['ntwork']:
                try:
                    self._init_ntwork()
                    self._use_lib = 'ntwork'
                    return
                except Exception as e:
                    print(f"[SuperWrapper] ntwork 初始化失败: {e}")
                    continue
            elif lib == 'mock':
                self._use_lib = 'mock'
                print("[SuperWrapper] 使用模拟模式")
                return
        
        # 默认使用模拟模式
        self._use_lib = 'mock'
        print("[SuperWrapper] 使用模拟模式（没有检测到可用的库）")
    
    def _init_wxwork_pc_api(self):
        """初始化 wxwork_pc_api"""
        print("[SuperWrapper] 初始化 wxwork_pc_api")
        # 这里可以根据实际的 wxwork_pc_api API 进行封装
        # 由于我们没有实际的 DLL，暂时跳过具体实现
    
    def _init_ntwork(self):
        """初始化 ntwork"""
        print("[SuperWrapper] 初始化 ntwork")
        import ntwork
        self._instance = ntwork.WeWork()
    
    def open(self, smart: bool = True) -> bool:
        """打开企业微信"""
        if self._use_lib == 'mock':
            print("[SuperWrapper][Mock] 打开企业微信")
            return True
        
        if self._use_lib == 'ntwork':
            try:
                self._instance.open(smart=smart)
                print("[SuperWrapper][ntwork] 企业微信已打开")
                return True
            except Exception as e:
                print(f"[SuperWrapper][ntwork] 打开失败: {e}")
                return False
        
        # TODO: 实现 wxwork_pc_api
        return False
    
    def wait_login(self, timeout: int = 300) -> bool:
        """等待登录"""
        if self._use_lib == 'mock':
            print("[SuperWrapper][Mock] 等待登录...")
            time.sleep(1)
            self._login_status = True
            self._login_info = {
                'user_id': 'mock_user_123',
                'name': '模拟用户',
                'corp_name': '模拟企业',
                'mobile': '13800138000'
            }
            print("[SuperWrapper][Mock] 登录成功！")
            return True
        
        if self._use_lib == 'ntwork':
            try:
                print("[SuperWrapper][ntwork] 等待登录...")
                self._instance.wait_login(timeout=timeout)
                self._login_status = True
                self._login_info = self._instance.get_login_info()
                print("[SuperWrapper][ntwork] 登录成功！")
                return True
            except Exception as e:
                print(f"[SuperWrapper][ntwork] 登录失败: {e}")
                return False
        
        return False
    
    @property
    def login_status(self) -> bool:
        """登录状态"""
        if self._use_lib == 'mock':
            return self._login_status
        if self._use_lib == 'ntwork':
            try:
                return self._instance.login_status
            except:
                return False
        return False
    
    def get_login_info(self) -> dict:
        """获取登录信息"""
        if self._use_lib == 'mock':
            return self._login_info or {
                'user_id': 'demo_user',
                'name': '演示用户',
                'corp_name': '演示企业'
            }
        
        if self._use_lib == 'ntwork':
            try:
                return self._instance.get_login_info()
            except Exception as e:
                print(f"[SuperWrapper][ntwork] 获取登录信息失败: {e}")
                return {}
        
        return {}
    
    def get_inner_contacts(self) -> List[Dict]:
        """获取内部联系人"""
        if self._use_lib == 'mock':
            print("[SuperWrapper][Mock] 获取内部联系人")
            return [
                {'user_id': 'user1', 'name': '张三', 'mobile': '13800138001'},
                {'user_id': 'user2', 'name': '李四', 'mobile': '13800138002'},
            ]
        
        if self._use_lib == 'ntwork':
            try:
                return self._instance.get_inner_contacts()
            except Exception as e:
                print(f"[SuperWrapper][ntwork] 获取内部联系人失败: {e}")
                return []
        
        return []
    
    def get_external_contacts(self) -> List[Dict]:
        """获取外部联系人"""
        if self._use_lib == 'mock':
            print("[SuperWrapper][Mock] 获取外部联系人")
            return [
                {'external_userid': 'ext1', 'name': '客户A', 'corp_name': '科技公司'},
                {'external_userid': 'ext2', 'name': '客户B', 'corp_name': '贸易公司'},
            ]
        
        if self._use_lib == 'ntwork':
            try:
                return self._instance.get_external_contacts()
            except Exception as e:
                print(f"[SuperWrapper][ntwork] 获取外部联系人失败: {e}")
                return []
        
        return []
    
    def get_rooms(self) -> List[Dict]:
        """获取群列表"""
        if self._use_lib == 'mock':
            print("[SuperWrapper][Mock] 获取群列表")
            return [
                {'room_id': 'room1', 'name': '销售群', 'member_count': 10},
                {'room_id': 'room2', 'name': '技术群', 'member_count': 8},
            ]
        
        if self._use_lib == 'ntwork':
            try:
                return self._instance.get_rooms()
            except Exception as e:
                print(f"[SuperWrapper][ntwork] 获取群列表失败: {e}")
                return []
        
        return []
    
    def send_text(self, conversation_id: str, content: str) -> bool:
        """发送文本消息"""
        if self._use_lib == 'mock':
            print(f"[SuperWrapper][Mock] 发送消息到 {conversation_id}: {content}")
            return True
        
        if self._use_lib == 'ntwork':
            try:
                self._instance.send_text(conversation_id=conversation_id, content=content)
                return True
            except Exception as e:
                print(f"[SuperWrapper][ntwork] 发送消息失败: {e}")
                return False
        
        return False
    
    def send_image(self, conversation_id: str, image_path: str) -> bool:
        """发送图片"""
        if self._use_lib == 'mock':
            print(f"[SuperWrapper][Mock] 发送图片到 {conversation_id}")
            return True
        
        if self._use_lib == 'ntwork':
            try:
                self._instance.send_image(conversation_id=conversation_id, image_path=image_path)
                return True
            except Exception as e:
                print(f"[SuperWrapper][ntwork] 发送图片失败: {e}")
                return False
        
        return False
    
    def send_file(self, conversation_id: str, file_path: str) -> bool:
        """发送文件"""
        if self._use_lib == 'mock':
            print(f"[SuperWrapper][Mock] 发送文件到 {conversation_id}")
            return True
        
        if self._use_lib == 'ntwork':
            try:
                self._instance.send_file(conversation_id=conversation_id, file_path=file_path)
                return True
            except Exception as e:
                print(f"[SuperWrapper][ntwork] 发送文件失败: {e}")
                return False
        
        return False
    
    def msg_register(self, msg_type: int):
        """消息注册装饰器"""
        def decorator(func: Callable):
            if msg_type not in self._callbacks:
                self._callbacks[msg_type] = []
            self._callbacks[msg_type].append(func)
            
            # 同时注册到底层库
            if self._use_lib == 'ntwork' and self._instance:
                try:
                    self._instance.msg_register(msg_type)(func)
                except:
                    pass
            
            return func
        return decorator
    
    def on(self, msg_type: int, callback: Callable):
        """注册消息回调"""
        if msg_type not in self._callbacks:
            self._callbacks[msg_type] = []
        self._callbacks[msg_type].append(callback)
        
        # 同时注册到底层库
        if self._use_lib == 'ntwork' and self._instance:
            try:
                self._instance.on(msg_type, callback)
            except:
                pass
    
    def close(self):
        """关闭"""
        if self._use_lib == 'ntwork' and self._instance:
            try:
                import ntwork
                ntwork.exit_()
                print("[SuperWrapper][ntwork] 已关闭")
            except:
                pass
        print("[SuperWrapper] 已关闭")
    
    def get_available_libs(self) -> dict:
        """获取可用的库信息"""
        return {
            'available': LIBS_AVAILABLE,
            'current': self._use_lib,
            'preferred': self.PREFERRED_LIBS
        }


# 全局实例
_super_wrapper_instance = None


def get_super_wrapper(preferred_lib: Optional[str] = None) -> WeComSuperWrapper:
    """获取全局超级封装实例"""
    global _super_wrapper_instance
    if _super_wrapper_instance is None:
        _super_wrapper_instance = WeComSuperWrapper(preferred_lib)
    return _super_wrapper_instance


# 测试函数
def test_super_wrapper():
    """测试超级封装"""
    print("="*80)
    print("企业微信超级智能封装测试")
    print("="*80)
    
    # 创建超级封装
    wrapper = WeComSuperWrapper()
    
    # 显示可用库信息
    lib_info = wrapper.get_available_libs()
    print(f"\n可用库信息: {lib_info}")
    
    # 1. 初始化
    print("\n[1/4] 初始化")
    print(f"✓ 初始化完成，使用库: {wrapper._use_lib}")
    
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
        if wrapper._use_lib == 'mock':
            print("  (模拟模式下自动登录成功)")
    
    # 4. 获取数据
    print("\n[4/4] 获取联系人数据")
    inner_contacts = wrapper.get_inner_contacts()
    print(f"✓ 内部联系人: {len(inner_contacts)}")
    
    external_contacts = wrapper.get_external_contacts()
    print(f"✓ 外部联系人: {len(external_contacts)}")
    
    rooms = wrapper.get_rooms()
    print(f"✓ 群: {len(rooms)}")
    
    print("\n" + "="*80)
    print("测试完成！")
    print("="*80)
    
    # 提示信息
    print("\n💡 可用的库安装提示:")
    if not LIBS_AVAILABLE['ntwork']:
        print("  - ntwork: pip install ntwork")
    if not LIBS_AVAILABLE['wxwork_pc_api']:
        print("  - wxwork_pc_api: 需下载 DLL 文件并放置在 libs 目录")
    
    wrapper.close()


if __name__ == "__main__":
    test_super_wrapper()

