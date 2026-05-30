# -*- coding: utf-8 -*-
"""添加备注字段到数据库"""
import os
import sys

# 设置环境变量
os.environ.setdefault('FLASK_APP', 'app.py')

from app import app
from models import db

with app.app_context():
    try:
        db.session.execute('ALTER TABLE behavior_tracking_record ADD COLUMN note TEXT')
        db.session.commit()
        print('字段添加成功')
    except Exception as e:
        print(f'错误: {e}')
