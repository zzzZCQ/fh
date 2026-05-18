# -*- coding: utf-8 -*-
"""通知API路由"""
from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from models import Notification
from helpers import get_unread_count

bp = Blueprint('notifications', __name__)


# ============ 通知API ============
@bp.route('/api/notifications')
@login_required
def api_notifications():
    """获取通知列表（JSON）"""
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.create_time.desc()).limit(20).all()
    return jsonify([{
        'id': n.id,
        'content': n.content,
        'time': n.create_time.strftime('%m-%d %H:%M'),
        'is_read': n.is_read
    } for n in notifications])


@bp.route('/api/notifications/unread_count')
@login_required
def api_unread_count():
    """获取未读通知数量"""
    return jsonify(get_unread_count(current_user.id))
