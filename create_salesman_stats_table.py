# -*- coding: utf-8 -*-
"""创建业务员每日统计表"""
import os

os.environ.setdefault('FLASK_APP', 'app.py')

from app import app
from models import db

with app.app_context():
    try:
        db.create_all()
        print('表创建成功')
    except Exception as e:
        print(f'错误: {e}')
