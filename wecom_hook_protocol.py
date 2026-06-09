# -*- coding: utf-8 -*-
"""
基于 Hook 技术的企业微信账号托管
================================
核心思路：通过 Hook PC 企业微信客户端实现登录与消息收发
参考项目：ntwork

工作流程：
1. 检测并启动 PC 版企业微信客户端
2. 等待用户在客户端扫码登录
3. 通过 Hook 监听登录状态
4. 登录成功后，通过 Hook API 获取登录信息、联系人、收发消息

**绝对不再使用管理后台 (work.weixin.qq.com/wework_admin) 的二维码**
"""

import os
import sys
import time
import json
import threading
import subprocess
from typing import Optional, Dict, List, Callable, Any
from datetime import datetime


# ============================================================
# 1. Hook 库自动检测
# ============================================================

HOOK_LIBS = {
    'ntwork': False,
    'wxwork': False,
}

try:
    import ntwork
    HOOK_LIBS['ntwork'] = True
    print("[Hook] 检测到 ntwork 库")
except ImportError:
    pass

try:
    import wxwork
    HOOK_LIBS['wxwork'] = True
    print("[Hook] 检测到 wxwork 库")
except ImportError:
    pass


# ============================================================
# 2. 企业微信路径检测
# ============================================================

def detect_wework_path() -> Optional[str]:
    """自动检测企业微信安装路径"""
    candidate_paths = [
        r"C:\Program Files (x86)\Tencent\WXWork\WXWork.exe",
        r"C:\Program Files\Tencent\WXWork\WXWork.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\WXWork\WXWork.exe"),
        os.path.expanduser(r"~\AppData\Local\Programs\WXWork\WXWork.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Tencent\WXWork\WXWork.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Tencent\WXWork\WXWork.exe"),
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            print(f"[Hook] 检测到企业微信客户端: {p}")
            return p
    return None


def is_wework_running() -> bool:
    """检查企业微信进程是否在运行"""
    try:
        import psutil
        for proc in psutil.process_iter(['name']):
            if proc.info.get('name') == 'WXWork.exe':
                return True
        return False
    except ImportError:
        try:
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq WXWork.exe'],
                capture_output=True, text=True, encoding='gbk', errors='ignore'
            )
            return 'WXWork.exe' in result.stdout
        except Exception:
            return False


# ============================================================
# 3. 核心 Hook 客户端类
# ============================================================

class WeComHookClient:
    """
    企业微信 Hook 客户端
    通过 Hook 本地 PC 企业微信客户端实现账号托管
    """

    def __init__(self, preferred_lib: Optional[str] = None):
        self._lib_name = None          # 当前使用的 Hook 库名
        self._lib_instance = None      # 底层 Hook 库实例
        self._wework_path = None       # 企业微信可执行文件路径
        self._login_status = False     # 是否已登录
        self._login_info = None        # 登录信息
        self._message_callbacks = {}   # 消息回调
        self._lock = threading.Lock()

        # 自动选择库
        self._select_lib(preferred_lib)

    # ---------- 库选择 ----------

    def _select_lib(self, preferred: Optional[str]):
        """选择可用的 Hook 库"""
        if preferred and preferred in HOOK_LIBS and HOOK_LIBS[preferred]:
            if self._try_init_lib(preferred):
                return

        for lib_name, available in HOOK_LIBS.items():
            if available and self._try_init_lib(lib_name):
                return

        # 没有可用的 Hook 库，使用模拟模式
        self._lib_name = 'mock'
        print("[Hook] ⚠️  未检测到可用的 Hook 库，使用模拟模式 (mock)")
        print("[Hook] 如需真实功能，请安装: pip install ntwork")

    def _try_init_lib(self, lib_name: str) -> bool:
        """尝试初始化某个 Hook 库"""
        try:
            if lib_name == 'ntwork':
                import ntwork
                self._lib_instance = ntwork.WeWork()
                self._lib_name = 'ntwork'
                print(f"[Hook] 使用 ntwork 库")
                return True
            elif lib_name == 'wxwork':
                import wxwork
                self._lib_instance = wxwork.WeWork()
                self._lib_name = 'wxwork'
                print(f"[Hook] 使用 wxwork 库")
                return True
        except Exception as e:
            print(f"[Hook] {lib_name} 初始化失败: {e}")
        return False

    @property
    def use_lib(self) -> str:
        return self._lib_name

    @property
    def available_libs(self) -> Dict[str, bool]:
        return dict(HOOK_LIBS)

    # ---------- 客户端控制 ----------

    def set_wework_path(self, path: str):
        if path and os.path.exists(path):
            self._wework_path = path

    def open(self, smart: bool = True) -> bool:
        """
        打开企业微信客户端
        smart=True 时，如果已运行则直接复用
        """
        if smart and is_wework_running():
            print("[Hook] 企业微信已运行，复用现有进程")
            # 如果底层库支持 open，调用一下
            if self._lib_name != 'mock' and self._lib_instance:
                try:
                    self._lib_instance.open(smart=True)
                except Exception:
                    pass
            return True

        # 启动企业微信
        if not self._wework_path:
            self._wework_path = detect_wework_path()

        if not self._wework_path:
            print("[Hook] ❌ 未检测到企业微信安装路径")
            return False

        try:
            print(f"[Hook] 正在启动企业微信客户端: {self._wework_path}")
            subprocess.Popen([self._wework_path])
            time.sleep(3)

            # 如果底层库支持 open，调用
            if self._lib_name != 'mock' and self._lib_instance:
                try:
                    self._lib_instance.open(smart=smart)
                except Exception as e:
                    print(f"[Hook] 底层库 open 警告: {e}")

            return True
        except Exception as e:
            print(f"[Hook] 启动企业微信失败: {e}")
            return False

    # ---------- 登录检测 ----------

    def wait_login(self, timeout: int = 300) -> bool:
        """
        等待用户在企业微信客户端完成扫码登录
        timeout: 最大等待秒数
        """
        print(f"[Hook] 等待登录 (timeout={timeout}s)...")
        start = time.time()

        while time.time() - start < timeout:
            try:
                if self._check_login():
                    self._login_status = True
                    print("[Hook] ✅ 检测到登录成功！")
                    return True
            except Exception as e:
                print(f"[Hook] 登录检测循环警告: {e}")

            time.sleep(2)

        print("[Hook] ⏱ 登录超时")
        return False

    def _check_login(self) -> bool:
        """
        检查当前是否已登录
        优先使用底层 Hook 库的真实检测
        """
        # 1. 使用底层库的真实检测
        if self._lib_name == 'ntwork' and self._lib_instance:
            try:
                return bool(self._lib_instance.login_status)
            except Exception:
                pass

        if self._lib_name == 'wxwork' and self._lib_instance:
            try:
                return bool(self._lib_instance.login_status)
            except Exception:
                pass

        # 2. 模拟模式：检查进程是否存在（简化逻辑）
        if self._lib_name == 'mock':
            # 模拟模式下，启动后 10 秒自动视为登录成功
            if is_wework_running() and not self._login_status:
                print("[Hook][Mock] 模拟模式：检测到客户端运行，视为登录准备就绪")
            return self._login_status

        return False

    @property
    def login_status(self) -> bool:
        return self._login_status or self._check_login()

    def get_login_info(self) -> Dict[str, Any]:
        """获取登录账号信息"""
        if self._login_info:
            return self._login_info

        # 尝试从底层库获取
        if self._lib_name != 'mock' and self._lib_instance:
            try:
                info = self._lib_instance.get_login_info()
                if info:
                    self._login_info = dict(info)
                    return self._login_info
            except Exception as e:
                print(f"[Hook] 获取登录信息失败: {e}")

        # 模拟模式返回示例
        self._login_info = {
            'user_id': 'hook_user',
            'name': '托管账号',
            'corp_name': '托管企业',
            'mobile': '',
        }
        return self._login_info

    # ---------- 数据获取 ----------

    def get_inner_contacts(self) -> List[Dict]:
        """获取内部联系人"""
        if self._lib_name != 'mock' and self._lib_instance:
            try:
                result = self._lib_instance.get_inner_contacts()
                return list(result) if result else []
            except Exception as e:
                print(f"[Hook] 获取内部联系人失败: {e}")
        return []

    def get_external_contacts(self) -> List[Dict]:
        """获取外部联系人"""
        if self._lib_name != 'mock' and self._lib_instance:
            try:
                result = self._lib_instance.get_external_contacts()
                return list(result) if result else []
            except Exception as e:
                print(f"[Hook] 获取外部联系人失败: {e}")
        return []

    def get_rooms(self) -> List[Dict]:
        """获取群列表"""
        if self._lib_name != 'mock' and self._lib_instance:
            try:
                result = self._lib_instance.get_rooms()
                return list(result) if result else []
            except Exception as e:
                print(f"[Hook] 获取群列表失败: {e}")
        return []

    # ---------- 消息发送 ----------

    def send_text(self, conversation_id: str, content: str) -> bool:
        """发送文本消息"""
        if not self._login_status:
            print("[Hook] ❌ 未登录，无法发送消息")
            return False

        if self._lib_name != 'mock' and self._lib_instance:
            try:
                self._lib_instance.send_text(
                    conversation_id=conversation_id,
                    content=content
                )
                return True
            except Exception as e:
                print(f"[Hook] 发送消息失败: {e}")
                return False
        return False

    def send_image(self, conversation_id: str, image_path: str) -> bool:
        """发送图片"""
        if not self._login_status or not os.path.exists(image_path):
            return False
        if self._lib_name != 'mock' and self._lib_instance:
            try:
                self._lib_instance.send_image(
                    conversation_id=conversation_id,
                    image_path=image_path
                )
                return True
            except Exception as e:
                print(f"[Hook] 发送图片失败: {e}")
        return False

    def send_file(self, conversation_id: str, file_path: str) -> bool:
        """发送文件"""
        if not self._login_status or not os.path.exists(file_path):
            return False
        if self._lib_name != 'mock' and self._lib_instance:
            try:
                self._lib_instance.send_file(
                    conversation_id=conversation_id,
                    file_path=file_path
                )
                return True
            except Exception as e:
                print(f"[Hook] 发送文件失败: {e}")
        return False

    # ---------- 消息监听 ----------

    def register_message_callback(self, callback: Callable[[Any], None]):
        """注册消息回调（用于监听收到的消息）"""
        if self._lib_name != 'mock' and self._lib_instance:
            try:
                # ntwork 使用 msg_register 装饰器模式
                if hasattr(self._lib_instance, 'msg_register'):
                    try:
                        import ntwork
                        @self._lib_instance.msg_register(ntwork.MT_ALL)
                        def _on_message(client, message):
                            try:
                                callback(message)
                            except Exception as e:
                                print(f"[Hook] 消息回调异常: {e}")
                    except Exception as e:
                        print(f"[Hook] 注册 ntwork 回调失败: {e}")
                elif hasattr(self._lib_instance, 'on'):
                    self._lib_instance.on('message', callback)
            except Exception as e:
                print(f"[Hook] 注册消息回调失败: {e}")

    # ---------- 清理 ----------

    def close(self):
        """关闭 Hook 客户端（不关闭企业微信本身）"""
        if self._lib_name == 'ntwork':
            try:
                import ntwork
                ntwork.exit_()
            except Exception:
                pass
        self._login_status = False
        self._login_info = None


# ============================================================
# 4. 全局单例服务
# ============================================================

_global_hook_instance: Optional[WeComHookClient] = None
_global_hook_lock = threading.Lock()


def get_hook_client(preferred_lib: Optional[str] = None) -> WeComHookClient:
    """获取全局 Hook 客户端实例"""
    global _global_hook_instance
    with _global_hook_lock:
        if _global_hook_instance is None:
            _global_hook_instance = WeComHookClient(preferred_lib=preferred_lib)
        return _global_hook_instance


def reset_hook_client():
    """重置 Hook 客户端（用于切换账号）"""
    global _global_hook_instance
    with _global_hook_lock:
        if _global_hook_instance:
            try:
                _global_hook_instance.close()
            except Exception:
                pass
        _global_hook_instance = None


# ============================================================
# 5. 交互式测试入口
# ============================================================

def _run_interactive_test():
    """交互式测试 - 用于本地验证"""
    print("=" * 70)
    print("企业微信 Hook 托管 - 交互式测试")
    print("=" * 70)

    client = WeComHookClient()
    print(f"使用库: {client.use_lib}")
    print(f"可用库: {client.available_libs}")
    print()

    # 打开企业微信
    print(">>> 步骤 1: 启动企业微信客户端")
    if not client.open(smart=True):
        print("启动失败，请确认企业微信已安装")
        return
    print()

    # 等待登录
    print(">>> 步骤 2: 请在打开的企业微信客户端中扫码登录")
    print("(等待中，最多 120 秒...)")
    success = client.wait_login(timeout=120)
    if not success:
        print("⏱ 登录超时")
        return
    print()

    # 获取信息
    print(">>> 步骤 3: 获取登录信息")
    info = client.get_login_info()
    print(f"登录账号: {info.get('name', '未知')}")
    print(f"所属企业: {info.get('corp_name', '未知')}")
    print()

    print(">>> 步骤 4: 获取数据")
    inner = client.get_inner_contacts()
    print(f"内部联系人: {len(inner)} 人")
    external = client.get_external_contacts()
    print(f"外部联系人: {len(external)} 人")
    rooms = client.get_rooms()
    print(f"群聊: {len(rooms)} 个")
    print()
    print("测试完成！")
    client.close()


if __name__ == "__main__":
    _run_interactive_test()
