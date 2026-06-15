# -*- coding: utf-8 -*-
"""创建 knowledge_entry_vote 表"""
from app import app
from models import db

with app.app_context():
    db.create_all()
    print('knowledge_entry_vote table created successfully')
