# -*- coding: utf-8 -*-
"""发货通知系统 - 主入口"""
import json

from flask import Flask
from flask_login import LoginManager

from config import Config
from models import db, User, _now_bj
from services import update_sf_logistics, check_order_reminders
from apscheduler.schedulers.background import BackgroundScheduler

# ============ 应用初始化 ============
app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Jinja2过滤器
@app.template_filter('from_json')
def from_json_filter(value):
    if isinstance(value, str):
        return json.loads(value)
    return value or {}

@app.template_filter('format_duration')
def format_duration_filter(seconds):
    """格式化时长显示"""
    try:
        if not seconds:
            return '-'
        seconds = int(seconds)
        minutes, secs = divmod(seconds, 60)
        hours, mins = divmod(minutes, 60)
        if hours > 0:
            return f'{hours}时{mins}分{secs}秒'
        elif minutes > 0:
            return f'{mins}分{secs}秒'
        else:
            return f'{secs}秒'
    except (ValueError, TypeError):
        return '-'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ============ 注册蓝图 ============
from routes_auth import bp as auth_bp
from routes_orders import bp as orders_bp
from routes_shipping import bp as shipping_bp
from routes_admin_users import bp as admin_users_bp
from routes_admin_config import bp as admin_config_bp
from routes_notifications import bp as notifications_bp
from routes_templates import bp as templates_bp
from routes_import import bp as import_routes_bp
from routes_export import bp as export_bp
from routes_performance import bp as performance_bp
from routes_behavior import bp as behavior_bp
from routes_dingtalk import bp as dingtalk_bp
from routes_customer_follow_up import bp as customer_follow_up_bp
from routes_tools import bp as tools_bp
from routes_broadcast import bp as broadcast_bp
from routes_wework import bp as wework_bp

app.register_blueprint(auth_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(shipping_bp)
app.register_blueprint(admin_users_bp)
app.register_blueprint(admin_config_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(templates_bp)
app.register_blueprint(import_routes_bp)
app.register_blueprint(export_bp)
app.register_blueprint(performance_bp)
app.register_blueprint(behavior_bp)
app.register_blueprint(dingtalk_bp)
app.register_blueprint(customer_follow_up_bp)
app.register_blueprint(tools_bp)
app.register_blueprint(broadcast_bp)
app.register_blueprint(wework_bp)

# Flask-SocketIO初始化
from flask_socketio import SocketIO, emit
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e6,
    transports=['polling']  # 强制使用轮询，避免WebSocket兼容性问题
)

# 导入并初始化socket事件
import socket_events
socket_events.init_socketio(socketio)


# ============ 数据库迁移 ============
def run_migrations():
    """数据库迁移：每次启动时自动检查并执行"""
    from sqlalchemy import text, inspect
    inspector = inspect(db.engine)

    # user表迁移
    user_columns = [col['name'] for col in inspector.get_columns('user')]
    if 'roles' not in user_columns:
        db.session.execute(text("ALTER TABLE `user` ADD COLUMN roles VARCHAR(100) DEFAULT 'salesman'"))
        db.session.execute(text("UPDATE `user` SET roles = role"))
        db.session.commit()
        print('[迁移] 已添加roles列，数据已从role迁移')
    if 'can_dingtalk_export' not in user_columns:
        db.session.execute(text('ALTER TABLE `user` ADD COLUMN can_dingtalk_export TINYINT(1) DEFAULT 0'))
        db.session.commit()
        print('[迁移] 已添加can_dingtalk_export列')
    
    # 检查password_hash列的类型，可能需要处理旧的二进制格式
    try:
        from models import User
        users = User.query.all()
        for user in users:
            if user.password_hash:
                try:
                    # 测试一下是否能正常处理
                    if isinstance(user.password_hash, bytes):
                        # 如果是二进制，解码后存回
                        user.password_hash = user.password_hash.decode('utf-8')
                except Exception:
                    pass
        db.session.commit()
    except Exception:
        pass

    # category表迁移
    try:
        cat_columns = [col['name'] for col in inspector.get_columns('category')]
        if 'example' not in cat_columns:
            db.session.execute(text("ALTER TABLE category ADD COLUMN example TEXT DEFAULT ''"))
            db.session.commit()
            print('[迁移] 已添加category.example列')
    except Exception:
        pass  # category表可能不存在

    # order表迁移
    try:
        order_columns = [col['name'] for col in inspector.get_columns('order')]
        if 'sign_time' not in order_columns:
            db.session.execute(text("ALTER TABLE `order` ADD COLUMN sign_time DATETIME"))
            db.session.commit()
            print('[迁移] 已添加order.sign_time列')
    except Exception:
        pass  # order表可能不存在
    
    # tool_file表迁移
    try:
        tool_file_columns = [col['name'] for col in inspector.get_columns('tool_file')]
        if 'group_id' not in tool_file_columns:
            db.session.execute(text("ALTER TABLE tool_file ADD COLUMN group_id INTEGER NOT NULL DEFAULT 0"))
            # 更新现有文件记录的group_id（从上传者的group_id获取）
            db.session.execute(text("""
                UPDATE tool_file 
                SET group_id = (SELECT group_id FROM `user` WHERE `user`.id = tool_file.uploader_id)
            """))
            db.session.commit()
            print('[迁移] 已添加tool_file.group_id列')
    except Exception:
        pass  # tool_file表可能不存在
    
    # 创建order_reminder表（MySQL语法兼容）
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS order_reminder (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                order_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                expected_shipping_time DATETIME NOT NULL,
                is_sent TINYINT(1) DEFAULT 0,
                sent_time DATETIME,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.session.commit()
        print('[迁移] 已创建order_reminder表')
    except Exception as e:
        if 'already exists' not in str(e).lower():
            print(f'[迁移] order_reminder表创建/检查: {e}')


def init_db():
    """初始化数据库"""
    db.create_all()

    # 执行数据迁移
    run_migrations()
    db.session.commit()


# ============ 启动定时任务 ============
scheduler = BackgroundScheduler()
scheduler.add_job(update_sf_logistics, 'interval', hours=6, args=[app])
# 每天凌晨1点检查订单发货提醒
scheduler.add_job(check_order_reminders, 'cron', hour=1, minute=0, args=[app])
scheduler.start()

# ============ 初始化数据库 ============
with app.app_context():
    init_db()

# ============ 初始化企微通话配置 ============
from routes_wework import init_call_recording_config
init_call_recording_config(app)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
