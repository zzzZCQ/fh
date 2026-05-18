# -*- coding: utf-8 -*-
"""企微双开工具 - 使用更可靠的方式"""
import sys
import os
import subprocess
import time
import ctypes
import ctypes.wintypes as wintypes
from typing import List


def is_admin() -> bool:
    """检查是否以管理员身份运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def require_admin():
    """请求管理员权限，重启程序"""
    if not is_admin():
        try:
            script = os.path.abspath(sys.argv[0])
            params = ' '.join([script] + sys.argv[1:])
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            sys.exit(0)
        except Exception as e:
            print(f"无法获取管理员权限: {e}")
            return False
    return True


def find_processes_by_name(name: str) -> List[int]:
    """根据进程名查找所有进程ID"""
    try:
        import psutil
        return [proc.pid for proc in psutil.process_iter(['pid', 'name']) if proc.info['name'] == name]
    except ImportError:
        pass
    
    # 备用方案：使用 tasklist
    result = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {name}', '/FO', 'CSV'], 
                          capture_output=True, text=True, encoding='gbk')
    pids = []
    for line in result.stdout.splitlines():
        if name in line:
            try:
                parts = line.split(',')
                if len(parts) >= 2:
                    pids.append(int(parts[1].strip('"')))
            except:
                pass
    return pids


def close_wework_handles_by_pid(pid: int) -> int:
    """使用更简单可靠的方式：调用外部工具或使用简单的方法"""
    # 方法1：使用 ProcessHacker 或 handle.exe（如果有的话）
    handle_tools = [
        os.path.join(os.path.dirname(__file__), 'handle.exe'),
        r'C:\Program Files\Process Hacker 2\handle.exe',
    ]
    
    for tool_path in handle_tools:
        if os.path.exists(tool_path):
            return close_handles_with_tool(tool_path, pid)
    
    # 方法2：使用我们自己的实现
    return close_handles_native(pid)


def close_handles_native(pid: int) -> int:
    """使用原生Windows API关闭句柄"""
    closed_count = 0
    
    # 定义Windows API
    kernel32 = ctypes.windll.kernel32
    ntdll = ctypes.windll.ntdll
    
    # 打开目标进程
    process_handle = kernel32.OpenProcess(0x001F0FFF, False, pid)
    if not process_handle:
        return 0
    
    try:
        # 目标句柄名（部分匹配即可）
        target_patterns = [
            "Tencent.WeWork.ExclusiveObject",
            "Tencent.WeWork.ExclusiveObjectInstance1"
        ]
        
        # 使用简单的方式：通过 DuplicateHandle 尝试关闭所有可能的句柄
        # 这里我们使用一个更直接的方法
        import struct
        
        # 尝试遍历句柄范围
        for handle_value in range(0x4, 0x10000, 4):
            # 尝试复制句柄以检查
            dup_handle = wintypes.HANDLE()
            success = kernel32.DuplicateHandle(
                process_handle,
                handle_value,
                ctypes.windll.kernel32.GetCurrentProcess(),
                ctypes.byref(dup_handle),
                0,
                False,
                0x00000002  # DUPLICATE_SAME_ACCESS
            )
            
            if success:
                try:
                    # 尝试获取句柄名称
                    size = 0x1000
                    buffer = ctypes.create_unicode_buffer(size)
                    ret_len = wintypes.ULONG()
                    
                    status = ntdll.NtQueryObject(
                        dup_handle,
                        1,  # ObjectNameInformation
                        buffer,
                        size,
                        ctypes.byref(ret_len)
                    )
                    
                    if status == 0:
                        name = buffer.value
                        for pattern in target_patterns:
                            if pattern in name:
                                # 找到目标句柄，关闭它
                                if kernel32.DuplicateHandle(
                                    process_handle,
                                    handle_value,
                                    0,
                                    None,
                                    0,
                                    False,
                                    0x00000001  # DUPLICATE_CLOSE_SOURCE
                                ):
                                    closed_count += 1
                                    print(f"  ✓ 已关闭: {name}")
                finally:
                    kernel32.CloseHandle(dup_handle)
    finally:
        kernel32.CloseHandle(process_handle)
    
    return closed_count


def close_handles_with_tool(tool_path: str, pid: int) -> int:
    """使用外部工具关闭句柄"""
    closed_count = 0
    target_patterns = [
        "Tencent.WeWork.ExclusiveObject",
        "Tencent.WeWork.ExclusiveObjectInstance1"
    ]
    
    try:
        result = subprocess.run([tool_path, '-p', str(pid)], 
                              capture_output=True, text=True, encoding='gbk', errors='ignore')
        
        for line in result.stdout.splitlines():
            if any(p in line for p in target_patterns):
                try:
                    # 解析句柄ID
                    parts = line.strip().split(':')
                    if len(parts) >= 1:
                        handle_id = parts[0].strip()
                        if handle_id.startswith('0x'):
                            # 关闭句柄
                            subprocess.run([tool_path, '-c', handle_id, '-p', str(pid), '-y'],
                                          capture_output=True)
                            closed_count += 1
                            print(f"  ✓ 已关闭句柄 {handle_id}")
                except:
                    pass
    except Exception as e:
        print(f"工具调用失败: {e}")
    
    return closed_count


def wework_double_open():
    """主函数：企微双开"""
    print("=" * 60)
    print("企微双开工具 v2.0")
    print("=" * 60)
    
    # 1. 请求管理员权限
    if not require_admin():
        print("\n❌ 需要管理员权限！")
        input("\n按回车键退出...")
        return
    
    print("✓ 已获取管理员权限")
    
    # 2. 查找企业微信进程
    wework_pids = find_processes_by_name("WXWork.exe")
    if not wework_pids:
        print("\n❌ 未找到运行中的企业微信进程！")
        print("请先打开一个企业微信，然后再运行此工具")
        input("\n按回车键退出...")
        return
    
    print(f"\n✓ 找到 {len(wework_pids)} 个企业微信进程: {wework_pids}")
    
    # 3. 处理每个进程
    total_closed = 0
    for i, pid in enumerate(wework_pids, 1):
        print(f"\n[{i}/{len(wework_pids)}] 处理进程 {pid}...")
        closed = close_wework_handles_by_pid(pid)
        total_closed += closed
        if closed > 0:
            print(f"  ✓ 进程 {pid} 关闭了 {closed} 个句柄")
        else:
            print(f"  ℹ 进程 {pid} 无需处理或未找到目标句柄")
    
    print("\n" + "=" * 60)
    if total_closed > 0:
        print(f"✓ 成功！共关闭 {total_closed} 个互斥体")
        print("\n现在您可以打开第二个企业微信了！")
    else:
        print("ℹ 未找到需要关闭的句柄")
        print("请确认企业微信正在运行，或者已经可以双开")
    
    print("\n" + "=" * 60)
    input("\n按回车键退出...")


def create_batch_file():
    """创建批处理文件方便用户运行"""
    batch_content = '''@echo off
chcp 65001 >nul
title 企微双开工具
python "%~dp0wework_tool.py"
pause
'''
    batch_path = os.path.join(os.path.dirname(__file__), "企微双开.bat")
    with open(batch_path, 'w', encoding='utf-8') as f:
        f.write(batch_content)
    return batch_path


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--create-bat':
        create_batch_file()
        print(f"已创建批处理文件")
    else:
        wework_double_open()
