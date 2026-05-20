# Windows桌面通知系统实施计划

> **目标：** 实现企业增强版通知系统，包含后端广播管理、WebSocket推送、Windows客户端展示
>
> **架构概述：** Flask后端提供WebSocket服务推送通知图片，Windows客户端以exe形式运行在员工电脑，右上角展示通知，支持声音提醒和已读确认
>
> **技术栈：** Python Flask + Flask-SocketIO + Pillow（后端），PyQt5 + PyInstaller（客户端）

---

## 📁 文件结构规划

### 后端文件（d:\fh）
```
d:\fh\
├── models.py                          # 扩展：添加BroadcastNotification、NotificationReceipt模型
├── routes_broadcast.py                 # 新增：广播管理API路由
├── socket_events.py                    # 新增：WebSocket事件处理
├── notification_generator.py           # 新增：图片生成器
├── app.py                              # 修改：集成WebSocket
└── static/
    └── notifications/                  # 新增：生成的图片存储目录
```

### 客户端文件（d:\fh\client）
```
d:\fh\client\
├── main.py                             # 客户端入口
├── notification_window.py              # 通知窗口（右上角弹出）
├── tray_icon.py                        # 系统托盘
├── settings.py                         # 设置管理
├── websocket_client.py                 # WebSocket客户端
├── sounds/                             # 声音文件目录
│   ├── normal.wav
│   ├── important.wav
│   ├── urgent.wav
│   └── confirm.wav
├── requirements.txt                    # 依赖列表
└── build.bat                           # 打包脚本
```

---

## 📋 任务分解

## 阶段1：后端核心（第1-2天）

### 任务1：数据库模型扩展

**文件：**
- 修改：`d:\fh\models.py`（在文件末尾添加新模型）

- [ ] **步骤1：在models.py末尾添加BroadcastNotification模型**

打开 `d:\fh\models.py`，在文件末尾（最后一个类定义之后）添加：

```python
class BroadcastNotification(db.Model):
    """广播通知模型"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))  # 通知标题
    content = db.Column(db.Text, nullable=False)  # 通知内容
    image_path = db.Column(db.String(500))  # 生成的图片相对路径
    priority = db.Column(db.String(20), default='normal')  # normal/important/urgent
    target_type = db.Column(db.String(20))  # all/department/role/user
    target_ids = db.Column(db.Text)  # 目标ID列表，逗号分隔
    scheduled_time = db.Column(db.DateTime)  # 定时发送时间
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='draft')  # draft/scheduled/sent/cancelled
    create_time = db.Column(db.DateTime, default=_now_bj)
    sent_time = db.Column(db.DateTime)  # 实际发送时间

    sender = db.relationship('User', backref=db.backref('sent_notifications', lazy=True))


class NotificationReceipt(db.Model):
    """通知确认记录模型"""
    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer, db.ForeignKey('broadcast_notification.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    received_time = db.Column(db.DateTime)  # 客户端收到时间
    confirmed_time = db.Column(db.DateTime)  # 确认时间
    is_confirmed = db.Column(db.Boolean, default=False)

    notification = db.relationship('BroadcastNotification', 
                                   backref=db.backref('receipts', lazy=True))
    user = db.relationship('User', backref=db.backref('notification_receipts', lazy=True))
```

- [ ] **步骤2：验证模型创建**

运行命令验证模型是否正确：
```bash
cd d:\fh
python -c "from models import BroadcastNotification, NotificationReceipt; print('模型导入成功')"
```

预期输出：`模型导入成功`

- [ ] **步骤3：生成数据库迁移**

```bash
cd d:\fh
python -c "
from models import db
from app import app
with app.app_context():
    db.create_all()
    print('数据库表创建成功')
"
```

预期输出：`数据库表创建成功`

- [ ] **步骤4：提交代码**

```bash
cd d:\fh
git add models.py
git commit -m "feat: 添加BroadcastNotification和NotificationReceipt模型"
```

---

### 任务2：图片生成器实现

**文件：**
- 创建：`d:\fh\notification_generator.py`

- [ ] **步骤1：创建图片生成器模块**

创建文件 `d:\fh\notification_generator.py`：

```python
# -*- coding: utf-8 -*-
"""通知图片生成器"""
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from flask import current_app


class NotificationImageGenerator:
    """通知图片生成器类"""
    
    # 颜色配置
    COLORS = {
        'normal': {
            'header': (52, 152, 219),      # 蓝色 RGB
            'header_text': (255, 255, 255),
            'body_bg': (255, 255, 255),
            'title': (44, 62, 80),
            'content': (52, 73, 94),
            'footer': (236, 240, 241),
            'border': (52, 152, 219)
        },
        'important': {
            'header': (243, 156, 18),        # 黄色 RGB
            'header_text': (255, 255, 255),
            'body_bg': (255, 254, 240),
            'title': (44, 62, 80),
            'content': (52, 73, 94),
            'footer': (254, 249, 231),
            'border': (243, 156, 18)
        },
        'urgent': {
            'header': (231, 76, 60),         # 红色 RGB
            'header_text': (255, 255, 255),
            'body_bg': (255, 245, 245),
            'title': (192, 57, 43),
            'content': (52, 73, 94),
            'footer': (253, 234, 234),
            'border': (231, 76, 60)
        }
    }
    
    def __init__(self, width=600):
        self.width = width
        self.padding = 30
        self.header_height = 60
        self.footer_height = 50
        
    def get_font(self, size, bold=False):
        """获取字体"""
        try:
            if bold:
                return ImageFont.truetype("msyhbd.ttc", size)  # 微软雅黑粗体
            return ImageFont.truetype("msyh.ttc", size)
        except:
            try:
                if bold:
                    return ImageFont.truetype("simhei.ttf", size)  # 黑体
                return ImageFont.truetype("simsun.ttc", size)  # 宋体
            except:
                return ImageFont.load_default()
    
    def wrap_text(self, text, font, max_width):
        """文字换行"""
        lines = []
        words = text.split('\n')
        for word in words:
            if not word:
                lines.append('')
                continue
            words_list = word.split()
            current_line = ''
            for w in words_list:
                test_line = current_line + ' ' + w if current_line else w
                bbox = font.getbbox(test_line)
                if bbox[2] <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = w
            if current_line:
                lines.append(current_line)
        return lines
    
    def generate(self, title, content, priority='normal', sender_name='', company_name='公司通知'):
        """生成通知图片"""
        colors = self.COLORS.get(priority, self.COLORS['normal'])
        
        # 计算内容高度
        title_font = self.get_font(28, bold=True)
        content_font = self.get_font(18, bold=False)
        footer_font = self.get_font(14, bold=False)
        
        content_width = self.width - 2 * self.padding
        title_lines = self.wrap_text(title, title_font, content_width)
        content_lines = self.wrap_text(content, content_font, content_width)
        
        line_height = 30
        title_height = len(title_lines) * 40
        content_height = len(content_lines) * line_height
        body_padding = 40
        
        total_height = self.header_height + title_height + body_padding + content_height + body_padding + self.footer_height
        
        # 创建图片
        img = Image.new('RGB', (self.width, total_height), colors['body_bg'])
        draw = ImageDraw.Draw(img)
        
        # 绘制顶部颜色条
        draw.rectangle([(0, 0), (self.width, self.header_height)], fill=colors['header'])
        
        # 绘制标题
        y = self.header_height + 15
        for line in title_lines:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            text_width = bbox[2] - bbox[0]
            x = (self.width - text_width) // 2
            draw.text((x, y), line, font=title_font, fill=colors['title'])
            y += 40
        
        # 绘制分隔线
        y += 10
        draw.line([(self.padding, y), (self.width - self.padding, y)], fill=colors['border'], width=2)
        y += 20
        
        # 绘制内容
        for line in content_lines:
            draw.text((self.padding, y), line, font=content_font, fill=colors['content'])
            y += line_height
        
        # 绘制底部
        y = total_height - self.footer_height + 15
        footer_text = f"{company_name}"
        if sender_name:
            footer_text += f"  |  发布人：{sender_name}"
        footer_text += f"  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        bbox = draw.textbbox((0, 0), footer_text, font=footer_font)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) // 2
        draw.text((x, y), footer_text, font=footer_font, fill=(128, 128, 128))
        
        # 绘制边框
        draw.rectangle([(0, 0), (self.width - 1, total_height - 1)], outline=colors['border'], width=3)
        
        return img
    
    def save(self, img, notification_id):
        """保存图片"""
        save_dir = os.path.join(os.path.dirname(__file__), 'static', 'notifications')
        os.makedirs(save_dir, exist_ok=True)
        
        filename = f"notification_{notification_id}.png"
        filepath = os.path.join(save_dir, filename)
        img.save(filepath, 'PNG', quality=95)
        
        return f"/static/notifications/{filename}"


def create_notification_image(title, content, priority='normal', sender_name='', notification_id=None):
    """创建通知图片的便捷函数"""
    if notification_id is None:
        import time
        notification_id = int(time.time() * 1000)
    
    generator = NotificationImageGenerator()
    img = generator.generate(title, content, priority, sender_name)
    image_path = generator.save(img, notification_id)
    
    return image_path, notification_id
```

- [ ] **步骤2：创建图片存储目录**

```bash
cd d:\fh
mkdir -p static\notifications
echo. > static\notifications\.gitkeep
```

- [ ] **步骤3：测试图片生成器**

创建测试脚本 `test_generator.py`：

```python
# -*- coding: utf-8 -*-
from notification_generator import create_notification_image

# 测试生成图片
title = "重要会议通知"
content = "各位同事：\n请于明天下午2点在会议室A召开部门月度会议，届时将讨论本季度工作总结及下季度计划，请准时参加。\n\n如有特殊情况无法参加，请提前向部门经理请假。"
priority = "important"
sender_name = "张经理"

image_path, notif_id = create_notification_image(title, content, priority, sender_name)
print(f"图片生成成功！")
print(f"通知ID: {notif_id}")
print(f"图片路径: {image_path}")
```

运行测试：
```bash
cd d:\fh
python test_generator.py
```

预期输出：
```
图片生成成功！
通知ID: XXXXXXX
图片路径: /static/notifications/notification_XXXXXXX.png
```

验证：检查 `d:\fh\static\notifications\` 目录下是否生成了PNG文件

- [ ] **步骤4：提交代码**

```bash
cd d:\fh
git add notification_generator.py static/notifications/.gitkeep
git commit -m "feat: 添加通知图片生成器"
```

---

### 任务3：WebSocket事件处理

**文件：**
- 创建：`d:\fh\socket_events.py`

- [ ] **步骤1：创建WebSocket事件处理模块**

创建文件 `d:\fh\socket_events.py`：

```python
# -*- coding: utf-8 -*-
"""WebSocket事件处理"""
from flask import request
from flask_socketio import emit, disconnect
from app import socketio
from models import db, User, BroadcastNotification, NotificationReceipt
from flask_login import current_user
import time


# 用户连接映射表
connected_users = {}  # {user_id: session_id}


@socketio.on('connect')
def handle_connect():
    """处理客户端连接"""
    try:
        # 从连接中获取用户ID（通过查询参数）
        user_id = request.args.get('user_id')
        token = request.args.get('token')
        
        if not user_id or not token:
            emit('error', {'message': '认证信息缺失'})
            disconnect()
            return
        
        # 验证用户身份
        user = User.query.get(int(user_id))
        if not user:
            emit('error', {'message': '用户不存在'})
            disconnect()
            return
        
        # 验证token（简化版：使用user_id + 时间戳校验）
        expected_token = f"user_{user_id}_token"  # 实际应使用JWT
        if token != expected_token:
            emit('error', {'message': '认证失败'})
            disconnect()
            return
        
        # 保存连接映射
        connected_users[user.id] = request.sid
        
        # 发送连接成功消息
        emit('connected', {
            'status': 'success',
            'user_id': user.id,
            'username': user.name
        })
        
        print(f"用户 {user.name} (ID: {user.id}) 已连接，Session: {request.sid}")
        
    except Exception as e:
        print(f"连接错误: {str(e)}")
        emit('error', {'message': '连接失败'})
        disconnect()


@socketio.on('disconnect')
def handle_disconnect():
    """处理客户端断开连接"""
    try:
        # 查找断开的用户
        for user_id, sid in list(connected_users.items()):
            if sid == request.sid:
                del connected_users[user_id]
                user = User.query.get(user_id)
                print(f"用户 {user.name if user else user_id} 已断开连接")
                break
    except Exception as e:
        print(f"断开连接错误: {str(e)}")


@socketio.on('ping')
def handle_ping():
    """处理心跳检测"""
    emit('pong', {'timestamp': time.time()})


@socketio.on('mark_received')
def handle_mark_received(data):
    """处理消息接收确认"""
    try:
        notification_id = data.get('notification_id')
        user_id = data.get('user_id')
        
        if not notification_id or not user_id:
            emit('error', {'message': '参数不完整'})
            return
        
        # 查找或创建确认记录
        receipt = NotificationReceipt.query.filter_by(
            notification_id=notification_id,
            user_id=int(user_id)
        ).first()
        
        if not receipt:
            receipt = NotificationReceipt(
                notification_id=notification_id,
                user_id=int(user_id),
                received_time=db.func.now()
            )
            db.session.add(receipt)
            db.session.commit()
        else:
            receipt.received_time = db.func.now()
            db.session.commit()
        
        emit('receipt_confirmed', {
            'notification_id': notification_id,
            'status': 'received'
        })
        
    except Exception as e:
        print(f"标记接收错误: {str(e)}")
        emit('error', {'message': '标记接收失败'})


@socketio.on('confirm_notification')
def handle_confirm_notification(data):
    """处理通知确认"""
    try:
        notification_id = data.get('notification_id')
        user_id = data.get('user_id')
        
        if not notification_id or not user_id:
            emit('error', {'message': '参数不完整'})
            return
        
        # 查找确认记录
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
                'status': 'confirmed',
                'confirmed_time': receipt.confirmed_time.isoformat() if receipt.confirmed_time else None
            })
        else:
            # 如果没有记录，创建新记录
            receipt = NotificationReceipt(
                notification_id=notification_id,
                user_id=int(user_id),
                received_time=db.func.now(),
                is_confirmed=True,
                confirmed_time=db.func.now()
            )
            db.session.add(receipt)
            db.session.commit()
            
            emit('confirm_success', {
                'notification_id': notification_id,
                'status': 'confirmed',
                'confirmed_time': receipt.confirmed_time.isoformat()
            })
            
    except Exception as e:
        print(f"确认通知错误: {str(e)}")
        emit('error', {'message': '确认失败'})


def push_notification_to_user(user_id, notification_data):
    """向指定用户推送通知"""
    try:
        if user_id in connected_users:
            session_id = connected_users[user_id]
            socketio.emit('new_notification', notification_data, room=session_id)
            return True
        return False
    except Exception as e:
        print(f"推送通知错误: {str(e)}")
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
```

- [ ] **步骤2：测试WebSocket连接**

创建测试脚本 `test_websocket.py`：

```python
# -*- coding: utf-8 -*-
"""WebSocket连接测试（仅服务器端）"""
from app import app, socketio
from models import User

def test_connection():
    with app.app_context():
        # 获取一个测试用户
        user = User.query.first()
        if not user:
            print("没有找到测试用户")
            return
        
        print(f"测试用户: {user.name} (ID: {user.id})")
        print(f"模拟token: user_{user.id}_token")
        print("\n服务器运行中...")
        print("请运行客户端测试脚本进行连接测试")

if __name__ == '__main__':
    test_connection()
```

运行服务器：
```bash
cd d:\fh
python app.py
```

预期输出：Flask应用正常启动，WebSocket服务运行

- [ ] **步骤3：提交代码**

```bash
cd d:\fh
git add socket_events.py
git commit -m "feat: 添加WebSocket事件处理模块"
```

---

### 任务4：广播管理API

**文件：**
- 创建：`d:\fh\routes_broadcast.py`

- [ ] **步骤1：创建广播管理API路由**

创建文件 `d:\fh\routes_broadcast.py`：

```python
# -*- coding: utf-8 -*-
"""广播通知管理API"""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from datetime import datetime
import time

from models import db, BroadcastNotification, NotificationReceipt, User
from notification_generator import create_notification_image
from socket_events import push_notification_to_user, push_notification_to_users, push_notification_to_all

bp = Blueprint('broadcast', __name__, url_prefix='/api/broadcast')


def check_broadcast_permission():
    """检查是否有广播权限"""
    return current_user.has_role('admin') or current_user.can_broadcast


def get_target_users(target_type, target_ids):
    """获取目标用户列表"""
    if target_type == 'all':
        # 所有活跃用户
        return [u.id for u in User.query.filter_by(is_active=True).all()]
    
    elif target_type == 'department':
        # 按部门
        if not target_ids:
            return []
        dept_ids = [int(x) for x in target_ids.split(',')]
        return [u.id for u in User.query.filter(User.group_id.in_(dept_ids), User.is_active==True).all()]
    
    elif target_type == 'role':
        # 按角色
        if not target_ids:
            return []
        roles = target_ids.split(',')
        users = []
        for user in User.query.filter_by(is_active=True).all():
            if any(role in user.get_roles() for role in roles):
                users.append(user.id)
        return users
    
    elif target_type == 'user':
        # 指定人员
        if not target_ids:
            return []
        return [int(x) for x in target_ids.split(',')]
    
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
    
    if not content:
        return jsonify({'success': False, 'error': '通知内容不能为空'}), 400
    
    # 创建通知记录
    notification = BroadcastNotification(
        title=title,
        content=content,
        priority=priority,
        target_type=target_type,
        target_ids=target_ids,
        sender_id=current_user.id,
        status='draft'
    )
    
    if scheduled_time:
        notification.scheduled_time = datetime.fromisoformat(scheduled_time)
        notification.status = 'scheduled'
    
    db.session.add(notification)
    db.session.commit()
    
    # 生成图片
    sender_name = current_user.name
    image_path, _ = create_notification_image(title, content, priority, sender_name, notification.id)
    
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
    
    if notification.status == 'sent':
        return jsonify({'success': False, 'error': '通知已经发送'}), 400
    
    # 获取目标用户
    target_user_ids = get_target_users(notification.target_type, notification.target_ids)
    
    if not target_user_ids:
        return jsonify({'success': False, 'error': '没有找到目标用户'}), 400
    
    # 创建确认记录
    for user_id in target_user_ids:
        receipt = NotificationReceipt(
            notification_id=notification.id,
            user_id=user_id
        )
        db.session.add(receipt)
    
    notification.status = 'sent'
    notification.sent_time = datetime.now()
    db.session.commit()
    
    # 推送通知
    notification_data = {
        'type': 'notification',
        'data': {
            'id': notification.id,
            'title': notification.title,
            'content': notification.content,
            'image_url': notification.image_path,
            'priority': notification.priority,
            'timestamp': notification.sent_time.isoformat()
        }
    }
    
    # 根据目标类型推送
    if notification.target_type == 'all':
        pushed_count = push_notification_to_all(notification_data)
    else:
        pushed_count = push_notification_to_users(target_user_ids, notification_data)
    
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
    
    notifications = BroadcastNotification.query\
        .order_by(BroadcastNotification.create_time.desc())\
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
            'sender_name': n.sender.name if n.sender else ''
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
    
    return jsonify({
        'id': notification.id,
        'title': notification.title,
        'content': notification.content,
        'priority': notification.priority,
        'target_type': notification.target_type,
        'target_ids': notification.target_ids,
        'image_path': notification.image_path,
        'status': notification.status,
        'create_time': notification.create_time.isoformat(),
        'sent_time': notification.sent_time.isoformat() if notification.sent_time else None,
        'sender_name': notification.sender.name if notification.sender else ''
    })


@bp.route('/notifications/<int:notification_id>/receipts', methods=['GET'])
@login_required
def get_receipts(notification_id):
    """获取通知确认状态"""
    if not check_broadcast_permission():
        return jsonify({'success': False, 'error': '没有广播权限'}), 403
    
    notification = BroadcastNotification.query.get_or_404(notification_id)
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
    """催读提醒（向未确认的用户重新发送）"""
    if not check_broadcast_permission():
        return jsonify({'success': False, 'error': '没有广播权限'}), 403
    
    notification = BroadcastNotification.query.get_or_404(notification_id)
    
    # 查找未确认的用户
    unconfirmed_receipts = NotificationReceipt.query.filter_by(
        notification_id=notification_id,
        is_confirmed=False
    ).all()
    
    if not unconfirmed_receipts:
        return jsonify({'success': False, 'error': '所有用户都已确认'}), 400
    
    # 重新推送通知
    notification_data = {
        'type': 'notification',
        'data': {
            'id': notification.id,
            'title': notification.title,
            'content': notification.content,
            'image_url': notification.image_path,
            'priority': notification.priority,
            'timestamp': notification.sent_time.isoformat(),
            'reminder': True  # 标记为催读
        }
    }
    
    unconfirmed_user_ids = [r.user_id for r in unconfirmed_receipts]
    pushed_count = push_notification_to_users(unconfirmed_user_ids, notification_data)
    
    return jsonify({
        'success': True,
        'message': f'已向 {pushed_count} 名未确认用户发送提醒',
        'total_unconfirmed': len(unconfirmed_user_ids),
        'pushed_count': pushed_count
    })
```

- [ ] **步骤2：在app.py中注册蓝图和SocketIO**

打开 `d:\fh\app.py`，找到蓝图注册的位置（大约在第20-30行），添加：

```python
# 在现有蓝图注册后添加
from routes_broadcast import bp as broadcast_bp
app.register_blueprint(broadcast_bp)

# 添加Flask-SocketIO
from flask_socketio import SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 导入socket事件（必须在socketio初始化之后）
import socket_events
```

找到运行服务器的代码（约在文件末尾），修改为：

```python
if __name__ == '__main__':
    # 开发环境使用
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
```

- [ ] **步骤3：测试API**

启动服务器：
```bash
cd d:\fh
python app.py
```

使用curl测试（另开一个终端）：
```bash
# 登录获取cookie
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"admin\", \"password\": \"your_password\"}" \
  -c cookies.txt

# 创建通知
curl -X POST http://localhost:5000/api/broadcast/notifications \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "title": "测试通知",
    "content": "这是一条测试通知内容",
    "priority": "normal",
    "target_type": "all"
  }'
```

预期输出：返回JSON，包含通知ID和图片路径

- [ ] **步骤4：提交代码**

```bash
cd d:\fh
git add routes_broadcast.py app.py
git commit -m "feat: 添加广播通知管理API"
```

---

## 阶段2：前端管理后台（第3天）

### 任务5：创建广播管理HTML页面

**文件：**
- 创建：`d:\fh\templates\admin_broadcast.html`

- [ ] **步骤1：创建广播管理页面**

创建文件 `d:\fh\templates\admin_broadcast.html`：

```html
{% extends "base.html" %}

{% block title %}广播通知管理{% endblock %}

{% block content %}
<div class="container-fluid">
    <h2 class="mb-4">
        <i class="bi bi-megaphone"></i> 广播通知管理
    </h2>
    
    <!-- 发送新通知 -->
    <div class="card mb-4">
        <div class="card-header bg-primary text-white">
            <h5 class="mb-0"><i class="bi bi-plus-circle"></i> 发布新通知</h5>
        </div>
        <div class="card-body">
            <form id="notificationForm">
                <div class="row">
                    <div class="col-md-8">
                        <div class="mb-3">
                            <label class="form-label">通知标题</label>
                            <input type="text" class="form-control" id="title" 
                                   maxlength="200" placeholder="请输入通知标题" required>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">通知内容</label>
                            <textarea class="form-control" id="content" rows="5" 
                                      placeholder="请输入通知内容，支持换行" required></textarea>
                        </div>
                    </div>
                    
                    <div class="col-md-4">
                        <div class="mb-3">
                            <label class="form-label">优先级</label>
                            <select class="form-select" id="priority">
                                <option value="normal">普通（蓝色）</option>
                                <option value="important">重要（黄色）</option>
                                <option value="urgent">紧急（红色）</option>
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">发送范围</label>
                            <select class="form-select" id="target_type">
                                <option value="all">全员发送</option>
                                <option value="role">按角色发送</option>
                                <option value="department">按部门发送</option>
                                <option value="user">指定人员发送</option>
                            </select>
                        </div>
                        
                        <div class="mb-3" id="targetIdsContainer" style="display:none;">
                            <label class="form-label">选择目标</label>
                            <select class="form-select" id="target_ids" multiple size="5">
                                <!-- 动态填充 -->
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">定时发送（可选）</label>
                            <input type="datetime-local" class="form-control" id="scheduled_time">
                        </div>
                    </div>
                </div>
                
                <div class="text-end">
                    <button type="button" class="btn btn-secondary me-2" onclick="previewNotification()">
                        <i class="bi bi-eye"></i> 预览图片
                    </button>
                    <button type="submit" class="btn btn-primary">
                        <i class="bi bi-send"></i> 立即发送
                    </button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- 通知列表 -->
    <div class="card">
        <div class="card-header">
            <h5 class="mb-0"><i class="bi bi-list-ul"></i> 通知列表</h5>
        </div>
        <div class="card-body">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>标题</th>
                        <th>优先级</th>
                        <th>发送范围</th>
                        <th>状态</th>
                        <th>发送时间</th>
                        <th>确认率</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody id="notificationTable">
                    <!-- 动态填充 -->
                </tbody>
            </table>
            
            <nav>
                <ul class="pagination justify-content-center" id="pagination">
                    <!-- 动态填充 -->
                </ul>
            </nav>
        </div>
    </div>
</div>

<!-- 预览Modal -->
<div class="modal fade" id="previewModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">通知预览</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body text-center">
                <img id="previewImage" src="" alt="通知预览" class="img-fluid">
            </div>
        </div>
    </div>
</div>

<!-- 确认详情Modal -->
<div class="modal fade" id="receiptsModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">确认详情</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="alert alert-info">
                    <strong>总人数：</strong><span id="totalReceivers">0</span>，
                    <strong>已确认：</strong><span id="confirmedCount">0</span>，
                    <strong>未确认：</strong><span id="unconfirmedCount">0</span>，
                    <strong>确认率：</strong><span id="confirmationRate">0%</span>
                </div>
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>姓名</th>
                            <th>收到时间</th>
                            <th>确认时间</th>
                            <th>状态</th>
                        </tr>
                    </thead>
                    <tbody id="receiptsTable">
                        <!-- 动态填充 -->
                    </tbody>
                </table>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-warning" onclick="remindNotification()">
                    <i class="bi bi-bell"></i> 催读提醒
                </button>
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
let currentNotificationId = null;
let currentPage = 1;

$(document).ready(function() {
    loadNotifications(1);
    loadTargetOptions();
    
    // 表单提交
    $('#notificationForm').submit(function(e) {
        e.preventDefault();
        sendNotification();
    });
    
    // 目标类型变化
    $('#target_type').change(function() {
        const targetType = $(this).val();
        if (targetType === 'all') {
            $('#targetIdsContainer').hide();
        } else {
            $('#targetIdsContainer').show();
        }
    });
});

function loadTargetOptions() {
    // 加载角色选项
    const roles = ['salesman', 'shipper', 'admin'];
    const roleNames = {'salesman': '销售', 'shipper': '发货员', 'admin': '管理员'};
    
    roles.forEach(role => {
        $('#target_ids').append(`<option value="${role}">${roleNames[role]}</option>`);
    });
}

function sendNotification() {
    const title = $('#title').val();
    const content = $('#content').val();
    const priority = $('#priority').val();
    const targetType = $('#target_type').val();
    const targetIds = $('#target_ids').val().join(',');
    const scheduledTime = $('#scheduled_time').val();
    
    $.ajax({
        url: '/api/broadcast/notifications',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            title: title,
            content: content,
            priority: priority,
            target_type: targetType,
            target_ids: targetIds,
            scheduled_time: scheduledTime || null
        }),
        success: function(response) {
            if (response.success) {
                alert('通知创建成功！');
                
                // 如果是立即发送，调用发送接口
                if (!scheduledTime) {
                    sendNotificationToUsers(response.notification.id);
                } else {
                    loadNotifications(1);
                    clearForm();
                }
            } else {
                alert('创建失败：' + response.error);
            }
        },
        error: function() {
            alert('创建通知失败！');
        }
    });
}

function sendNotificationToUsers(notificationId) {
    $.ajax({
        url: `/api/broadcast/notifications/${notificationId}/send`,
        method: 'POST',
        success: function(response) {
            if (response.success) {
                alert(`通知发送成功！共 ${response.total_users} 人，${response.online_users} 人在线`);
                loadNotifications(1);
                clearForm();
            } else {
                alert('发送失败：' + response.error);
            }
        },
        error: function() {
            alert('发送通知失败！');
        }
    });
}

function loadNotifications(page) {
    currentPage = page;
    $.get(`/api/broadcast/notifications?page=${page}`, function(response) {
        const tbody = $('#notificationTable');
        tbody.empty();
        
        response.items.forEach(item => {
            const priorityBadge = {
                'normal': '<span class="badge bg-primary">普通</span>',
                'important': '<span class="badge bg-warning">重要</span>',
                'urgent': '<span class="badge bg-danger">紧急</span>'
            }[item.priority];
            
            const statusBadge = {
                'draft': '<span class="badge bg-secondary">草稿</span>',
                'scheduled': '<span class="badge bg-info">待发送</span>',
                'sent': '<span class="badge bg-success">已发送</span>'
            }[item.status];
            
            tbody.append(`
                <tr>
                    <td>${item.id}</td>
                    <td>${item.title}</td>
                    <td>${priorityBadge}</td>
                    <td>${item.target_type}</td>
                    <td>${statusBadge}</td>
                    <td>${item.sent_time ? item.sent_time.substring(0, 16) : '-'}</td>
                    <td>-</td>
                    <td>
                        <button class="btn btn-sm btn-info" onclick="showReceipts(${item.id})">
                            <i class="bi bi-check-circle"></i> 详情
                        </button>
                    </td>
                </tr>
            `);
        });
        
        // 分页
        renderPagination(response);
    });
}

function renderPagination(response) {
    const pagination = $('#pagination');
    pagination.empty();
    
    if (response.pages <= 1) return;
    
    if (response.has_prev) {
        pagination.append(`<li class="page-item"><a class="page-link" href="#" onclick="loadNotifications(${response.page - 1}); return false;">上一页</a></li>`);
    }
    
    for (let i = 1; i <= response.pages; i++) {
        pagination.append(`<li class="page-item ${i === response.page ? 'active' : ''}">
            <a class="page-link" href="#" onclick="loadNotifications(${i}); return false;">${i}</a>
        </li>`);
    }
    
    if (response.has_next) {
        pagination.append(`<li class="page-item"><a class="page-link" href="#" onclick="loadNotifications(${response.page + 1}); return false;">下一页</a></li>`);
    }
}

function previewNotification() {
    const title = $('#title').val() || '通知标题预览';
    const content = $('#content').val() || '通知内容预览';
    const priority = $('#priority').val();
    
    // 临时创建图片预览
    $.ajax({
        url: '/api/broadcast/notifications',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            title: title,
            content: content,
            priority: priority,
            target_type: 'all'
        }),
        success: function(response) {
            if (response.success) {
                $('#previewImage').attr('src', response.notification.image_path);
                $('#previewModal').modal('show');
                
                // 预览后删除（可选）
            }
        }
    });
}

function showReceipts(notificationId) {
    currentNotificationId = notificationId;
    $.get(`/api/broadcast/notifications/${notificationId}/receipts`, function(response) {
        $('#totalReceivers').text(response.total_receivers);
        $('#confirmedCount').text(response.confirmed_count);
        $('#unconfirmedCount').text(response.unconfirmed_count);
        $('#confirmationRate').text(response.confirmation_rate + '%');
        
        const tbody = $('#receiptsTable');
        tbody.empty();
        
        response.receipts.forEach(receipt => {
            tbody.append(`
                <tr>
                    <td>${receipt.user_name}</td>
                    <td>${receipt.received_time ? receipt.received_time.substring(0, 19) : '-'}</td>
                    <td>${receipt.confirmed_time ? receipt.confirmed_time.substring(0, 19) : '-'}</td>
                    <td>${receipt.is_confirmed ? '<span class="badge bg-success">已确认</span>' : '<span class="badge bg-warning">未确认</span>'}</td>
                </tr>
            `);
        });
        
        $('#receiptsModal').modal('show');
    });
}

function remindNotification() {
    if (!currentNotificationId) return;
    
    if (!confirm('确定要向未确认的用户发送催读提醒吗？')) return;
    
    $.ajax({
        url: `/api/broadcast/notifications/${currentNotificationId}/remind`,
        method: 'POST',
        success: function(response) {
            if (response.success) {
                alert(response.message);
                showReceipts(currentNotificationId);
            } else {
                alert('提醒失败：' + response.error);
            }
        },
        error: function() {
            alert('发送提醒失败！');
        }
    });
}

function clearForm() {
    $('#title').val('');
    $('#content').val('');
    $('#priority').val('normal');
    $('#target_type').val('all');
    $('#target_ids').val('');
    $('#scheduled_time').val('');
    $('#targetIdsContainer').hide();
}
</script>
{% endblock %}
```

- [ ] **步骤2：在base.html添加入口链接**

打开 `d:\fh\templates\base.html`，找到导航菜单的位置，添加广播管理入口：

```html
<!-- 在现有的管理菜单下添加 -->
{% if current_user.has_role('admin') %}
<li class="nav-item">
    <a class="nav-link" href="{{ url_for('broadcast.list_notifications') }}">
        <i class="bi bi-megaphone"></i> 广播管理
    </a>
</li>
{% endif %}
```

同时添加路由映射，在 `d:\fh\app.py` 中添加：

```python
@bp.route('/admin_broadcast')
@login_required
def admin_broadcast():
    return render_template('admin_broadcast.html')
```

- [ ] **步骤3：提交代码**

```bash
cd d:\fh
git add templates/admin_broadcast.html app.py
git commit -m "feat: 添加广播管理前端页面"
```

---

## 阶段3：Windows客户端（第4-6天）

### 任务6：客户端环境准备

**文件：**
- 创建：`d:\fh\client\requirements.txt`
- 创建：`d:\fh\client\build.bat`

- [ ] **步骤1：创建requirements.txt**

创建 `d:\fh\client\requirements.txt`：

```
PyQt5==5.15.10
websocket-client==1.6.1
Pillow==10.0.0
requests==2.31.0
```

- [ ] **步骤2：创建build.bat打包脚本**

创建 `d:\fh\client\build.bat`：

```batch
@echo off
echo 开始打包Windows客户端...

:: 安装打包工具
pip install pyinstaller

:: 打包
pyinstaller --onefile --windowed --icon=app.ico --name="通知客户端" main.py

echo 打包完成！可执行文件位于 dist/通知客户端.exe
pause
```

- [ ] **步骤3：创建README说明**

创建 `d:\fh\client\README.md`：

```markdown
# Windows通知客户端

## 安装依赖
```
pip install -r requirements.txt
```

## 运行测试
```
python main.py
```

## 打包发布
```
build.bat
```

## 配置说明
首次运行会要求配置服务器地址和登录信息。
```

- [ ] **步骤4：提交代码**

```bash
cd d:\fh
mkdir -p client/sounds
git add client/requirements.txt client/build.bat client/README.md
git commit -m "feat: 添加Windows客户端框架"
```

---

### 任务7：客户端核心实现

**文件：**
- 创建：`d:\fh\client\main.py`（主程序入口）
- 创建：`d:\fh\client\notification_window.py`（通知窗口）
- 创建：`d:\fh\client\tray_icon.py`（系统托盘）
- 创建：`d:\fh\client\settings.py`（设置管理）
- 创建：`d:\fh\client\websocket_client.py`（WebSocket客户端）

#### 步骤1：创建settings.py（设置管理）

创建 `d:\fh\client\settings.py`：

```python
# -*- coding: utf-8 -*-
"""设置管理"""
import json
import os
from pathlib import Path


class Settings:
    """设置管理类"""
    
    DEFAULT_SETTINGS = {
        'server_url': 'http://localhost:5000',
        'user_id': '',
        'username': '',
        'token': '',
        'auto_start': False,
        'start_minimized': True,
        'volume': 80,
        'sound_enabled': True,
        'normal_duration': 5,
        'important_duration': 10,
        'urgent_duration': 0  # 0表示不自动隐藏
    }
    
    def __init__(self):
        self.config_dir = Path.home() / '.notification_client'
        self.config_file = self.config_dir / 'settings.json'
        self.settings = self.load()
    
    def load(self):
        """加载设置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    settings = self.DEFAULT_SETTINGS.copy()
                    settings.update(loaded)
                    return settings
            except:
                return self.DEFAULT_SETTINGS.copy()
        return self.DEFAULT_SETTINGS.copy()
    
    def save(self):
        """保存设置"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=2)
    
    def get(self, key, default=None):
        """获取设置"""
        return self.settings.get(key, default)
    
    def set(self, key, value):
        """设置值"""
        self.settings[key] = value
        self.save()
    
    def is_configured(self):
        """检查是否已配置"""
        return bool(self.settings.get('user_id') and self.settings.get('token'))
```

#### 步骤2：创建websocket_client.py（WebSocket客户端）

创建 `d:\fh\client\websocket_client.py`：

```python
# -*- coding: utf-8 -*-
"""WebSocket客户端"""
import threading
import time
import json
from websocket import WebSocketApp, WebSocketConnectionClosedException
from settings import Settings


class WebSocketClient:
    """WebSocket客户端类"""
    
    def __init__(self, on_notification=None, on_connect=None, on_disconnect=None):
        self.settings = Settings()
        self.on_notification = on_notification
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.ws = None
        self.running = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 30
        self.thread = None
    
    def get_server_url(self):
        """获取WebSocket服务器URL"""
        server_url = self.settings.get('server_url', 'http://localhost:5000')
        return server_url.replace('http://', 'ws://').replace('https://', 'wss://') + '/socket.io/?EIO=4&transport=websocket'
    
    def start(self):
        """启动WebSocket连接"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """停止WebSocket连接"""
        self.running = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        if self.thread:
            self.thread.join(timeout=2)
    
    def _run(self):
        """运行WebSocket连接（在线程中）"""
        while self.running:
            try:
                url = self.get_server_url()
                user_id = self.settings.get('user_id')
                token = self.settings.get('token')
                
                if not user_id or not token:
                    if self.on_disconnect:
                        self.on_disconnect('未配置用户信息')
                    time.sleep(5)
                    continue
                
                # 简化版WebSocket URL（Flask-SocketIO兼容）
                ws_url = self.settings.get('server_url', 'http://localhost:5000')
                full_url = f"{ws_url.replace('http://', 'ws://').replace('https://', 'wss://')}/websocket"
                
                headers = [
                    f"user_id: {user_id}",
                    f"token: {token}"
                ]
                
                self.ws = WebSocketApp(
                    full_url,
                    header=headers,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_open=self._on_open,
                    on_close=self._on_close
                )
                
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
                
            except Exception as e:
                print(f"WebSocket错误: {e}")
                if self.on_disconnect:
                    self.on_disconnect(str(e))
            
            if self.running:
                time.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    def _on_open(self, ws):
        """连接打开"""
        print("WebSocket连接已打开")
        self.reconnect_delay = 1
        if self.on_connect:
            self.on_connect()
    
    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭"""
        print(f"WebSocket连接已关闭: {close_msg}")
        if self.on_disconnect:
            self.on_disconnect(close_msg)
    
    def _on_error(self, ws, error):
        """连接错误"""
        print(f"WebSocket错误: {error}")
    
    def _on_message(self, ws, message):
        """收到消息"""
        try:
            data = json.loads(message)
            
            # 处理不同类型的消息
            msg_type = data.get('type')
            
            if msg_type == 'notification' or 'data' in data:
                notification_data = data.get('data', data)
                if self.on_notification:
                    self.on_notification(notification_data)
            
            elif msg_type == 'connected':
                print(f"已连接: {data.get('username')}")
            
            elif msg_type == 'error':
                print(f"错误: {data.get('message')}")
            
            elif msg_type == 'confirm_success':
                print(f"确认成功: 通知 {data.get('notification_id')}")
            
            elif msg_type == 'receipt_confirmed':
                print(f"收到确认: 通知 {data.get('notification_id')}")
            
        except json.JSONDecodeError:
            print(f"收到非JSON消息: {message}")
        except Exception as e:
            print(f"处理消息错误: {e}")
    
    def send_confirm(self, notification_id):
        """发送确认"""
        if self.ws:
            try:
                message = json.dumps({
                    'type': 'confirm_notification',
                    'notification_id': notification_id,
                    'user_id': self.settings.get('user_id')
                })
                self.ws.send(message)
                return True
            except Exception as e:
                print(f"发送确认失败: {e}")
                return False
        return False
    
    def send_received(self, notification_id):
        """发送已收到标记"""
        if self.ws:
            try:
                message = json.dumps({
                    'type': 'mark_received',
                    'notification_id': notification_id,
                    'user_id': self.settings.get('user_id')
                })
                self.ws.send(message)
                return True
            except Exception as e:
                print(f"发送收到标记失败: {e}")
                return False
        return False
```

#### 步骤3：创建notification_window.py（通知窗口）

创建 `d:\fh\client\notification_window.py`：

```python
# -*- coding: utf-8 -*-
"""通知窗口"""
import os
import time
import requests
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPixmap, QImage, QPainter, QFont, QColor, QBrush, QPen
from PyQt5.Qt import QUrl, QNetworkAccessManager, QNetworkRequest, QNetworkReply
from settings import Settings


class NotificationWindow(QWidget):
    """通知窗口类"""
    
    PRIORITY_COLORS = {
        'normal': {'border': '#3498db', 'bg': '#ffffff', 'title': '#2c3e50'},
        'important': {'border': '#f39c12', 'bg': '#fffef0', 'title': '#2c3e50'},
        'urgent': {'border': '#e74c3c', 'bg': '#fff5f5', 'title': '#c0392b'}
    }
    
    def __init__(self, notification_data, on_confirm, on_close):
        super().__init__()
        self.notification_data = notification_data
        self.on_confirm = on_confirm
        self.on_close = on_close
        self.settings = Settings()
        self.downloaded_image = None
        
        self.init_ui()
        self.load_image()
        self.start_auto_hide()
        self.animate_in()
    
    def init_ui(self):
        """初始化UI"""
        # 窗口属性
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 尺寸和位置
        width = 600
        height = 450
        screen_geometry = self.screen().geometry()
        x = screen_geometry.right() - width - 20
        y = screen_geometry.top() + 20
        self.setGeometry(x, y, width, height)
        
        # 主容器
        container = QWidget(self)
        container.setGeometry(0, 0, width, height)
        
        # 优先级颜色
        priority = self.notification_data.get('priority', 'normal')
        colors = self.PRIORITY_COLORS.get(priority, self.PRIORITY_COLORS['normal'])
        
        # 设置样式
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {colors['bg']};
                border: 3px solid {colors['border']};
                border-radius: 10px;
            }}
            QPushButton {{
                background-color: {colors['border']};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {colors['border']}dd;
            }}
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 关闭按钮
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton('✕')
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.handle_close)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)
        
        # 图片标签
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(300)
        self.image_label.setStyleSheet("border: none;")
        layout.addWidget(self.image_label)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        confirm_btn = QPushButton('✓ 我已知晓')
        confirm_btn.setFixedSize(150, 40)
        confirm_btn.clicked.connect(self.handle_confirm)
        btn_layout.addWidget(confirm_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 紧急通知闪烁效果
        if priority == 'urgent':
            self.start_blink_effect()
    
    def load_image(self):
        """加载通知图片"""
        image_url = self.notification_data.get('image_url')
        if not image_url:
            self.show_placeholder()
            return
        
        # 处理URL
        if image_url.startswith('http'):
            url = image_url
        else:
            server_url = self.settings.get('server_url', 'http://localhost:5000')
            url = server_url.rstrip('/') + image_url
        
        try:
            # 下载图片
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                from PyQt5.QtGui import QPixmap
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                
                # 缩放到合适大小
                scaled_pixmap = pixmap.scaled(
                    560, 350,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
                self.downloaded_image = pixmap
        except Exception as e:
            print(f"加载图片失败: {e}")
            self.show_placeholder()
    
    def show_placeholder(self):
        """显示占位符"""
        self.image_label.setText('通知图片加载中...')
        self.image_label.setStyleSheet("color: gray; font-size: 16px;")
    
    def start_auto_hide(self):
        """启动自动隐藏定时器"""
        priority = self.notification_data.get('priority', 'normal')
        durations = {
            'normal': self.settings.get('normal_duration', 5),
            'important': self.settings.get('important_duration', 10),
            'urgent': self.settings.get('urgent_duration', 0)
        }
        
        duration = durations.get(priority, 5)
        
        if duration > 0:
            self.hide_timer = QTimer()
            self.hide_timer.timeout.connect(self.handle_close)
            self.hide_timer.setSingleShot(True)
            self.hide_timer.start(duration * 1000)
    
    def start_blink_effect(self):
        """紧急通知闪烁效果"""
        self.blink_timer = QTimer()
        self.blink_count = 0
        self.blink_timer.timeout.connect(self.toggle_blink)
        self.blink_timer.start(500)  # 每500ms切换一次
    
    def toggle_blink(self):
        """切换闪烁状态"""
        self.blink_count += 1
        if self.blink_count > 20:  # 闪烁10次后停止
            self.blink_timer.stop()
            return
        
        current_opacity = self.windowOpacity()
        new_opacity = 0.3 if current_opacity > 0.5 else 1.0
        self.setWindowOpacity(new_opacity)
    
    def animate_in(self):
        """入场动画"""
        self.setWindowOpacity(0)
        
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.start()
    
    def animate_out(self, callback):
        """出场动画"""
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(200)
        self.animation.setStartValue(1)
        self.animation.setEndValue(0)
        self.animation.setEasingCurve(QEasingCurve.InCubic)
        self.animation.finished.connect(callback)
        self.animation.start()
    
    def handle_confirm(self):
        """处理确认按钮"""
        self.stop_timers()
        
        if self.on_confirm:
            self.on_confirm(self.notification_data.get('id'))
        
        self.animate_out(self.close)
    
    def handle_close(self):
        """处理关闭按钮"""
        self.stop_timers()
        
        if self.on_close:
            self.on_close(self.notification_data.get('id'))
        
        self.animate_out(self.close)
    
    def stop_timers(self):
        """停止所有定时器"""
        if hasattr(self, 'hide_timer'):
            self.hide_timer.stop()
        if hasattr(self, 'blink_timer'):
            self.blink_timer.stop()
```

#### 步骤4：创建tray_icon.py（系统托盘）

创建 `d:\fh\client\tray_icon.py`：

```python
# -*- coding: utf-8 -*-
"""系统托盘图标"""
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush
from PyQt5.QtCore import Qt


class TrayIcon(QSystemTrayIcon):
    """系统托盘图标类"""
    
    def __init__(self, on_open=None, on_history=None, on_settings=None, on_exit=None):
        super().__init__()
        self.on_open = on_open
        self.on_history = on_history
        self.on_settings = on_settings
        self.on_exit = on_exit
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        # 创建图标
        self.setIcon(self.create_icon('normal'))
        self.setToolTip('通知客户端')
        
        # 创建菜单
        self.menu = QMenu()
        
        self.menu.addAction('📖 打开主界面', self.handle_open)
        self.menu.addAction('📋 历史通知', self.handle_history)
        self.menu.addSeparator()
        self.menu.addAction('⚙️ 设置', self.handle_settings)
        self.menu.addSeparator()
        self.menu.addAction('❌ 退出', self.handle_exit)
        
        self.setContextMenu(self.menu)
        
        # 点击事件
        self.activated.connect(self.on_activated)
    
    def create_icon(self, status='normal'):
        """创建图标"""
        # 图标颜色
        colors = {
            'normal': (0, 200, 0),      # 绿色
            'new': (0, 150, 255),         # 蓝色
            'urgent': (255, 0, 0),        # 红色
            'offline': (128, 128, 128)    # 灰色
        }
        
        r, g, b = colors.get(status, colors['normal'])
        
        # 创建图标
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制圆形
        painter.setBrush(QBrush(QColor(r, g, b)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        
        # 绘制通知符号
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(self.font())
        painter.drawText(pixmap.rect(), Qt.AlignCenter, '📢')
        
        painter.end()
        
        return QIcon(pixmap)
    
    def on_activated(self, reason):
        """处理托盘图标激活"""
        if reason == QSystemTrayIcon.Trigger:
            self.handle_open()
        elif reason == QSystemTrayIcon.DoubleClick:
            self.handle_open()
    
    def handle_open(self):
        """打开主界面"""
        if self.on_open:
            self.on_open()
    
    def handle_history(self):
        """查看历史"""
        if self.on_history:
            self.on_history()
    
    def handle_settings(self):
        """打开设置"""
        if self.on_settings:
            self.on_settings()
    
    def handle_exit(self):
        """退出程序"""
        if self.on_exit:
            self.on_exit()
    
    def set_status(self, status):
        """设置图标状态"""
        self.setIcon(self.create_icon(status))
    
    def show_message(self, title, message, duration=3000):
        """显示气泡消息"""
        self.showMessage(title, message, QSystemTrayIcon.Information, duration)
    
    def set_has_new(self, has_new=True):
        """设置是否有新通知"""
        if has_new:
            self.set_status('new')
        else:
            self.set_status('normal')
    
    def set_offline(self):
        """设置离线状态"""
        self.set_status('offline')
        self.show_message('连接已断开', '正在尝试重新连接...')
    
    def set_online(self):
        """设置在线状态"""
        self.set_status('normal')
        self.show_message('已连接', '通知客户端已启动')
```

#### 步骤5：创建main.py（主程序）

创建 `d:\fh\client\main.py`：

```python
# -*- coding: utf-8 -*-
"""通知客户端主程序"""
import sys
import os
import winsound
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from settings import Settings
from tray_icon import TrayIcon
from notification_window import NotificationWindow
from websocket_client import WebSocketClient


class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('设置')
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        
        # 服务器地址
        layout.addWidget(QLabel('服务器地址:'))
        self.server_input = QLineEdit()
        self.server_input.setText(self.settings.get('server_url', 'http://localhost:5000'))
        layout.addWidget(self.server_input)
        
        # 用户ID
        layout.addWidget(QLabel('用户ID:'))
        self.user_id_input = QLineEdit()
        self.user_id_input.setText(str(self.settings.get('user_id', '')))
        layout.addWidget(self.user_id_input)
        
        # Token
        layout.addWidget(QLabel('认证Token:'))
        self.token_input = QLineEdit()
        self.token_input.setText(self.settings.get('token', ''))
        layout.addWidget(self.token_input)
        
        # 音量
        layout.addWidget(QLabel(f'音量 ({self.settings.get("volume", 80)}%):'))
        self.volume_slider = QComboBox()
        for v in [0, 20, 40, 60, 80, 100]:
            self.volume_slider.addItem(f'{v}%', v)
        self.volume_slider.setCurrentIndex(self.settings.get('volume', 80) // 20)
        layout.addWidget(self.volume_slider)
        
        # 保存按钮
        save_btn = QPushButton('保存')
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        
        self.setLayout(layout)
    
    def save_settings(self):
        """保存设置"""
        self.settings.set('server_url', self.server_input.text())
        self.settings.set('user_id', self.user_id_input.text())
        self.settings.set('token', self.token_input.text())
        self.settings.set('volume', self.volume_slider.currentData())
        
        QMessageBox.information(self, '提示', '设置已保存！')
        self.accept()


class MainWindow:
    """主窗口类（无实际窗口，仅管理托盘）"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.settings = Settings()
        self.notification_windows = []
        
        # 检查配置
        if not self.settings.is_configured():
            self.show_settings()
        
        # 初始化组件
        self.init_tray()
        self.init_websocket()
        
        # 播放启动声音
        self.play_sound('start')
    
    def init_tray(self):
        """初始化托盘"""
        self.tray = TrayIcon(
            on_open=self.on_open,
            on_history=self.on_history,
            on_settings=self.show_settings,
            on_exit=self.on_exit
        )
        self.tray.show()
    
    def init_websocket(self):
        """初始化WebSocket"""
        self.ws_client = WebSocketClient(
            on_notification=self.on_notification,
            on_connect=self.on_connect,
            on_disconnect=self.on_disconnect
        )
        self.ws_client.start()
    
    def on_notification(self, data):
        """收到新通知"""
        print(f"收到通知: {data.get('title', '无标题')}")
        
        # 播放声音
        priority = data.get('priority', 'normal')
        self.play_sound(priority)
        
        # 显示托盘消息
        self.tray.show_message('新通知', data.get('title', '您有一条新通知'))
        self.tray.set_status('new')
        
        # 显示通知窗口
        self.show_notification_window(data)
    
    def show_notification_window(self, data):
        """显示通知窗口"""
        window = NotificationWindow(
            data,
            on_confirm=self.on_confirm,
            on_close=self.on_close
        )
        window.show()
        self.notification_windows.append(window)
    
    def on_confirm(self, notification_id):
        """确认通知"""
        if self.ws_client:
            self.ws_client.send_confirm(notification_id)
        self.tray.set_status('normal')
        print(f"已确认通知: {notification_id}")
    
    def on_close(self, notification_id):
        """关闭通知"""
        self.tray.set_status('normal')
        print(f"已关闭通知: {notification_id}")
    
    def on_connect(self):
        """连接成功"""
        self.tray.set_status('normal')
        self.tray.show_message('已连接', '通知客户端已启动')
        print("WebSocket连接成功")
    
    def on_disconnect(self, reason):
        """断开连接"""
        self.tray.set_offline()
        print(f"WebSocket断开: {reason}")
    
    def on_open(self):
        """打开主界面（显示托盘菜单）"""
        pass
    
    def on_history(self):
        """查看历史"""
        QMessageBox.information(None, '历史通知', '历史通知功能开发中...')
    
    def show_settings(self):
        """显示设置对话框"""
        dialog = SettingsDialog(self.settings)
        dialog.exec_()
    
    def on_exit(self):
        """退出程序"""
        self.ws_client.stop()
        sys.exit(0)
    
    def play_sound(self, sound_type):
        """播放声音"""
        if not self.settings.get('sound_enabled', True):
            return
        
        volume = self.settings.get('volume', 80)
        
        # 使用winsound播放系统声音
        sound_map = {
            'normal': winsound.MB_ICONASTERISK,
            'important': winsound.MB_ICONHAND,
            'urgent': winsound.MB_ICONWARNING,
            'start': winsound.MB_ICONASTERISK
        }
        
        winsound.MessageBeep(sound_map.get(sound_type, winsound.MB_ICONASTERISK))
    
    def run(self):
        """运行应用"""
        sys.exit(self.app.exec_())


if __name__ == '__main__':
    window = MainWindow()
    window.run()
```

- [ ] **步骤6：提交客户端代码**

```bash
cd d:\fh
git add client/main.py client/notification_window.py client/tray_icon.py
git add client/settings.py client/websocket_client.py
git commit -m "feat: 添加Windows客户端核心功能"
```

---

## 阶段4：测试与部署（第7天）

### 任务8：测试与打包

**文件：**
- 修改：客户端配置和测试

- [ ] **步骤1：测试后端功能**

```bash
cd d:\fh

# 启动服务器
python app.py
```

在浏览器中访问 `http://localhost:5000/admin_broadcast`，使用管理员账号登录测试。

- [ ] **步骤2：测试客户端**

```bash
cd d:\fh\client

# 安装依赖
pip install -r requirements.txt

# 运行客户端
python main.py
```

验证：
- [ ] 托盘图标显示
- [ ] 设置对话框可用
- [ ] WebSocket连接（需要配置正确的服务器地址）

- [ ] **步骤3：打包客户端**

```bash
cd d:\fh\client

# 运行打包脚本
build.bat
```

验证：`dist/通知客户端.exe` 是否生成。

- [ ] **步骤4：提交测试代码**

```bash
cd d:\fh
git add .
git commit -m "feat: 完成通知系统全部功能开发和测试"
```

---

## 📊 实施检查清单

### 阶段1：后端核心 ✅
- [x] 数据库模型扩展
- [x] 图片生成器
- [x] WebSocket事件处理
- [x] 广播管理API

### 阶段2：前端管理后台 ✅
- [x] 广播管理HTML页面
- [x] 通知列表和统计
- [x] 确认详情和催读功能

### 阶段3：Windows客户端 ✅
- [x] 客户端环境准备
- [x] 设置管理
- [x] WebSocket客户端
- [x] 通知窗口
- [x] 系统托盘
- [x] 主程序入口

### 阶段4：测试与部署 ✅
- [ ] 后端功能测试
- [ ] 客户端功能测试
- [ ] 打包exe
- [ ] 部署上线

---

## 🚀 部署说明

### 服务器部署
```bash
cd d:\fh
pip install flask-socketio flask-socketio pillow websocket-client
python app.py
```

### 客户端部署
1. 将 `dist/通知客户端.exe` 分发给员工
2. 员工首次运行需要配置：
   - 服务器地址
   - 用户ID和Token
3. 可选：配置开机自启动

### 注意事项
- 确保服务器防火墙开放WebSocket端口
- 客户端需要保持网络连接
- 建议使用HTTPS（生产环境）

---

**计划版本：** 1.0  
**创建日期：** 2026-05-19  
**预计工期：** 7天
