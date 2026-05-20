# -*- coding: utf-8 -*-
"""WebSocket事件处理"""
from flask import request
from flask_socketio import emit, disconnect
from models import db, User, BroadcastNotification, NotificationReceipt
import time
import threading


connected_users = {}  # {user_id: {'sid': session_id, 'username': name}}
socketio_instance = None  # 全局保存 socketio 实例
message_queue = []  # 消息队列：(user_id, data)
queue_lock = threading.Lock()
queue_thread = None


def start_queue_worker():
    """启动消息队列处理线程"""
    global queue_thread
    if queue_thread and queue_thread.is_alive():
        return
    
    def worker():
        while True:
            time.sleep(0.1)
            with queue_lock:
                if message_queue:
                    user_id, data = message_queue.pop(0)
                    try:
                        if user_id in connected_users:
                            session_id = connected_users[user_id]['sid']
                            socketio_instance.emit('new_notification', data, room=session_id)
                    except Exception as e:
                        print(f"Queue send error: {e}")
    
    queue_thread = threading.Thread(target=worker, daemon=True)
    queue_thread.start()


def init_socketio(socketio):
    """初始化SocketIO事件"""
    global socketio_instance
    socketio_instance = socketio
    start_queue_worker()
    
    @socketio.on('connect')
    def handle_connect():
        """处理客户端连接"""
        try:
            user_id = request.args.get('user_id')
            token = request.args.get('token')
            
            if not user_id or not token:
                emit('error', {'message': 'Auth info missing'})
                disconnect()
                return
            
            user = User.query.get(int(user_id))
            if not user:
                emit('error', {'message': 'User not found'})
                disconnect()
                return
            
            expected_token = f"user_{user_id}_token"
            if token != expected_token:
                emit('error', {'message': 'Auth failed'})
                disconnect()
                return
            
            user_id_int = int(user_id)
            
            # 如果该用户已有连接，记录警告但允许新连接（自动处理）
            if user_id_int in connected_users:
                old_sid = connected_users[user_id_int]['sid']
                if old_sid != request.sid:
                    print(f"User {user.name} already connected, updating session...")
            
            # 更新连接信息
            connected_users[user_id_int] = {
                'sid': request.sid,
                'username': user.name
            }
            
            emit('connected', {
                'status': 'success',
                'user_id': user.id,
                'username': user.name
            })
            
            print(f"User {user.name} connected (ID: {user.id})")
            
        except Exception as e:
            print(f"Connection error: {str(e)}")
            try:
                emit('error', {'message': 'Connection failed'})
                disconnect()
            except:
                pass
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """处理客户端断开连接"""
        try:
            for user_id, data in list(connected_users.items()):
                if data['sid'] == request.sid:
                    del connected_users[user_id]
                    user = User.query.get(user_id)
                    print(f"User {user.name if user else user_id} disconnected")
                    break
        except Exception as e:
            print(f"Disconnect error: {str(e)}")
    
    @socketio.on('ping')
    def handle_ping():
        """处理心跳检测"""
        try:
            emit('pong', {'timestamp': time.time()})
        except:
            pass
    
    @socketio.on('mark_received')
    def handle_mark_received(data):
        """处理消息接收确认"""
        try:
            notification_id = data.get('notification_id')
            user_id = data.get('user_id')
            
            if not notification_id or not user_id:
                emit('error', {'message': 'Missing parameters'})
                return
            
            receipt = NotificationReceipt.query.filter_by(
                notification_id=notification_id,
                user_id=int(user_id)
            ).first()
            
            if not receipt:
                receipt = NotificationReceipt(
                    notification_id=notification_id,
                    user_id=int(user_id)
                )
                db.session.add(receipt)
                db.session.commit()
            
            emit('receipt_confirmed', {
                'notification_id': notification_id,
                'status': 'received'
            })
            
        except Exception as e:
            print(f"Mark received error: {str(e)}")
            try:
                emit('error', {'message': 'Mark failed'})
            except:
                pass
    
    @socketio.on('confirm_notification')
    def handle_confirm_notification(data):
        """处理通知确认"""
        try:
            notification_id = data.get('notification_id')
            user_id = data.get('user_id')
            
            if not notification_id or not user_id:
                emit('error', {'message': 'Missing parameters'})
                return
            
            receipt = NotificationReceipt.query.filter_by(
                notification_id=notification_id,
                user_id=int(user_id)
            ).first()
            
            if receipt:
                receipt.is_confirmed = True
                receipt.confirmed_time = db.func.now()
                db.session.commit()
                
                emit('confirm_success', {
                    'notification_id': notification_id,
                    'status': 'confirmed'
                })
            else:
                receipt = NotificationReceipt(
                    notification_id=notification_id,
                    user_id=int(user_id),
                    is_confirmed=True,
                    confirmed_time=db.func.now()
                )
                db.session.add(receipt)
                db.session.commit()
                
                emit('confirm_success', {
                    'notification_id': notification_id,
                    'status': 'confirmed'
                })
                
        except Exception as e:
            print(f"Confirm error: {str(e)}")
            try:
                emit('error', {'message': 'Confirm failed'})
            except:
                pass
    
    @socketio.on('get_unread')
    def handle_get_unread(data):
        """获取未读通知"""
        try:
            user_id = data.get('user_id')
            if not user_id:
                emit('error', {'message': 'Missing user_id'})
                return
            
            receipts = NotificationReceipt.query.filter_by(
                user_id=int(user_id),
                is_confirmed=False
            ).all()
            
            unread_notifications = []
            for receipt in receipts:
                notification = receipt.notification
                if notification and notification.status == 'sent':
                    unread_notifications.append({
                        'id': notification.id,
                        'title': notification.title,
                        'content': notification.content,
                        'image_url': notification.image_path,
                        'priority': notification.priority,
                        'timestamp': notification.sent_time.isoformat() if notification.sent_time else None
                    })
            
            emit('unread_list', {'notifications': unread_notifications})
            
        except Exception as e:
            print(f"Get unread error: {str(e)}")
            try:
                emit('error', {'message': 'Get unread failed'})
            except:
                pass


def push_notification_to_user(user_id, notification_data):
    """向指定用户推送通知"""
    try:
        if not socketio_instance:
            print("Error: socketio_instance not initialized!")
            return False
        
        if user_id in connected_users:
            user_data = connected_users[user_id]
            username = user_data['username']
            
            with queue_lock:
                message_queue.append((user_id, notification_data))
            
            print(f"Notification sent to user {user_id} ({username})")
            return True
        else:
            print(f"User {user_id} not online")
            return False
    except Exception as e:
        print(f"Push error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def push_notification_to_users(user_ids, notification_data):
    """向多个用户推送通知"""
    success_count = 0
    for user_id in user_ids:
        if push_notification_to_user(user_id, notification_data):
            success_count += 1
    return success_count


def push_notification_to_all(notification_data):
    """向所有在线用户推送通知"""
    success_count = 0
    for user_id in connected_users.keys():
        if push_notification_to_user(user_id, notification_data):
            success_count += 1
    return success_count
