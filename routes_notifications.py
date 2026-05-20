# -*- coding: utf-8 -*-
"""通知API路由"""
from flask import Blueprint, jsonify, Response
from flask_login import login_required, current_user
import time

from models import db, Notification
from helpers import get_unread_count

bp = Blueprint('notifications', __name__)


# ============ SSE通知推送 ============
@bp.route('/api/notifications/stream')
@login_required
def notification_stream():
    """SSE实时推送未读通知数量"""
    from flask import current_app
    user_id = current_user.id
    app = current_app._get_current_object()
    
    # 在请求上下文中获取初始值
    initial_count = get_unread_count(user_id)
    
    def generate():
        last_count = initial_count
        try:
            yield f"data: {last_count}\n\n"
        except (GeneratorExit, Exception):
            return
        
        consecutive_errors = 0
        while True:
            try:
                time.sleep(10)
                # 在新的应用上下文中查询
                with app.app_context():
                    new_count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
                if new_count != last_count:
                    yield f"data: {new_count}\n\n"
                    last_count = new_count
                consecutive_errors = 0
            except GeneratorExit:
                return
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    return
                time.sleep(1)
    
    def event_stream():
        """包装生成器，处理连接断开"""
        try:
            for data in generate():
                yield data
        except (GeneratorExit, ConnectionResetError, BrokenPipeError):
            pass
    
    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


# ============ 通知API ============
@bp.route('/api/notifications')
@login_required
def api_notifications():
    """获取通知列表（JSON），默认返回10条"""
    page = 1
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.create_time.desc()).limit(10).all()
    total = Notification.query.filter_by(user_id=current_user.id).count()
    return jsonify({
        'items': [{
            'id': n.id,
            'content': n.content,
            'time': n.create_time.strftime('%m-%d %H:%M'),
            'is_read': n.is_read
        } for n in notifications],
        'total': total,
        'page': page,
        'has_more': total > 10
    })


@bp.route('/api/notifications/page/<int:page>')
@login_required
def api_notifications_page(page):
    """分页获取通知列表"""
    page_size = 10
    offset = (page - 1) * page_size
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.create_time.desc()).offset(offset).limit(page_size).all()
    total = Notification.query.filter_by(user_id=current_user.id).count()
    has_more = offset + page_size < total
    return jsonify({
        'items': [{
            'id': n.id,
            'content': n.content,
            'time': n.create_time.strftime('%m-%d %H:%M'),
            'is_read': n.is_read
        } for n in notifications],
        'total': total,
        'page': page,
        'has_more': has_more
    })


@bp.route('/api/notifications/unread_count')
@login_required
def api_unread_count():
    """获取未读通知数量"""
    return jsonify(get_unread_count(current_user.id))


@bp.route('/api/notifications/mark_all_read', methods=['POST'])
@login_required
def api_mark_all_read():
    """标记所有通知为已读"""
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/api/notifications/mark_read/<int:notification_id>', methods=['POST'])
@login_required
def api_mark_notification_read(notification_id):
    """标记单个通知为已读"""
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        return jsonify({'success': False, 'error': '无权操作该通知'})
    notification.is_read = True
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/api/notifications/check_urgent')
@login_required
def api_check_urgent():
    """检查是否有紧急未读通知"""
    urgent = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False,
        importance='urgent'
    ).order_by(Notification.create_time.desc()).first()
    
    if urgent:
        return jsonify({
            'has_urgent': True,
            'id': urgent.id,
            'content': urgent.content,
            'importance': urgent.importance
        })
    return jsonify({'has_urgent': False})
