# -*- coding: utf-8 -*-
"""发货通知系统 - 主入口"""
import json

from flask import Flask
from flask_login import LoginManager

from config import Config
from models import db, User, _now_bj
from services import run_scheduled_task_by_key
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
from routes_blacklist import bp as blacklist_bp
from routes_wecom_scrm import bp as wecom_scrm_bp
from routes_admin_tasks import bp as admin_tasks_bp, register_task, sync_task_config_to_db
from routes_knowledge import bp as knowledge_bp
from routes_finance import bp as finance_bp
from routes_marketing import bp as marketing_bp


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
app.register_blueprint(blacklist_bp)
app.register_blueprint(wecom_scrm_bp)
app.register_blueprint(admin_tasks_bp)
app.register_blueprint(knowledge_bp)
app.register_blueprint(finance_bp)
app.register_blueprint(marketing_bp)


# ============ 注册定时任务（在这里新增任务即可，配置由 admin 在页面上调整） ============
register_task('update_sf_logistics',
              name='顺丰物流批量更新',
              description='按间隔小时数定时扫描所有顺丰订单，调用顺丰接口获取最新物流状态并更新',
              trigger_type='interval',
              default_interval_hours=6)
register_task('check_order_reminders',
              name='订单发货提醒检查',
              description='每天检查预计发货时间已到或即将到达的订单，向业务员发送桌面提醒',
              trigger_type='cron',
              default_cron_time='01:00')

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
    
    # behavior_tracking_record表迁移：添加is_rejected列
    try:
        bt_columns = [col['name'] for col in inspector.get_columns('behavior_tracking_record')]
        if 'is_rejected' not in bt_columns:
            db.session.execute(text("ALTER TABLE behavior_tracking_record ADD COLUMN is_rejected TINYINT(1) DEFAULT 0"))
            # 迁移旧数据：play_status=4表示拒接
            db.session.execute(text("""
                UPDATE behavior_tracking_record 
                SET is_rejected = 1, play_status = 0 
                WHERE play_status = 4
            """))
            db.session.commit()
            print('[迁移] 已添加behavior_tracking_record.is_rejected列，旧数据已迁移')
    except Exception as e:
        print(f'[迁移] behavior_tracking_record表检查/迁移: {e}')
    
    # behavior_tracking_record表迁移：添加is_missed列（未接）
    try:
        bt_columns = [col['name'] for col in inspector.get_columns('behavior_tracking_record')]
        if 'is_missed' not in bt_columns:
            db.session.execute(text("ALTER TABLE behavior_tracking_record ADD COLUMN is_missed TINYINT(1) DEFAULT 0"))
            db.session.commit()
            print('[迁移] 已添加behavior_tracking_record.is_missed列')
    except Exception as e:
        print(f'[迁移] behavior_tracking_record表检查/迁移is_missed列: {e}')
    
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

    # 创建 scheduled_task 配置表
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS scheduled_task (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                task_key VARCHAR(100) NOT NULL UNIQUE,
                name VARCHAR(200) NOT NULL,
                description VARCHAR(500),
                trigger_type VARCHAR(20) DEFAULT 'interval',
                interval_hours INTEGER DEFAULT 6,
                cron_time VARCHAR(10) DEFAULT '01:00',
                is_enabled TINYINT(1) DEFAULT 1,
                last_run_time DATETIME,
                last_run_status VARCHAR(20),
                last_run_message VARCHAR(500),
                next_run_time DATETIME,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """))
        db.session.commit()
        print('[迁移] 已检查/创建 scheduled_task 表')
    except Exception as e:
        if 'already exists' not in str(e).lower():
            print(f'[迁移] scheduled_task表创建/检查: {e}')

    # 创建 scheduled_task_log 日志表
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS scheduled_task_log (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                task_id INTEGER NOT NULL,
                run_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                duration_seconds INTEGER DEFAULT 0,
                status VARCHAR(20),
                message TEXT,
                FOREIGN KEY (task_id) REFERENCES scheduled_task(id)
            )
        """))
        db.session.commit()
        print('[迁移] 已检查/创建 scheduled_task_log 表')
    except Exception as e:
        if 'already exists' not in str(e).lower():
            print(f'[迁移] scheduled_task_log表创建/检查: {e}')

    # 创建 knowledge_entry 话术库表
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS knowledge_entry (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                title VARCHAR(200) NOT NULL,
                keywords VARCHAR(500) NOT NULL,
                content TEXT NOT NULL,
                is_active TINYINT(1) DEFAULT 1,
                view_count INTEGER DEFAULT 0,
                author_id INTEGER,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (author_id) REFERENCES `user`(id)
            )
        """))
        db.session.commit()
        print('[迁移] 已检查/创建 knowledge_entry 表')
    except Exception as e:
        if 'already exists' not in str(e).lower():
            print(f'[迁移] knowledge_entry表创建/检查: {e}')


def init_db():
    """初始化数据库"""
    db.create_all()

    # 执行数据迁移
    run_migrations()

    # 同步任务注册表到数据库
    sync_task_config_to_db()
    db.session.commit()


# ============ 启动定时任务（从数据库配置加载） ============
scheduler = BackgroundScheduler()


def _scheduled_job_wrapper(task_key):
    """调度器统一包装函数：执行任务并更新状态/日志"""
    from models import ScheduledTask, ScheduledTaskLog, _now_bj as __now_bj

    result = run_scheduled_task_by_key(task_key)

    with app.app_context():
        task = ScheduledTask.query.filter_by(task_key=task_key).first()
        if task:
            task.last_run_time = __now_bj()
            task.last_run_status = result.get('status')
            task.last_run_message = result.get('message', '')[:500]

            log = ScheduledTaskLog(
                task_id=task.id,
                run_time=task.last_run_time,
                duration_seconds=result.get('duration', 0),
                status=result.get('status'),
                message=result.get('message', '')[:2000],
            )
            db.session.add(log)
            db.session.commit()


def _reload_scheduler_jobs():
    """从数据库读取所有启用的任务，重建调度器"""
    from models import ScheduledTask
    from datetime import timedelta

    # 清空现有任务
    for job in scheduler.get_jobs():
        scheduler.remove_job(job.id)

    with app.app_context():
        tasks = ScheduledTask.query.filter_by(is_enabled=True).all()
        for task in tasks:
            try:
                if task.trigger_type == 'interval':
                    scheduler.add_job(
                        _scheduled_job_wrapper,
                        'interval',
                        hours=task.interval_hours,
                        args=[task.task_key],
                        id=task.task_key,
                        replace_existing=True,
                    )
                elif task.trigger_type == 'cron':
                    h, m = map(int, task.cron_time.split(':'))
                    scheduler.add_job(
                        _scheduled_job_wrapper,
                        'cron',
                        hour=h,
                        minute=m,
                        args=[task.task_key],
                        id=task.task_key,
                        replace_existing=True,
                    )
            except Exception as e:
                print(f'[定时任务] 注册任务 {task.task_key} 失败: {e}')

        # 维护每个任务的 next_run_time（展示用）
        # 通过 get_jobs() 获取所有任务，避免不同版本 APScheduler 属性差异
        job_map = {j.id: j for j in scheduler.get_jobs()}
        for task in ScheduledTask.query.all():
            job = job_map.get(task.task_key)
            if job:
                try:
                    raw = getattr(job, 'next_run_time', None)
                    if raw is None:
                        pass
                    elif callable(raw):
                        next_rt = raw()
                        if next_rt:
                            task.next_run_time = next_rt.replace(tzinfo=None) if hasattr(next_rt, 'replace') else None
                    else:
                        if raw:
                            task.next_run_time = raw.replace(tzinfo=None) if hasattr(raw, 'replace') else None
                except Exception:
                    pass
                if not task.is_enabled:
                    task.next_run_time = None
            elif not task.is_enabled:
                task.next_run_time = None
        db.session.commit()


# 启动调度器（先初始化数据库，再加载任务）
with app.app_context():
    init_db()

# 从数据库加载任务并启动
_reload_scheduler_jobs()
scheduler.start()

# 每 5 分钟检测一次数据库中是否有配置变更，如有则重建调度器
_reload_last_check = {'update_time': None}


def _check_config_changes():
    """检查是否有任务被启停/改配置，如有则重建调度器"""
    from models import ScheduledTask
    with app.app_context():
        latest = db.session.query(db.func.max(ScheduledTask.update_time)).scalar()
        if latest and (_reload_last_check['update_time'] is None or latest > _reload_last_check['update_time']):
            _reload_last_check['update_time'] = latest
            _reload_scheduler_jobs()
            print(f'[定时任务] 检测到配置变更，已重新加载 ({latest})')


scheduler.add_job(_check_config_changes, 'interval', minutes=5, id='_config_watcher', replace_existing=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
