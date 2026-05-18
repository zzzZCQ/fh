# -*- coding: utf-8 -*-
"""认证相关路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, login_required, logout_user, current_user

from models import db, User, Notification, Group
from helpers import get_unread_count, notify_users

bp = Blueprint('auth', __name__)


# ============ 基础路由 ============
@bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('orders.dashboard'))
        elif current_user.role == 'shipper':
            return redirect(url_for('orders.dashboard'))
        else:
            return redirect(url_for('orders.dashboard'))
    return redirect(url_for('auth.login'))


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if not user.is_active:
                flash('该账号已被停用，请联系管理员！', 'danger')
                return redirect(url_for('auth.login'))
            login_user(user)
            return redirect(url_for('auth.index'))
        else:
            flash('用户名或密码错误！', 'danger')
    return render_template('login.html', unread_count=0)


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已成功登出！', 'success')
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        name = request.form.get('name')
        password = request.form.get('password')
        role = request.form.get('role')
        group_id = request.form.get('group_id', type=int)

        # 管理员可以创建管理员账号
        valid_roles = ['salesman', 'shipper']
        if current_user.is_authenticated and current_user.has_role('admin'):
            valid_roles = ['salesman', 'shipper', 'admin']

        if role not in valid_roles:
            flash('只能注册业务员或发货员账号！', 'danger')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(username=username).first():
            flash('用户名已存在！', 'danger')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(name=name).first():
            flash('该姓名已被注册，不允许同名注册！', 'danger')
            return redirect(url_for('auth.register'))
        if not all([username, name, password]):
            flash('请填写所有必填字段！', 'danger')
            return redirect(url_for('auth.register'))
        if not group_id:
            flash('请选择所属组别！', 'danger')
            return redirect(url_for('auth.register'))

        user = User(username=username, name=name, roles=role, group_id=group_id)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        if current_user.is_authenticated:
            flash(f'用户 {name} 创建成功！', 'success')
            return redirect(url_for('admin_users.admin_users'))

        flash('注册成功！请使用新账号登录。', 'success')
        return redirect(url_for('auth.login'))

    # 组别过滤：管理员只看本级及下级，未登录看所有
    if current_user.is_authenticated and current_user.has_role('admin') and current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        groups = Group.query.filter(Group.id.in_(managed_group_ids), Group.is_active==True).order_by(Group.level.asc(), Group.create_time.asc()).all()
    else:
        groups = Group.query.filter_by(is_active=True).order_by(Group.level.asc(), Group.create_time.asc()).all()
    return render_template('register.html', groups=groups, unread_count=0)


@bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')

        if not current_user.check_password(old_password):
            flash('旧密码错误！', 'danger')
            return redirect(url_for('auth.change_password'))
        if len(new_password) < 6:
            flash('新密码长度不能少于6位！', 'danger')
            return redirect(url_for('auth.change_password'))

        current_user.set_password(new_password)
        db.session.commit()
        flash('密码修改成功！', 'success')
        return redirect(url_for('auth.index'))

    return render_template('change_password.html', unread_count=get_unread_count(current_user.id))


@bp.route('/notifications')
@login_required
def notifications():
    """通知列表页面"""
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.create_time.desc()).limit(100).all()
    total = Notification.query.filter_by(user_id=current_user.id).count()
    return render_template('notifications.html', unread_count=get_unread_count(current_user.id), total=total, notifications=notifications)


@bp.route('/notification/<int:notification_id>')
@login_required
def notification_detail(notification_id):
    """通知详情页面"""
    notification = Notification.query.get_or_404(notification_id)
    # 确认是当前用户的通知
    if notification.user_id != current_user.id:
        flash('无权查看该通知！', 'danger')
        return redirect(url_for('auth.notifications'))
    # 标记为已读
    notification.is_read = True
    db.session.commit()
    return render_template('notification_detail.html', notification=notification, unread_count=get_unread_count(current_user.id))
