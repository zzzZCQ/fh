# -*- coding: utf-8 -*-
"""工具箱路由 - 企微双开等工具管理"""
import os
import zipfile
import subprocess
from datetime import datetime
from io import BytesIO
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify, send_file
from flask_login import current_user
from werkzeug.utils import secure_filename

from models import db, ToolFile, Group
from helpers import role_required, get_unread_count
from flask_login import login_required

bp = Blueprint('tools', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'apps')
ALLOWED_EXTENSIONS = {'exe'}


def is_super_admin():
    return current_user.has_role('admin')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def has_file_permission(file_obj):
    """检查当前用户是否有权限访问该文件：文件对上传者的本级组及下级组用户可见"""
    uploader = file_obj.uploader
    if not uploader or not uploader.group_id:
        return False
    
    uploader_group = Group.query.get(uploader.group_id)
    if not uploader_group:
        return False
    
    # 获取上传者组及其所有下级组的ID列表
    visible_group_ids = [uploader_group.id]
    visible_group_ids.extend(uploader_group.get_all_children_ids())
    
    # 检查当前用户组是否在可见范围内
    if not current_user.group_id:
        return False
    
    return current_user.group_id in visible_group_ids


@bp.route('/tools')
@login_required
def tools_page():
    """工具箱页面"""
    apps = []
    apps_dir = UPLOAD_FOLDER
    if os.path.exists(apps_dir):
        for f in os.listdir(apps_dir):
            if f.endswith('.exe'):
                filepath = os.path.join(apps_dir, f)
                stat = os.stat(filepath)
                apps.append({
                    'name': f,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
    
    return render_template('tools.html', apps=apps, is_super_admin=is_super_admin(), unread_count=get_unread_count(current_user.id))


@bp.route('/tools/upload', methods=['POST'])
def upload_app():
    """上传exe应用"""
    if not is_super_admin():
        flash('只有超级管理员才能上传应用！', 'danger')
        return redirect(url_for('tools.tools_page'))
    
    file = request.files.get('file')
    
    if not file or file.filename == '':
        flash('请选择文件！', 'danger')
        return redirect(url_for('tools.tools_page'))
    
    if not allowed_file(file.filename):
        flash('只允许上传 .exe 文件！', 'danger')
        return redirect(url_for('tools.tools_page'))
    
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    if os.path.exists(filepath):
        flash(f'文件 {filename} 已存在，将被覆盖！', 'warning')
        os.remove(filepath)
    
    file.save(filepath)
    flash(f'上传成功！', 'success')
    return redirect(url_for('tools.tools_page'))


@bp.route('/tools/delete/<filename>', methods=['POST'])
def delete_app(filename):
    """删除exe应用"""
    if not is_super_admin():
        flash('只有超级管理员才能删除应用！', 'danger')
        return redirect(url_for('tools.tools_page'))
    
    filename = secure_filename(filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    if os.path.exists(filepath):
        os.remove(filepath)
        flash(f'删除成功！', 'success')
    else:
        flash('文件不存在！', 'danger')
    
    return redirect(url_for('tools.tools_page'))


@bp.route('/tools/launch/<filename>', methods=['POST'])
def launch_app(filename):
    """启动exe应用（以管理员身份运行）"""
    filename = secure_filename(filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'message': '文件不存在'})
    
    try:
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(None, "runas", filepath, None, None, 1)
        return jsonify({'success': True, 'message': f'已以管理员身份启动 {filename}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@bp.route('/tools/download_wework')
@login_required
def download_wework():
    """下载企微双开工具包"""
    wework_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wework_double_open')
    
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 添加目录下的所有文件
        for root, dirs, files in os.walk(wework_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, wework_dir)
                zf.write(file_path, arcname)
    
    memory_file.seek(0)
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='企微双开工具.zip'
    )


@bp.route('/tools/download_wework_python')
@login_required
def download_wework_python():
    """下载Python版本"""
    wework_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wework_double_open')
    
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 只添加Python相关文件
        files_to_add = ['企微双开.bat', 'wework_tool.py', '使用说明.txt']
        for file in files_to_add:
            file_path = os.path.join(wework_dir, file)
            if os.path.exists(file_path):
                zf.write(file_path, file)
    
    memory_file.seek(0)
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='企微双开_Python版.zip'
    )


@bp.route('/tools/files')
@login_required
def files_page():
    """文件管理页面"""
    is_admin = current_user.has_role('admin')
    return render_template('file_management.html', is_admin=is_admin, unread_count=get_unread_count(current_user.id))


@bp.route('/tools/files/api/list')
@login_required
def list_files():
    """获取文件列表API - 权限隔离：文件对上传者的同级组、本级组、下级组用户都可见"""
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    # 获取所有文件，然后在内存中进行权限过滤
    query = ToolFile.query
    
    if search:
        query = query.filter(
            db.or_(
                ToolFile.name.like(f'%{search}%'),
                ToolFile.filename.like(f'%{search}%'),
                ToolFile.category.like(f'%{search}%')
            )
        )
    
    if category:
        query = query.filter(ToolFile.category == category)
    
    query = query.order_by(ToolFile.create_time.desc())
    all_files = query.all()
    
    # 在内存中过滤：只保留当前用户有权限查看的文件
    files = []
    for file in all_files:
        if has_file_permission(file):
            files.append(file)
    
    # 获取所有可见文件的分类
    category_set = set()
    for file in files:
        if file.category:
            category_set.add(file.category)
    categories = list(category_set)
    
    result = []
    for file in files:
        result.append({
            'id': file.id,
            'name': file.name,
            'filename': file.filename,
            'category': file.category,
            'uploader': file.uploader.name if file.uploader else '',
            'create_time': file.create_time.strftime('%Y-%m-%d %H:%M:%S') if file.create_time else '',
            'is_admin': current_user.has_role('admin')
        })
    
    return jsonify({'files': result, 'categories': categories})


@bp.route('/tools/files/upload', methods=['POST'])
@login_required
def upload_tool_file():
    """上传工具文件 - 仅admin可上传"""
    if not current_user.has_role('admin'):
        return jsonify({'success': False, 'message': '只有管理员可以上传文件！'}), 403
    
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    file = request.files.get('file')
    
    if not name:
        return jsonify({'success': False, 'message': '请输入文件名称！'}), 400
    
    if not file or file.filename == '':
        return jsonify({'success': False, 'message': '请选择要上传的文件！'}), 400
    
    # 保存文件
    upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'tool_files')
    os.makedirs(upload_dir, exist_ok=True)
    
    original_filename = secure_filename(file.filename)
    filename = f"{int(datetime.now().timestamp())}_{original_filename}"
    filepath = os.path.join(upload_dir, filename)
    
    file.save(filepath)
    
    # 保存到数据库
    tool_file = ToolFile(
        name=name,
        filename=original_filename,
        filepath=filepath,
        category=category,
        uploader_id=current_user.id,
        group_id=current_user.group_id
    )
    db.session.add(tool_file)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '上传成功！'})


@bp.route('/tools/files/delete/<int:file_id>', methods=['POST'])
@login_required
def delete_tool_file(file_id):
    """删除工具文件 - 仅admin可删除，且只能删除有权限访问的文件"""
    if not current_user.has_role('admin'):
        return jsonify({'success': False, 'message': '只有管理员可以删除文件！'}), 403
    
    tool_file = ToolFile.query.get_or_404(file_id)
    
    # 检查权限
    if not has_file_permission(tool_file):
        return jsonify({'success': False, 'message': '您没有权限删除该文件！'}), 403
    
    # 删除文件
    if os.path.exists(tool_file.filepath):
        os.remove(tool_file.filepath)
    
    # 删除记录
    db.session.delete(tool_file)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '删除成功！'})


@bp.route('/tools/files/download/<int:file_id>')
@login_required
def download_tool_file(file_id):
    """下载工具文件 - 权限隔离：只能下载有权限访问的文件"""
    tool_file = ToolFile.query.get_or_404(file_id)
    
    # 检查权限
    if not has_file_permission(tool_file):
        return jsonify({'success': False, 'message': '您没有权限下载该文件！'}), 403
    
    if not os.path.exists(tool_file.filepath):
        return jsonify({'success': False, 'message': '文件不存在！'}), 404
    
    return send_file(
        tool_file.filepath,
        as_attachment=True,
        download_name=tool_file.filename
    )


@bp.route('/tools/git')
@role_required('admin')
def git_page():
    """Git操作页面"""
    return render_template('admin_git.html', unread_count=get_unread_count(current_user.id))


@bp.route('/tools/git/status')
@role_required('admin')
def git_status():
    """获取Git状态"""
    try:
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True, encoding='utf-8', cwd=os.path.dirname(os.path.abspath(__file__)))
        changed_files = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        
        remotes = subprocess.run(['git', 'remote', '-v'], capture_output=True, text=True, encoding='utf-8', cwd=os.path.dirname(os.path.abspath(__file__)))
        remote_info = {}
        for line in remotes.stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    remote_info[parts[0]] = parts[1]
        
        branches = subprocess.run(['git', 'branch'], capture_output=True, text=True, encoding='utf-8', cwd=os.path.dirname(os.path.abspath(__file__)))
        current_branch = ''
        all_branches = []
        for line in branches.stdout.strip().split('\n'):
            branch = line.strip().lstrip('* ').strip()
            all_branches.append(branch)
            if line.strip().startswith('*'):
                current_branch = branch
        
        return jsonify({
            'has_changes': len(changed_files) > 0,
            'changed_files': changed_files,
            'remote': remote_info.get('origin', ''),
            'current_branch': current_branch,
            'all_branches': all_branches,
            'is_repo': True
        })
    except FileNotFoundError:
        return jsonify({'error': '未检测到Git，请安装Git', 'is_repo': False}), 200
    except Exception as e:
        return jsonify({'error': str(e), 'is_repo': False}), 200


@bp.route('/tools/git/commit', methods=['POST'])
@role_required('admin')
def git_commit():
    """提交代码"""
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'success': False, 'message': '请输入提交信息'}), 400
    
    try:
        subprocess.run(['git', 'add', '.'], capture_output=True, encoding='utf-8', cwd=os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(['git', 'commit', '-m', message], capture_output=True, text=True, encoding='utf-8', cwd=os.path.dirname(os.path.abspath(__file__)))
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': '提交成功'})
        else:
            return jsonify({'success': False, 'message': result.stderr or '提交失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/tools/git/push', methods=['POST'])
@role_required('admin')
def git_push():
    """推送到远程仓库"""
    try:
        result = subprocess.run(['git', 'push'], capture_output=True, text=True, encoding='utf-8', cwd=os.path.dirname(os.path.abspath(__file__)))
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': '推送成功'})
        else:
            return jsonify({'success': False, 'message': result.stderr or '推送失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/tools/git/pull', methods=['POST'])
@role_required('admin')
def git_pull():
    """从远程仓库拉取"""
    try:
        result = subprocess.run(['git', 'pull'], capture_output=True, text=True, encoding='utf-8', cwd=os.path.dirname(os.path.abspath(__file__)))
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': '拉取成功', 'output': result.stdout})
        else:
            return jsonify({'success': False, 'message': result.stderr or '拉取失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/tools/git/clone', methods=['POST'])
@role_required('admin')
def git_clone():
    """克隆远程仓库"""
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'success': False, 'message': '请输入仓库地址'}), 400
    
    try:
        result = subprocess.run(['git', 'clone', url, '.'], capture_output=True, text=True, encoding='utf-8', cwd=os.path.dirname(os.path.abspath(__file__)))
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': '克隆成功'})
        else:
            return jsonify({'success': False, 'message': result.stderr or '克隆失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/tools/git/log')
@role_required('admin')
def git_log():
    """获取提交日志"""
    try:
        result = subprocess.run(['git', 'log', '--oneline', '-20'], capture_output=True, text=True, encoding='utf-8', cwd=os.path.dirname(os.path.abspath(__file__)))
        logs = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        return jsonify({'logs': logs})
    except Exception as e:
        return jsonify({'logs': [], 'error': str(e)}), 200


@bp.route('/tools/download_wework_monitor')
@login_required
def download_wework_monitor():
    """下载企微通话监控工具"""
    wework_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wework_call_monitor')
    
    if not os.path.exists(wework_dir):
        os.makedirs(wework_dir)
    
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 创建监控脚本
        monitor_script = '''# -*- coding: utf-8 -*-
"""企业微信通话监控脚本"""
import time
import json
import requests
import win32gui
import win32process
import psutil
from datetime import datetime

# === 配置 ===
SERVER_URL = "http://127.0.0.1:5000/wework/api/record"  # 服务器地址
CHECK_INTERVAL = 1  # 检查间隔（秒）

# === 全局变量 ===
active_calls = {}  # {窗口句柄: {'user_name': 'xxx', 'start_time': '2024-01-01T00:00:00'}}


def get_window_text(hwnd):
    """获取窗口标题"""
    return win32gui.GetWindowText(hwnd)


def is_wework_call_window(hwnd):
    """判断是否是企微通话窗口"""
    title = get_window_text(hwnd)
    if not title:
        return False
    # 企微通话窗口特征：包含"语音通话"、"视频通话"或时长显示
    keywords = ["语音通话", "视频通话", "通话中", "秒", "分"]
    for kw in keywords:
        if kw in title:
            return True
    return False


def extract_user_name(title):
    """从窗口标题中提取用户名"""
    # 常见格式："与张三的语音通话"、"李四 - 语音通话"
    title = title.replace("语音通话", "").replace("视频通话", "").replace("通话中", "")
    title = title.replace("与", "").replace("的", "").replace("-", "").strip()
    # 移除时长信息（如 "00:05"）
    import re
    title = re.sub(r'\\d+:\\d+', '', title).strip()
    title = re.sub(r'\\d+分\\d+秒', '', title).strip()
    title = re.sub(r'\\d+秒', '', title).strip()
    return title if title else "未知用户"


def upload_call_record(user_name, start_time, end_time=None):
    """上传通话记录到服务器"""
    try:
        data = {
            "user_name": user_name,
            "call_start_time": start_time
        }
        if end_time:
            data["call_end_time"] = end_time
        
        response = requests.post(SERVER_URL, json=data, timeout=5)
        return response.json()
    except Exception as e:
        print(f"上传失败: {e}")
        return None


def enum_windows_callback(hwnd, _):
    """枚举窗口回调函数"""
    if not win32gui.IsWindowVisible(hwnd):
        return True
    
    if is_wework_call_window(hwnd):
        title = get_window_text(hwnd)
        user_name = extract_user_name(title)
        
        if hwnd not in active_calls:
            # 新通话开始
            start_time = datetime.now().isoformat()
            active_calls[hwnd] = {
                "user_name": user_name,
                "start_time": start_time
            }
            print(f"通话开始: {user_name}")
            upload_call_record(user_name, start_time)
    
    return True


def main():
    print("企业微信通话监控已启动...")
    print(f"服务器地址: {SERVER_URL}")
    print("按 Ctrl+C 停止监控\\n")
    
    try:
        while True:
            # 枚举所有窗口
            win32gui.EnumWindows(enum_windows_callback, None)
            
            # 检查已结束的通话
            current_hwnds = set()
            def check_callback(hwnd, _):
                if is_wework_call_window(hwnd):
                    current_hwnds.add(hwnd)
                return True
            
            win32gui.EnumWindows(check_callback, None)
            
            # 处理已结束的通话
            hwnds_to_remove = []
            for hwnd in list(active_calls.keys()):
                if hwnd not in current_hwnds:
                    # 通话结束
                    call_info = active_calls[hwnd]
                    end_time = datetime.now().isoformat()
                    print(f"通话结束: {call_info['user_name']}")
                    upload_call_record(call_info['user_name'], call_info['start_time'], end_time)
                    hwnds_to_remove.append(hwnd)
            
            for hwnd in hwnds_to_remove:
                del active_calls[hwnd]
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\\n监控已停止")


if __name__ == "__main__":
    main()
'''
        
        # 创建 requirements.txt
        requirements_content = '''requests==2.31.0
pywin32==306
psutil==5.9.5
'''
        
        # 创建启动脚本
        start_bat = '''@echo off
chcp 65001 >nul
echo 正在启动企业微信通话监控...
echo.
python wework_call_monitor.py
if errorlevel 1 (
    echo.
    echo 程序异常退出，请检查是否已安装Python和依赖库
    pause
)
'''
        
        # 创建配置示例
        config_example = '''# 企业微信通话监控配置
# 将此文件复制为 config.py 并修改配置

SERVER_URL = "http://192.168.1.100:5000/wework/api/record"  # 修改为你的服务器地址
CHECK_INTERVAL = 1
'''
        
        # 创建使用说明
        readme_content = '''企业微信通话监控工具
====================

一、安装依赖
1. 确保已安装 Python 3.7+
2. 运行: pip install -r requirements.txt

二、配置
1. 编辑 wework_call_monitor.py，修改 SERVER_URL 为你的服务器地址

三、运行
1. 双击运行 启动监控.bat
2. 或者运行: python wework_call_monitor.py

四、说明
- 监控会自动检测企业微信的语音/视频通话窗口
- 通话开始时自动记录，结束时上传时长
- 数据会自动同步到服务器的"企业微信通话记录"页面
'''
        
        # 写入文件到zip
        zf.writestr('wework_call_monitor.py', monitor_script)
        zf.writestr('requirements.txt', requirements_content)
        zf.writestr('启动监控.bat', start_bat)
        zf.writestr('config_example.py', config_example)
        zf.writestr('使用说明.txt', readme_content)
    
    memory_file.seek(0)
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='企微通话监控工具.zip'
    )
