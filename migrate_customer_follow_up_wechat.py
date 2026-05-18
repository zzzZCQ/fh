# -*- coding: utf-8 -*-
"""添加客户微信名字段到customer_follow_up表"""
from models import db

def migrate():
    """执行数据库迁移"""
    from sqlalchemy import text
    
    # 检查字段是否已存在
    result = db.session.execute(text("PRAGMA table_info([customer_follow_up])"))
    columns = [row[1] for row in result.fetchall()]
    
    if 'customer_wechat' not in columns:
        db.session.execute(text("ALTER TABLE [customer_follow_up] ADD COLUMN customer_wechat VARCHAR(100)"))
        db.session.commit()
        print("已添加 customer_wechat 字段到 customer_follow_up 表")
    else:
        print("customer_wechat 字段已存在")

if __name__ == '__main__':
    from app import app
    with app.app_context():
        migrate()
