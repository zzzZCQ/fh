# -*- coding: utf-8 -*-
"""发货通知系统 - 主入口"""
import json

from flask import Flask
from flask_login import LoginManager

from config import Config
from models import db, User, _now_bj
from services import update_sf_logistics
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

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


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


# ============ 数据库迁移 ============
def run_migrations():
    """数据库迁移：每次启动时自动检查并执行"""
    from sqlalchemy import text, inspect
    inspector = inspect(db.engine)

    # user表迁移
    user_columns = [col['name'] for col in inspector.get_columns('user')]
    if 'roles' not in user_columns:
        db.session.execute(text("ALTER TABLE user ADD COLUMN roles VARCHAR(100) DEFAULT 'salesman'"))
        db.session.execute(text("UPDATE user SET roles = role"))
        db.session.commit()
        print('[迁移] 已添加roles列，数据已从role迁移')
    if 'can_dingtalk_export' not in user_columns:
        db.session.execute(text('ALTER TABLE user ADD COLUMN can_dingtalk_export BOOLEAN DEFAULT 0'))
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
            db.session.execute(text("ALTER TABLE order ADD COLUMN sign_time DATETIME"))
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
                SET group_id = (SELECT group_id FROM user WHERE user.id = tool_file.uploader_id)
            """))
            db.session.commit()
            print('[迁移] 已添加tool_file.group_id列')
    except Exception:
        pass  # tool_file表可能不存在


def init_db():
    """初始化数据库"""
    db.create_all()

    # 执行数据迁移
    run_migrations()
    db.session.commit()


# ============ 启动定时任务 ============
scheduler = BackgroundScheduler()
scheduler.add_job(update_sf_logistics, 'interval', hours=6, args=[app])
scheduler.start()

# ============ 初始化数据库 ============
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
