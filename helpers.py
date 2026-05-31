# -*- coding: utf-8 -*-
"""共享辅助函数和装饰器"""
import functools

from flask import redirect, url_for, flash
from flask_login import login_required, current_user

from models import db, Notification, Category, Gift, User


# ============ 权限装饰器 ============
def role_required(*roles):
    def decorator(f):
        @functools.wraps(f)
        @login_required
        def wrapped(*args, **kwargs):
            # 检查用户是否有任意一个所需角色
            user_roles = current_user.get_roles()
            if not any(r in user_roles for r in roles):
                flash('您没有权限访问此页面！', 'danger')
                return redirect(url_for('auth.index'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ============ 公共辅助函数 ============
def get_unread_count(user_id):
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()


def get_active_categories():
    from models import _now_bj
    now = _now_bj()
    return Category.query.filter(
        Category.is_active == True,
        (Category.expire_time == None) | (Category.expire_time > now)
    ).order_by(Category.sort_order.asc(), Category.id.asc()).all()


def get_all_categories():
    """获取所有类别（包括已过期的），用于订单列表筛选"""
    return Category.query.filter_by(is_active=True).order_by(
        Category.sort_order.asc(), Category.id.asc()
    ).all()


def get_active_gifts(category_id=None):
    """获取启用的赠品列表，可按类别过滤"""
    query = Gift.query.filter_by(is_active=True)
    if category_id:
        # 获取该类别的赠品 + 通用赠品（category_id为空）
        query = query.filter((Gift.category_id == category_id) | (Gift.category_id == None))
    return query.order_by(Gift.sort_order.asc(), Gift.id.asc()).all()


def notify_users(user_ids, content, order_id=None):
    """批量发送通知"""
    for uid in user_ids:
        notification = Notification(user_id=uid, content=content, order_id=order_id)
        db.session.add(notification)
    db.session.commit()


def get_nearest_admin_upward(user):
    """获取用户向上层级最近的管理员
    
    查找逻辑：
    1. 首先检查用户所在组是否有管理员
    2. 如果没有，向上查找父组
    3. 继续向上直到找到管理员
    4. 如果所有层级都没有，返回None
    """
    if not user or not user.group_id:
        return None
    
    current_group = user.group
    if not current_group:
        return None
    
    while current_group:
        from models import User
        admin = User.query.filter(
            User.roles.like('%admin%'),
            User.group_id == current_group.id,
            User.is_active == True
        ).first()
        
        if admin:
            return admin
        
        current_group = current_group.parent
    
    return None


def notify_user_upward_admin(user, content, order_id=None):
    """通知用户向上层级最近的管理员
    
    如果没有找到上级管理员，不发送通知
    """
    admin = get_nearest_admin_upward(user)
    if admin:
        notification = Notification(user_id=admin.id, content=content, order_id=order_id)
        db.session.add(notification)
        db.session.commit()


def broadcast_notification(sender, content, image_url=None, user_ids=None, importance='normal'):
    """广播通知给用户（除发送者外）
    
    超级管理员发送给所有用户或指定用户；
    普通用户只发送给自己的组及其下级组的用户；
    
    Args:
        sender: 发送者用户对象
        content: 通知内容（支持HTML）
        image_url: 图片URL（可选）
        user_ids: 指定的用户ID列表，可选（None表示发送给所有人）
        importance: 重要性级别，'normal'(一般)、'important'(重要)、'urgent'(紧急)
    """
    from models import User
    
    if image_url:
        full_content = f'{content}<br><img src="{image_url}" style="max-width:100%; max-height:300px; margin-top:8px; border-radius:4px;">'
    else:
        full_content = content
    
    users = []
    
    if user_ids:
        users = User.query.filter(User.id.in_(user_ids), User.is_active == True).all()
    elif sender.username == 'admin':
        users = User.query.filter(User.is_active == True).all()
    else:
        target_group_ids = sender.get_managed_group_ids()
        if target_group_ids:
            users = User.query.filter(
                User.is_active == True,
                User.group_id.in_(target_group_ids)
            ).all()
    
    for user in users:
        if user.id != sender.id:
            notification = Notification(user_id=user.id, content=full_content, importance=importance)
            db.session.add(notification)
    db.session.commit()
