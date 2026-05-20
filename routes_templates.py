# -*- coding: utf-8 -*-
"""Excel模板管理、组别管理路由"""
import os
import json
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, flash, render_template, send_file
from flask_login import current_user
from werkzeug.utils import secure_filename

from models import db, Category, ExcelTemplate, ImportTemplate, Group, Order, _now_bj
from helpers import role_required, get_unread_count

bp = Blueprint('templates', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'templates')
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============ Excel模板管理 ============
@bp.route('/admin/templates')
@role_required('admin')
def admin_templates():
    """模板管理页面"""
    export_page = request.args.get('export_page', 1, type=int)
    import_page = request.args.get('import_page', 1, type=int)

    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order.asc()).all()

    # 导出模板分页
    templates = ExcelTemplate.query.paginate(
        page=export_page, per_page=10, error_out=False)

    # 导入模板分页
    import_templates = ImportTemplate.query.paginate(
        page=import_page, per_page=10, error_out=False)

    return render_template('admin_templates.html', categories=categories,
                           templates=templates, import_templates=import_templates,
                           unread_count=get_unread_count(current_user.id))


# ============ 组别管理 ============
@bp.route('/admin/groups')
@role_required('admin')
def admin_groups():
    """组别管理页面"""
    # 超级管理员或有admin角色的用户看所有组别，其他只看本级及下级
    is_super_admin = current_user.username == 'admin'
    if is_super_admin or current_user.has_role('admin'):
        groups = Group.query.order_by(Group.level.asc(), Group.create_time.asc()).all()
    elif current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        groups = Group.query.filter(Group.id.in_(managed_group_ids)).order_by(Group.level.asc(), Group.create_time.asc()).all()
    else:
        groups = []

    # 计算当前用户可管理的组别ID（用于前端按钮权限控制）
    # 有admin角色（包括超级管理员）可以管理所有组别
    if is_super_admin or current_user.has_role('admin'):
        managed_group_ids = [g.id for g in groups]
    elif current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
    else:
        managed_group_ids = []

    return render_template('admin_groups.html', groups=groups,
                           managed_group_ids=managed_group_ids,
                           is_super_admin=is_super_admin,
                           unread_count=get_unread_count(current_user.id))


@bp.route('/admin/group/add', methods=['POST'])
@role_required('admin')
def add_group():
    """新增组别"""
    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip()
    parent_id = request.form.get('parent_id', type=int)

    if not name:
        flash('组名不能为空！', 'danger')
        return redirect(url_for('templates.admin_groups'))

    # 非超级管理员只能在自己所属组及下级组下创建子组
    if current_user.username != 'admin' and current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        if parent_id and parent_id not in managed_group_ids:
            flash('只能在您所属的组别范围内创建子组！', 'danger')
            return redirect(url_for('templates.admin_groups'))
        if not parent_id:
            flash('只能在您所属的组别范围内创建子组！', 'danger')
            return redirect(url_for('templates.admin_groups'))

    # 计算层级
    level = 1
    if parent_id:
        parent = Group.query.get(parent_id)
        if parent:
            level = parent.level + 1

    group = Group(name=name, code=code, parent_id=parent_id, level=level)
    db.session.add(group)
    db.session.commit()
    flash(f'组别 "{name}" 添加成功！', 'success')
    return redirect(url_for('templates.admin_groups'))


@bp.route('/admin/group/edit/<int:group_id>', methods=['POST'])
@role_required('admin')
def edit_group(group_id):
    """编辑组别"""
    group = Group.query.get_or_404(group_id)

    # 非超级管理员只能编辑本级及下级组
    if current_user.username != 'admin' and current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        if group_id not in managed_group_ids:
            flash('只能编辑本级及下级组别！', 'danger')
            return redirect(url_for('templates.admin_groups'))

    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip()
    parent_id = request.form.get('parent_id', type=int)

    if not name:
        flash('组名不能为空！', 'danger')
        return redirect(url_for('templates.admin_groups'))

    # 检查循环引用
    if parent_id == group_id:
        flash('不能将自己设为父级！', 'danger')
        return redirect(url_for('templates.admin_groups'))

    # 计算新层级
    level = 1
    if parent_id:
        parent = Group.query.get(parent_id)
        if parent:
            level = parent.level + 1

    group.name = name
    group.code = code
    group.parent_id = parent_id
    group.level = level
    db.session.commit()
    flash(f'组别 "{name}" 修改成功！', 'success')
    return redirect(url_for('templates.admin_groups'))


@bp.route('/admin/group/toggle/<int:group_id>', methods=['POST'])
@role_required('admin')
def toggle_group(group_id):
    """停用/启用组别"""
    group = Group.query.get_or_404(group_id)

    # 非超级管理员只能停用/启用本级及下级组
    if current_user.username != 'admin' and current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        if group_id not in managed_group_ids:
            flash('只能操作本级及下级组别！', 'danger')
            return redirect(url_for('templates.admin_groups'))

    group.is_active = not group.is_active
    db.session.commit()
    status = '启用' if group.is_active else '停用'
    flash(f'组别 "{group.name}" 已{status}！', 'success')
    return redirect(url_for('templates.admin_groups'))


@bp.route('/admin/group/delete/<int:group_id>', methods=['POST'])
@role_required('admin')
def delete_group(group_id):
    """删除组别"""
    group = Group.query.get_or_404(group_id)

    # 非超级管理员只能删除本级及下级组
    if current_user.username != 'admin' and current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        if group_id not in managed_group_ids:
            flash('只能删除本级及下级组别！', 'danger')
            return redirect(url_for('templates.admin_groups'))

    # 检查是否有子组（有子组则不能删除）
    if group.children:
        flash(f'组别 "{group.name}" 下有子组，请先删除子组！', 'danger')
        return redirect(url_for('templates.admin_groups'))

    # 检查是否有关联的用户
    from models import User
    user_count = User.query.filter_by(group_id=group.id).count()
    if user_count > 0:
        flash(f'组别 "{group.name}" 下有 {user_count} 个用户，请先移动用户再删除！', 'danger')
        return redirect(url_for('templates.admin_groups'))

    # 检查是否有关联的订单
    order_count = Order.query.filter_by(group_id=group.id).count()
    if order_count > 0:
        flash(f'组别 "{group.name}" 下有 {order_count} 个订单，请先处理订单再删除！', 'danger')
        return redirect(url_for('templates.admin_groups'))

    group_name = group.name
    db.session.delete(group)
    db.session.commit()
    flash(f'组别 "{group_name}" 已删除！', 'success')
    return redirect(url_for('templates.admin_groups'))


@bp.route('/admin/template/upload', methods=['POST'])
@role_required('admin')
def upload_template():
    """上传模板"""
    category_id = request.form.get('category_id', type=int)
    file = request.files.get('file')

    if not category_id:
        flash('请选择产品类别！', 'danger')
        return redirect(url_for('templates.admin_templates'))
    if not file or file.filename == '':
        flash('请选择文件！', 'danger')
        return redirect(url_for('templates.admin_templates'))
    if not allowed_file(file.filename):
        flash('只允许上传Excel文件（.xlsx, .xls）！', 'danger')
        return redirect(url_for('templates.admin_templates'))

    # 收集字段映射（支持正则表达式）
    field_mapping = {}
    idx = 0
    while True:
        excel_col = request.form.get(f'excel_col_{idx}', '').strip()
        order_field = request.form.get(f'order_field_{idx}', '').strip()
        regex_field = request.form.get(f'regex_field_{idx}', '').strip()
        if not excel_col and not order_field and not regex_field:
            break
        # 优先使用正则表达式
        actual_field = regex_field if regex_field else order_field
        if excel_col and actual_field:
            field_mapping[excel_col] = actual_field
        idx += 1

    # 确保上传目录存在
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # 保存文件
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    saved_name = f"{category_id}_{timestamp}_{filename}"
    filepath = os.path.join(UPLOAD_FOLDER, saved_name)
    file.save(filepath)

    # 检查是否已存在该类别的模板
    existing = ExcelTemplate.query.filter_by(category_id=category_id).first()
    if existing:
        # 删除旧文件
        if os.path.exists(existing.filepath):
            os.remove(existing.filepath)
        existing.filename = filename
        existing.filepath = filepath
        existing.field_mapping = json.dumps(field_mapping, ensure_ascii=False)
        existing.create_time = _now_bj()
        flash(f'模板已更新！', 'success')
    else:
        template = ExcelTemplate(category_id=category_id, filename=filename, filepath=filepath,
                                field_mapping=json.dumps(field_mapping, ensure_ascii=False))
        db.session.add(template)
        flash(f'模板上传成功！', 'success')

    db.session.commit()
    return redirect(url_for('templates.admin_templates'))


@bp.route('/admin/template/download/<int:template_id>')
@role_required('admin')
def download_template(template_id):
    """下载模板"""
    template = ExcelTemplate.query.get_or_404(template_id)
    if not os.path.exists(template.filepath):
        flash('文件不存在！', 'danger')
        return redirect(url_for('templates.admin_templates'))
    return send_file(template.filepath, as_attachment=True, download_name=template.filename)


@bp.route('/admin/template/delete/<int:template_id>', methods=['POST'])
@role_required('admin')
def delete_template(template_id):
    """删除模板"""
    template = ExcelTemplate.query.get_or_404(template_id)
    if os.path.exists(template.filepath):
        os.remove(template.filepath)
    db.session.delete(template)
    db.session.commit()
    flash('模板删除成功！', 'success')
    return redirect(url_for('templates.admin_templates'))


@bp.route('/admin/template/edit', methods=['POST'])
@role_required('admin')
def edit_template():
    """编辑导出模板（只更新字段映射，可选重新上传文件）"""
    template_id = request.form.get('template_id', type=int)
    template = ExcelTemplate.query.get_or_404(template_id)

    # 收集字段映射（支持正则表达式）
    field_mapping = {}
    idx = 0
    while True:
        excel_col = request.form.get(f'excel_col_{idx}', '').strip()
        order_field = request.form.get(f'order_field_{idx}', '').strip()
        regex_field = request.form.get(f'regex_field_{idx}', '').strip()
        if not excel_col and not order_field and not regex_field:
            break
        actual_field = regex_field if regex_field else order_field
        if excel_col and actual_field:
            field_mapping[excel_col] = actual_field
        idx += 1

    if not field_mapping:
        flash('至少需要配置一个字段映射！', 'danger')
        return redirect(url_for('templates.admin_templates'))

    # 处理可选的文件重新上传
    file = request.files.get('file')
    if file and file.filename:
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        new_filename = f"export_{template.category_id}_{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, new_filename)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file.save(filepath)
        # 删除旧文件
        if os.path.exists(template.filepath):
            os.remove(template.filepath)
        template.filepath = filepath
        template.filename = filename

    template.field_mapping = json.dumps(field_mapping, ensure_ascii=False)
    db.session.commit()
    flash(f'模板 "{template.category.name}" 更新成功！', 'success')
    return redirect(url_for('templates.admin_templates'))
