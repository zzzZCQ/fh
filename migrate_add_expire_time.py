# -*- coding: utf-8 -*-
"""迁移脚本：添加 category.expire_time 字段"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db

def migrate():
    """添加 category 表的 expire_time 字段"""
    with app.app_context():
        # 检查字段是否已存在
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('category')]
        
        if 'expire_time' not in columns:
            # 添加字段
            db.session.execute(db.text('ALTER TABLE category ADD COLUMN expire_time DATETIME'))
            db.session.commit()
            print('✓ 成功添加 expire_time 字段到 category 表')
        else:
            print('ℹ expire_time 字段已存在，无需迁移')

if __name__ == '__main__':
    migrate()
