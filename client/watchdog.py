# -*- coding: utf-8 -*-
"""客户端监控脚本 - 自动重启已关闭的客户端"""
import sys
import os
import time
import subprocess
from pathlib import Path


def get_process_count(process_name):
    """获取进程数量"""
    try:
        result = subprocess.run(
            ['tasklist', '/fi', f'IMAGENAME eq {process_name}'],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        return result.stdout.count(process_name) - 1  # 减去标题行
    except Exception as e:
        print(f"检查进程失败: {e}")
        return -1


def start_client(exe_path):
    """启动客户端"""
    try:
        subprocess.Popen(
            [exe_path],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        return True
    except Exception as e:
        print(f"启动失败: {e}")
        return False


def main():
    """主函数"""
    script_dir = Path(__file__).parent
    exe_path = script_dir / 'dist' / 'NotificationClient.exe'
    process_name = 'NotificationClient.exe'
    
    restart_delay = 3  # 重启延迟（秒）
    max_restarts = 100  # 最大重启次数
    restart_count = 0
    
    print("=" * 50)
    print("Notification Client Watchdog")
    print("=" * 50)
    print()
    
    if not exe_path.exists():
        print(f"[错误] 找不到 EXE 文件: {exe_path}")
        print("请先运行 build.bat 构建程序")
        input("\n按回车键退出...")
        sys.exit(1)
    
    print(f"监控进程: {process_name}")
    print(f"最大重启次数: {max_restarts}")
    print(f"重启延迟: {restart_delay} 秒")
    print()
    print("按 Ctrl+C 可以安全退出")
    print()
    print("开始监控...")
    print()
    
    try:
        while True:
            count = get_process_count(process_name)
            
            if count == 0:
                restart_count += 1
                if restart_count <= max_restarts:
                    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{current_time}] 客户端已关闭，重启中... (第 {restart_count} 次)")
                    
                    time.sleep(restart_delay)
                    
                    if start_client(str(exe_path)):
                        print(f"[{current_time}] 重启成功!")
                    else:
                        print(f"[{current_time}] 重启失败!")
                else:
                    print()
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 已达到最大重启次数 ({max_restarts})")
                    print("客户端将不再自动重启")
                    print("请手动启动客户端或重启此监控程序")
                    input("\n按回车键退出...")
                    break
            elif count > 1:
                print(f"[警告] 检测到多个客户端进程: {count}")
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print()
        print()
        print("=" * 50)
        print("监控程序已退出")
        print(f"总共重启次数: {restart_count}")
        print("=" * 50)


if __name__ == '__main__':
    main()
