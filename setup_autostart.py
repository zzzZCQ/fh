# -*- coding: utf-8 -*-
"""设置开机自启动"""
import os
import sys
import winreg
import ctypes
from pathlib import Path

def is_admin():
    """检查是否以管理员身份运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_pythonw_path():
    """获取pythonw.exe路径"""
    return sys.executable.replace('python.exe', 'pythonw.exe')

def add_to_startup():
    """添加到开机自启动（使用注册表）"""
    try:
        # 获取当前脚本路径
        script_path = os.path.abspath(__file__)
        server_script = os.path.join(os.path.dirname(script_path), 'start_server.py')
        
        if not os.path.exists(server_script):
            print(f"Error: {server_script} not found")
            return False
        
        # Pythonw路径
        pythonw_path = get_pythonw_path()
        
        # 命令行参数
        command = f'"{pythonw_path}" "{server_script}"'
        
        # 写入注册表
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_WRITE
        )
        
        winreg.SetValueEx(key, "NotificationService", 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
        
        print("Successfully added to startup!")
        print(f"Command: {command}")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

def remove_from_startup():
    """从开机自启动移除"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_WRITE
        )
        
        try:
            winreg.DeleteValue(key, "NotificationService")
            print("Successfully removed from startup!")
        except FileNotFoundError:
            print("Startup entry not found, may already be removed")
        
        winreg.CloseKey(key)
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

def check_startup():
    """检查是否已添加到开机自启动"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ
        )
        
        try:
            value, _ = winreg.QueryValueEx(key, "NotificationService")
            winreg.CloseKey(key)
            return True, value
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False, None
            
    except Exception as e:
        return False, None

def main():
    print("=" * 50)
    print("Notification Service Autostart Setup")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        action = sys.argv[1].lower()
    else:
        print("\nCommands:")
        print("  install   - Add to startup")
        print("  uninstall - Remove from startup")
        print("  check     - Check current status")
        print()
        action = input("Enter command (install/uninstall/check): ").lower()
    
    if action == 'install':
        print("\nAdding to startup...")
        if add_to_startup():
            print("\nDone! Service will start on next boot.")
            print("To start immediately, run: start_server.vbs")
    
    elif action == 'uninstall':
        print("\nRemoving from startup...")
        remove_from_startup()
    
    elif action == 'check':
        exists, value = check_startup()
        if exists:
            print(f"\nStartup entry exists:")
            print(f"  {value}")
        else:
            print("\nNo startup entry found.")
    
    else:
        print(f"\nUnknown command: {action}")

if __name__ == '__main__':
    main()
    print()
    input("Press Enter to exit...")