# -*- coding: utf-8 -*-
"""工具箱路由 - 企微双开等工具管理"""
import os
import zipfile
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
    """检查当前用户是否有权限访问该文件"""
    uploader = file_obj.uploader
    if not uploader or not uploader.group_id:
        return False
    
    uploader_group = Group.query.get(uploader.group_id)
    if not uploader_group:
        return False
    
    current_user_group = Group.query.get(current_user.group_id)
    if not current_user_group:
        return False
    
    # 检查：当前用户组是否在上传者组的下级（包括本级、子级、孙级等）
    # 即：当前用户组是否是上传者组本身，或者上传者组是当前用户组的祖先
    def is_self_or_descendant(uploader_grp, check_grp):
        """检查 check_grp 是否是 uploader_grp 本身或其后代"""
        if check_grp.id == uploader_grp.id:
            return True
        
        # 递归检查祖先
        temp_group = check_grp
        while temp_group.parent_id:
            if temp_group.parent_id == uploader_grp.id:
                return True
            temp_group = Group.query.get(temp_group.parent_id)
            if not temp_group:
                break
        
        return False
    
    return is_self_or_descendant(uploader_group, current_user_group)


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
