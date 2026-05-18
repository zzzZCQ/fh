# -*- coding: utf-8 -*-
"""共享辅助函数和装饰器"""
import functools

from flask import redirect, url_for, flash
from flask_login import login_required, current_user

from models import db, Notification, Category, Gift


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
    return Category.query.filter_by(is_active=True).order_by(Category.sort_order.asc(), Category.id.asc()).all()


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
