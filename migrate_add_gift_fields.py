# -*- coding: utf-8 -*-
"""迁移脚本：添加 category.is_gift 和 category.related_main_product_id 字段"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db

def migrate():
    """添加 category 表的 is_gift 和 related_main_product_id 字段"""
    with app.app_context():
        # 检查字段是否已存在
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('category')]
        
        # 添加 is_gift 字段
        if 'is_gift' not in columns:
            db.session.execute(db.text('ALTER TABLE category ADD COLUMN is_gift BOOLEAN DEFAULT 0'))
            db.session.commit()
            print('✓ 成功添加 is_gift 字段到 category 表')
        else:
            print('ℹ is_gift 字段已存在，无需迁移')
        
        # 添加 related_main_product_id 字段
        if 'related_main_product_id' not in columns:
            db.session.execute(db.text('ALTER TABLE category ADD COLUMN related_main_product_id INT'))
            db.session.commit()
            print('✓ 成功添加 related_main_product_id 字段到 category 表')
        else:
            print('ℹ related_main_product_id 字段已存在，无需迁移')

if __name__ == '__main__':
    migrate()
