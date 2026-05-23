"""添加企业微信通话记录表"""
from app import app, db

with app.app_context():
    # 检查表是否已存在
    from sqlalchemy import text
    result = db.session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='wework_call_record'"))
    exists = result.fetchone()
    
    if exists:
        print("wework_call_record 表已存在，无需迁移")
    else:
        print("创建 wework_call_record 表...")
        # 创建表
        from models import WeworkCallRecord
        db.create_all()
        print("✓ 表创建成功！")
