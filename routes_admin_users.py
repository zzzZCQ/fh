# -*- coding: utf-8 -*-
"""用户管理路由"""
from flask import Blueprint, request, redirect, url_for, flash, render_template
from flask_login import current_user

from models import db, User, Notification, Group, Order
from helpers import role_required, get_unread_count

bp = Blueprint('admin_users', __name__)


# ============ 用户管理 ============
@bp.route('/admin/users')
@role_required('admin')
def admin_users():
    page = request.args.get('page', 1, type=int)
    keyword = request.args.get('keyword', '').strip()

    # 超级管理员看所有用户，其他管理员只看同级及下级组
    if current_user.username == 'admin':
        query = User.query
    elif current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        query = User.query.filter(User.group_id.in_(managed_group_ids))
    else:
        query = User.query.filter_by(group_id=None)

    # 关键字搜索（用户名或姓名）
    if keyword:
        query = query.filter(db.or_(User.username.contains(keyword), User.name.contains(keyword)))

    users = query.order_by(User.id.asc()).paginate(page=page, per_page=10)

    # 组别下拉框：超级管理员看所有，其他管理员只看本级及下级
    if current_user.username == 'admin':
        groups = Group.query.filter_by(is_active=True).order_by(Group.level.asc(), Group.create_time.asc()).all()
    elif current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        groups = Group.query.filter(Group.id.in_(managed_group_ids), Group.is_active==True).order_by(Group.level.asc(), Group.create_time.asc()).all()
    else:
        groups = []

    return render_template('admin_users.html', users=users, groups=groups, keyword=keyword,
                           unread_count=get_unread_count(current_user.id))


@bp.route('/admin/user/change_role/<int:user_id>', methods=['POST'])
@role_required('admin')
def change_user_role(user_id):
    user = User.query.get_or_404(user_id)

    # 非超级管理员只能修改同组及下级组的用户
    if current_user.username != 'admin' and current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        if user.group_id not in managed_group_ids:
            flash('只能修改同组及下级组的用户！', 'danger')
            return redirect(url_for('admin_users.admin_users'))

    # 获取选中的角色列表
    selected_roles = request.form.getlist('roles')
    valid_roles = ['salesman', 'shipper', 'admin', 'follow_up']
    roles = [r for r in selected_roles if r in valid_roles]

    if not roles:
        flash('至少选择一个角色！', 'danger')
        return redirect(url_for('admin_users.admin_users'))

    user.roles = ','.join(roles)
    db.session.commit()

    role_names = {"salesman": "业务员", "shipper": "发货员", "admin": "管理员", "follow_up": "对接员"}
    role_str = '、'.join([role_names.get(r, r) for r in roles])
    flash(f'用户 {user.name} 的角色已修改为：{role_str}！', 'success')
    return redirect(url_for('admin_users.admin_users'))


@bp.route('/admin/user/change_group/<int:user_id>', methods=['POST'])
@role_required('admin')
def change_user_group(user_id):
    """修改用户所属组别"""
    user = User.query.get_or_404(user_id)
    group_id = request.form.get('group_id', type=int)

    # 非超级管理员只能修改同组及下级组的用户
    if current_user.username != 'admin' and current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        if user.group_id not in managed_group_ids:
            flash('只能修改同组及下级组的用户！', 'danger')
            return redirect(url_for('admin_users.admin_users'))
        # 只能移到同组及下级组
        if group_id and group_id not in managed_group_ids:
            flash('只能将用户分配到同组及下级组！', 'danger')
            return redirect(url_for('admin_users.admin_users'))

    if group_id:
        group = Group.query.get(group_id)
        if group:
            user.group_id = group_id
            db.session.commit()
            flash(f'用户 {user.name} 的组别已修改为：{group.get_full_path()}！', 'success')
        else:
            flash('组别不存在！', 'danger')
    else:
        user.group_id = None
        db.session.commit()
        flash(f'用户 {user.name} 的组别已清空！', 'success')

    return redirect(url_for('admin_users.admin_users'))


@bp.route('/admin/user/toggle_dingtalk/<int:user_id>', methods=['POST'])
@role_required('admin')
def toggle_user_dingtalk(user_id):
    """切换用户导出时发送钉钉的权限"""
    user = User.query.get_or_404(user_id)
    # 非超级管理员只能操作同组及下级组的用户
    if current_user.username != 'admin' and current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        if user.group_id not in managed_group_ids:
            flash('只能操作同组及下级组的用户！', 'danger')
            return redirect(url_for('admin_users.admin_users'))
    user.can_dingtalk_export = not user.can_dingtalk_export
    status = '开启' if user.can_dingtalk_export else '关闭'
    db.session.commit()
    flash(f'用户 {user.name} 的钉钉导出权限已{status}！', 'success')
    return redirect(url_for('admin_users.admin_users'))


@bp.route('/admin/user/toggle_active/<int:user_id>', methods=['POST'])
@role_required('admin')
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    # 不允许停用自己
    if user.id == current_user.id:
        flash('不能停用自己的账号！', 'danger')
        return redirect(url_for('admin_users.admin_users'))
    # 非超级管理员只能操作同组及下级组的用户
    if current_user.username != 'admin' and current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        if user.group_id not in managed_group_ids:
            flash('只能操作同组及下级组的用户！', 'danger')
            return redirect(url_for('admin_users.admin_users'))
    user.is_active = not user.is_active
    status = '启用' if user.is_active else '停用'
    db.session.commit()
    flash(f'用户 {user.name} 已{status}！', 'success')
    return redirect(url_for('admin_users.admin_users'))


@bp.route('/admin/user/delete/<int:user_id>', methods=['POST'])
@role_required('admin')
def delete_user(user_id):
    """删除用户"""
    user = User.query.get_or_404(user_id)

    # 不能删除自己
    if user.id == current_user.id:
        flash('不能删除自己的账号！', 'danger')
        return redirect(url_for('admin_users.admin_users'))

    # 不能删除超级管理员admin
    if user.username == 'admin':
        flash('不能删除超级管理员账号！', 'danger')
        return redirect(url_for('admin_users.admin_users'))

    # 非超级管理员只能删除同级及下级组的用户
    if current_user.username != 'admin' and current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        if user.group_id not in managed_group_ids:
            flash('只能删除同级及下级组的用户！', 'danger')
            return redirect(url_for('admin_users.admin_users'))

    # 删除关联的订单通知等
    Notification.query.filter_by(user_id=user.id).delete()

    # 将该用户的订单转移（如果有订单的话，将salesman_id置空或转移给当前用户）
    Order.query.filter_by(salesman_id=user.id).update({'salesman_id': current_user.id})

    db.session.delete(user)
    db.session.commit()
    flash(f'用户 {user.name} 已删除！', 'success')
    return redirect(url_for('admin_users.admin_users'))


@bp.route('/admin/user/reset_password/<int:user_id>', methods=['POST'])
@role_required('admin')
def reset_user_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '').strip()
    if not new_password or len(new_password) < 6:
        flash('密码长度不能少于6位！', 'danger')
        return redirect(url_for('admin_users.admin_users'))
    user.set_password(new_password)
    db.session.commit()
    flash(f'用户 {user.name} 的密码已重置！', 'success')
    return redirect(url_for('admin_users.admin_users'))


@bp.route('/admin/user/add', methods=['POST'])
@role_required('admin')
def add_user():
    """新增用户"""
    username = request.form.get('username', '').strip()
    name = request.form.get('name', '').strip()
    password = request.form.get('password', '').strip()
    roles = request.form.getlist('roles')
    group_id = request.form.get('group_id', type=int)

    if not username or not name:
        flash('用户名和姓名不能为空！', 'danger')
        return redirect(url_for('admin_users.admin_users'))

    if not password or len(password) < 6:
        flash('密码长度不能少于6位！', 'danger')
        return redirect(url_for('admin_users.admin_users'))

    # 检查用户名是否已存在
    existing = User.query.filter_by(username=username).first()
    if existing:
        flash(f'用户名 "{username}" 已存在！', 'danger')
        return redirect(url_for('admin_users.admin_users'))

    # 验证角色
    valid_roles = ['salesman', 'shipper', 'admin', 'follow_up']
    user_roles = [r for r in roles if r in valid_roles]
    if not user_roles:
        user_roles = ['salesman']

    user = User(
        username=username,
        name=name,
        roles=','.join(user_roles),
        group_id=group_id if group_id else None,
        is_active=True
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    flash(f'用户 {name} 创建成功！', 'success')
    return redirect(url_for('admin_users.admin_users'))
