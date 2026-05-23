# -*- coding: utf-8 -*-
"""广播通知管理API"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime
import os
from werkzeug.utils import secure_filename

from models import db, BroadcastNotification, NotificationReceipt, User, Group
from notification_generator import create_notification_image
import socket_events

bp = Blueprint('broadcast', __name__, url_prefix='/api/broadcast')

# 允许上传的图片格式
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

def allowed_file(filename):
    """检查文件格式是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route('/upload-image', methods=['POST'])
@login_required
def upload_image():
    """上传通知图片"""
    if not check_broadcast_permission():
        return jsonify({'success': False, 'error': '没有权限'}), 403
    
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': '没有上传文件'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': '没有选择文件'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': '不支持的文件格式'}), 400
    
    try:
        # 创建上传目录
        upload_dir = os.path.join('static', 'notifications', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        # 生成唯一文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = secure_filename(file.filename)
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(upload_dir, unique_filename)
        
        # 保存文件
        file.save(filepath)
        
        # 返回相对路径
        relative_path = f"/{upload_dir.replace(os.path.sep, '/')}/{unique_filename}"
        
        return jsonify({
            'success': True,
            'image_url': relative_path
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/auth', methods=['POST'])
def authenticate():
    """客户端认证接口"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'error': '用户名和密码不能为空'}), 400
    
    # 查找用户
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'error': '用户名或密码错误'}), 401
    
    if not user.is_active:
        return jsonify({'success': False, 'error': '用户已被禁用'}), 403
    
    # 生成token（简化版：使用固定格式）
    token = f"user_{user.id}_token"
    
    return jsonify({
        'success': True,
        'user_id': user.id,
        'username': user.name,
        'token': token
    })


def check_broadcast_permission():
    """检查是否有广播权限"""
    return current_user.has_role('admin') and current_user.can_broadcast


def get_visible_groups(user):
    """获取用户可管理的部门ID列表（自己部门+所有子部门）"""
    # 超级管理员可以看到所有部门
    if user.username == 'admin':
        return [g.id for g in Group.query.filter_by(is_active=True).all()]
    
    # 普通管理员：只能看到自己部门及子部门
    if user.group:
        group_ids = [user.group.id]
        # 获取所有子部门ID
        if user.group.children:
            def add_children(group):
                for child in group.children:
                    if child.is_active:
                        group_ids.append(child.id)
                        add_children(child)
            add_children(user.group)
        return group_ids
    
    return []


@bp.route('/users', methods=['GET'])
def get_users():
    """获取用户列表（支持分页、组别筛选和搜索）- 只显示自己部门及子部门的用户"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    group_id = request.args.get('group_id', 'all')
    search = request.args.get('search', '')
    
    query = User.query.filter_by(is_active=True)
    
    # 获取当前用户可管理的部门ID列表（自己部门+所有子部门）
    visible_group_ids = get_visible_groups(current_user)
    
    # 只显示自己部门及子部门的用户
    query = query.filter(User.group_id.in_(visible_group_ids))
    
    if group_id != 'all' and group_id:
        query = query.filter(User.group_id == int(group_id))
    
    if search:
        query = query.filter(
            (User.name.ilike(f'%{search}%')) | 
            (User.username.ilike(f'%{search}%'))
        )
    
    users = query.order_by(User.name).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'success': True,
        'items': [{
            'id': u.id,
            'username': u.username,
            'name': u.name,
            'group_id': u.group_id,
            'group_name': u.group.name if u.group else ''
        } for u in users.items],
        'total': users.total,
        'page': users.page,
        'pages': users.pages,
        'has_next': users.has_next,
        'has_prev': users.has_prev
    })


@bp.route('/departments', methods=['GET'])
def get_departments():
    """获取部门列表（按层级排序）"""
    departments = Group.query.filter_by(is_active=True).order_by(Group.level.asc(), Group.id.asc()).all()
    return jsonify({
        'success': True,
        'departments': [{
            'id': d.id,
            'name': d.name,
            'level': d.level,
            'parent_id': d.parent_id
        } for d in departments]
    })


def get_target_users(target_type, target_ids, current_user=None):
    """获取目标用户列表（考虑权限限制）"""
    # 获取当前用户可管理的部门ID列表
    visible_group_ids = get_visible_groups(current_user) if current_user else []
    
    if target_type == 'all':
        # 全员发送：只发送给自己部门及子部门的用户
        query = User.query.filter_by(is_active=True)
        query = query.filter(User.group_id.in_(visible_group_ids))
        return [u.id for u in query.all()]
    
    elif target_type == 'department':
        if not target_ids:
            return []
        dept_ids = [int(x) for x in target_ids.split(',')]
        # 部门发送：只发送给该部门中自己权限范围内的用户
        # 先过滤出用户有权限的部门
        valid_dept_ids = [d for d in dept_ids if d in visible_group_ids]
        if not valid_dept_ids:
            return []
        query = User.query.filter(User.group_id.in_(valid_dept_ids), User.is_active==True)
        return [u.id for u in query.all()]
    
    elif target_type == 'role':
        if not target_ids:
            return []
        roles = target_ids.split(',')
        users = []
        query = User.query.filter_by(is_active=True).filter(User.group_id.in_(visible_group_ids))
        for user in query.all():
            if any(role in user.get_roles() for role in roles):
                users.append(user.id)
        return users
    
    elif target_type == 'user':
        if not target_ids:
            return []
        user_ids = [int(x) for x in target_ids.split(',')]
        # 用户发送：只发送给权限范围内的用户
        query = User.query.filter(User.id.in_(user_ids), User.is_active==True)
        query = query.filter(User.group_id.in_(visible_group_ids))
        return [u.id for u in query.all()]
    
    return []


@bp.route('/notifications', methods=['POST'])
@login_required
def create_notification():
    """创建广播通知"""
    if not check_broadcast_permission():
        return jsonify({'success': False, 'error': '没有广播权限'}), 403
    
    data = request.get_json()
    
    title = data.get('title', '')
    content = data.get('content')
    priority = data.get('priority', 'normal')
    target_type = data.get('target_type', 'all')
    target_ids = data.get('target_ids', '')
    scheduled_time = data.get('scheduled_time')
    user_image_url = data.get('user_image_url')  # 用户上传的图片
    
    notification = BroadcastNotification(
        title=title,
        content=content,
        priority=priority,
        target_type=target_type,
        target_ids=target_ids,
        sender_id=current_user.id,
        status='draft'
    )
    
    if user_image_url:
        notification.user_image_path = user_image_url
    
    if scheduled_time:
        notification.scheduled_time = datetime.fromisoformat(scheduled_time)
        notification.status = 'scheduled'
    
    db.session.add(notification)
    db.session.commit()
    
    sender_name = current_user.name
    image_path, _ = create_notification_image(title, content, priority, sender_name, notification.id, user_image_url)
    
    notification.image_path = image_path
    db.session.commit()
    
    return jsonify({
        'success': True,
        'notification': {
            'id': notification.id,
            'title': notification.title,
            'content': notification.content,
            'priority': notification.priority,
            'image_path': notification.image_path,
            'user_image_path': notification.user_image_path,
            'status': notification.status,
            'create_time': notification.create_time.isoformat()
        }
    })


@bp.route('/notifications/<int:notification_id>/send', methods=['POST'])
@login_required
def send_notification(notification_id):
    """发送广播通知"""
    if not check_broadcast_permission():
        return jsonify({'success': False, 'error': '没有广播权限'}), 403
    
    notification = BroadcastNotification.query.get_or_404(notification_id)
    
    # 数据范围检查：非超级管理员只能发送自己的通知
    if current_user.username != 'admin' and notification.sender_id != current_user.id:
        return jsonify({'success': False, 'error': '没有权限发送此通知'}), 403
    
    if notification.status == 'sent':
        return jsonify({'success': False, 'error': '通知已经发送'}), 400
    
    target_user_ids = get_target_users(notification.target_type, notification.target_ids, current_user)
    
    if not target_user_ids:
        return jsonify({'success': False, 'error': '没有找到目标用户'}), 400
    
    for user_id in target_user_ids:
        receipt = NotificationReceipt(
            notification_id=notification.id,
            user_id=user_id
        )
        db.session.add(receipt)
    
    notification.status = 'sent'
    notification.sent_time = datetime.now()
    db.session.commit()
    
    notification_data = {
        'id': notification.id,
        'title': notification.title,
        'content': notification.content,
        'image_url': notification.image_path,
        'user_image_url': notification.user_image_path,
        'priority': notification.priority,
        'timestamp': notification.sent_time.isoformat()
    }
    
    print(f"准备推送通知 - target_type: {notification.target_type}, target_user_ids: {target_user_ids}")
    print(f"当前在线用户列表: {socket_events.connected_users}")
    
    if notification.target_type == 'all':
        pushed_count = socket_events.push_notification_to_all(notification_data)
    else:
        pushed_count = socket_events.push_notification_to_users(target_user_ids, notification_data)
    
    print(f"推送完成 - 成功推送到 {pushed_count} 个在线用户")
    
    return jsonify({
        'success': True,
        'message': f'通知已发送',
        'total_users': len(target_user_ids),
        'online_users': pushed_count,
        'notification': {
            'id': notification.id,
            'status': notification.status,
            'sent_time': notification.sent_time.isoformat()
        }
    })


@bp.route('/notifications', methods=['GET'])
@login_required
def list_notifications():
    """获取广播通知列表"""
    if not check_broadcast_permission():
        return jsonify({'success': False, 'error': '没有广播权限'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    query = BroadcastNotification.query
    
    # 数据范围控制
    if current_user.username != 'admin':
        # 非超级管理员只能看到自己发送的通知
        query = query.filter(BroadcastNotification.sender_id == current_user.id)
    
    notifications = query.order_by(BroadcastNotification.create_time.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'items': [{
            'id': n.id,
            'title': n.title,
            'content': n.content,
            'priority': n.priority,
            'target_type': n.target_type,
            'status': n.status,
            'create_time': n.create_time.isoformat(),
            'sent_time': n.sent_time.isoformat() if n.sent_time else None,
            'sender_name': n.sender.name if n.sender else '',
            'user_image_path': n.user_image_path
        } for n in notifications.items],
        'total': notifications.total,
        'page': page,
        'pages': notifications.pages,
        'has_next': notifications.has_next,
        'has_prev': notifications.has_prev
    })


@bp.route('/notifications/<int:notification_id>', methods=['GET'])
@login_required
def get_notification(notification_id):
    """获取通知详情"""
    notification = BroadcastNotification.query.get_or_404(notification_id)
    
    # 数据范围检查
    if current_user.username != 'admin' and notification.sender_id != current_user.id:
        return jsonify({'error': '没有权限查看此通知'}), 403
    
    return jsonify({
        'id': notification.id,
        'title': notification.title,
        'content': notification.content,
        'priority': notification.priority,
        'target_type': notification.target_type,
        'target_ids': notification.target_ids,
        'image_path': notification.image_path,
        'user_image_path': notification.user_image_path,
        'status': notification.status,
        'create_time': notification.create_time.isoformat(),
        'sent_time': notification.sent_time.isoformat() if notification.sent_time else None,
        'sender_name': notification.sender.name if notification.sender else ''
    })


@bp.route('/notifications/<int:notification_id>', methods=['DELETE'])
@login_required
def delete_notification(notification_id):
    """删除通知"""
    if not check_broadcast_permission():
        return jsonify({'success': False, 'error': '没有权限'}), 403
    
    notification = BroadcastNotification.query.get_or_404(notification_id)
    
    # 数据范围检查：非超级管理员只能删除自己的通知
    if current_user.username != 'admin' and notification.sender_id != current_user.id:
        return jsonify({'success': False, 'error': '没有权限删除此通知'}), 403
    
    # 删除关联的确认记录
    NotificationReceipt.query.filter_by(notification_id=notification_id).delete()
    
    db.session.delete(notification)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '删除成功'
    })


@bp.route('/notifications/<int:notification_id>/resend', methods=['POST'])
@login_required
def resend_notification(notification_id):
    """重新发送草稿/已发送的通知"""
    if not check_broadcast_permission():
        return jsonify({'success': False, 'error': '没有权限'}), 403
    
    notification = BroadcastNotification.query.get_or_404(notification_id)
    
    # 数据范围检查：非超级管理员只能重发自己的通知
    if current_user.username != 'admin' and notification.sender_id != current_user.id:
        return jsonify({'success': False, 'error': '没有权限重发此通知'}), 403
    
    # 获取目标用户
    target_user_ids = get_target_users(notification.target_type, notification.target_ids, current_user)
    
    if not target_user_ids:
        return jsonify({'success': False, 'error': '没有找到目标用户'}), 400
    
    # 删除旧的确认记录
    NotificationReceipt.query.filter_by(notification_id=notification_id).delete()
    
    # 创建新的确认记录
    for user_id in target_user_ids:
        receipt = NotificationReceipt(
            notification_id=notification.id,
            user_id=user_id
        )
        db.session.add(receipt)
    
    # 更新状态
    notification.status = 'sent'
    notification.sent_time = datetime.now()
    db.session.commit()
    
    # 推送通知
    notification_data = {
        'id': notification.id,
        'title': notification.title,
        'content': notification.content,
        'image_url': notification.image_path,
        'user_image_url': notification.user_image_path,
        'priority': notification.priority,
        'timestamp': notification.sent_time.isoformat()
    }
    
    if notification.target_type == 'all':
        pushed_count = socket_events.push_notification_to_all(notification_data)
    else:
        pushed_count = socket_events.push_notification_to_users(target_user_ids, notification_data)
    
    return jsonify({
        'success': True,
        'message': '重新发送成功',
        'total_users': len(target_user_ids),
        'online_users': pushed_count
    })


@bp.route('/notifications/<int:notification_id>/receipts', methods=['GET'])
@login_required
def get_receipts(notification_id):
    """获取通知确认状态"""
    if not check_broadcast_permission():
        return jsonify({'success': False, 'error': '没有广播权限'}), 403
    
    notification = BroadcastNotification.query.get_or_404(notification_id)
    
    # 数据范围检查：非超级管理员只能查看自己的通知确认状态
    if current_user.username != 'admin' and notification.sender_id != current_user.id:
        return jsonify({'success': False, 'error': '没有权限查看此通知'}), 403
    
    receipts = NotificationReceipt.query.filter_by(notification_id=notification_id).all()
    
    total = len(receipts)
    confirmed = sum(1 for r in receipts if r.is_confirmed)
    
    return jsonify({
        'notification_id': notification_id,
        'total_receivers': total,
        'confirmed_count': confirmed,
        'unconfirmed_count': total - confirmed,
        'confirmation_rate': round(confirmed / total * 100, 1) if total > 0 else 0,
        'receipts': [{
            'user_id': r.user_id,
            'user_name': r.user.name if r.user else '未知',
            'received_time': r.received_time.isoformat() if r.received_time else None,
            'confirmed_time': r.confirmed_time.isoformat() if r.confirmed_time else None,
            'is_confirmed': r.is_confirmed
        } for r in receipts]
    })


@bp.route('/notifications/<int:notification_id>/remind', methods=['POST'])
@login_required
def remind_notification(notification_id):
    """催读提醒"""
    if not check_broadcast_permission():
        return jsonify({'success': False, 'error': '没有广播权限'}), 403
    
    notification = BroadcastNotification.query.get_or_404(notification_id)
    
    # 数据范围检查：非超级管理员只能催读自己的通知
    if current_user.username != 'admin' and notification.sender_id != current_user.id:
        return jsonify({'success': False, 'error': '没有权限催读此通知'}), 403
    
    unconfirmed_receipts = NotificationReceipt.query.filter_by(
        notification_id=notification_id,
        is_confirmed=False
    ).all()
    
    if not unconfirmed_receipts:
        return jsonify({'success': False, 'error': '所有用户都已确认'}), 400
    
    notification_data = {
        'id': notification.id,
        'title': notification.title,
        'content': notification.content,
        'image_url': notification.image_path,
        'priority': notification.priority,
        'timestamp': notification.sent_time.isoformat() if notification.sent_time else datetime.now().isoformat(),
        'reminder': True
    }
    
    unconfirmed_user_ids = [r.user_id for r in unconfirmed_receipts]
    pushed_count = socket_events.push_notification_to_users(unconfirmed_user_ids, notification_data)
    
    return jsonify({
        'success': True,
        'message': f'已向 {pushed_count} 名未确认用户发送提醒',
        'total_unconfirmed': len(unconfirmed_user_ids),
        'pushed_count': pushed_count
    })


@bp.route('/user/notifications', methods=['GET'])
def get_user_notifications():
    """客户端获取用户通知列表"""
    user_id = request.args.get('user_id', type=int)
    token = request.args.get('token')
    
    if not user_id or not token:
        return jsonify({'success': False, 'error': '缺少参数'}), 400
    
    expected_token = f"user_{user_id}_token"
    if token != expected_token:
        return jsonify({'success': False, 'error': '认证失败'}), 401
    
    receipts = NotificationReceipt.query.filter_by(user_id=user_id)\
        .order_by(NotificationReceipt.id.desc())\
        .limit(50).all()
    
    notifications = []
    for receipt in receipts:
        n = receipt.notification
        if not n:
            continue
        notifications.append({
            'id': n.id,
            'title': n.title,
            'content': n.content,
            'image_url': n.image_path,
            'priority': n.priority,
            'is_confirmed': receipt.is_confirmed,
            'confirmed_time': receipt.confirmed_time.isoformat() if receipt.confirmed_time else None,
            'received_time': receipt.received_time.isoformat() if receipt.received_time else None,
            'sent_time': n.sent_time.isoformat() if n.sent_time else None
        })
    
    return jsonify({
        'success': True,
        'notifications': notifications
    })


@bp.route('/user/confirm', methods=['POST'])
def confirm_notification():
    """客户端确认通知"""
    data = request.get_json()
    user_id = data.get('user_id')
    token = data.get('token')
    notification_id = data.get('notification_id')
    
    if not user_id or not token or not notification_id:
        return jsonify({'success': False, 'error': '缺少参数'}), 400
    
    expected_token = f"user_{user_id}_token"
    if token != expected_token:
        return jsonify({'success': False, 'error': '认证失败'}), 401
    
    receipt = NotificationReceipt.query.filter_by(
        notification_id=notification_id,
        user_id=user_id
    ).first()
    
    if not receipt:
        return jsonify({'success': False, 'error': '未找到通知记录'}), 404
    
    receipt.is_confirmed = True
    receipt.confirmed_time = datetime.now()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '确认成功'
    })


@bp.route('/admin/broadcast')
@login_required
def admin_broadcast():
    """广播管理页面"""
    if not check_broadcast_permission():
        from flask import abort
        abort(403)
    from flask import render_template
    from helpers import get_unread_count
    unread_count = get_unread_count(current_user.id)
    return render_template('admin_broadcast.html', unread_count=unread_count)
