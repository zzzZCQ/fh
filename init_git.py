# -*- coding: utf-8 -*-
"""初始化Git仓库脚本"""
import os
import subprocess
import sys

def run_command(cmd, check=True):
    """运行命令"""
    print(f"$ {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True, encoding='utf-8')
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败: {e}")
        print(e.stdout)
        print(e.stderr)
        return False

def main():
    print("=" * 50)
    print("Git仓库初始化脚本")
    print("=" * 50)
    print()
    
    # 检查是否已安装git
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
    except FileNotFoundError:
        print("错误：未检测到Git，请先安装Git")
        print("下载地址：https://git-scm.com/download/win")
        input("按回车键退出...")
        return 1
    
    # 检查是否已初始化
    if os.path.exists(".git"):
        print("提示：Git仓库已存在")
    else:
        print("步骤1：初始化Git仓库...")
        if not run_command("git init"):
            return 1
    
    print()
    print("步骤2：设置用户信息...")
    name = input("请输入您的名字 (默认: Auto Committer): ").strip() or "Auto Committer"
    email = input("请输入您的邮箱 (默认: auto@example.com): ").strip() or "auto@example.com"
    
    run_command(f'git config user.name "{name}"', check=False)
    run_command(f'git config user.email "{email}"', check=False)
    
    print()
    print("步骤3：添加所有文件...")
    run_command("git add .", check=False)
    
    print()
    print("步骤4：创建初始提交...")
    run_command('git commit -m "初始提交: 发货通知系统"', check=False)
    
    print()
    print("=" * 50)
    print("初始化完成！")
    print("=" * 50)
    print()
    print("接下来的步骤：")
    print("1. 如果需要关联远程仓库，运行:")
    print('   git remote add origin <仓库地址>')
    print("2. 设置定时任务，运行 setup_scheduled_task.bat")
    print()
    input("按回车键退出...")
    return 0

if __name__ == "__main__":
    sys.exit(main())
