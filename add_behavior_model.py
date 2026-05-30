# -*- coding: utf-8 -*-
"""添加行为轨迹数据模型到models.py"""
import re

file_path = 'd:/fh/models.py'

# 读取文件
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 检查是否已存在模型
if 'class BehaviorTrackingRecord' in content:
    print("模型已存在，无需添加")
else:
    # 新模型代码
    new_model = '''

class BehaviorTrackingRecord(db.Model):
    """行为轨迹记录模型"""
    __tablename__ = 'behavior_tracking_record'
    __table_args__ = (
        db.Index('idx_bt_user_nickname', 'user_id', 'nickname'),
        db.Index('idx_bt_date', 'month', 'day'),
        db.Index('idx_bt_user_date', 'user_id', 'month', 'day'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nickname = db.Column(db.String(200), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    day = db.Column(db.Integer, nullable=False)
    play_status = db.Column(db.Integer, nullable=False, default=3)
    call_duration_seconds = db.Column(db.Integer, default=0)
    play_order = db.Column(db.Integer, default=0)
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)
    
    user = db.relationship('User', backref=db.backref('behavior_tracking_records', lazy=True))
'''
    
    # 在文件末尾添加
    content += new_model
    
    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 行为轨迹记录模型已添加")
