# -*- coding: utf-8 -*-
"""检查行为轨迹数据"""
import os

os.environ.setdefault('FLASK_APP', 'app.py')

from app import app
from models import db, BehaviorTrackingRecord

with app.app_context():
    # 查询所有不重复的日期
    dates = db.session.query(
        BehaviorTrackingRecord.month,
        BehaviorTrackingRecord.day
    ).distinct().order_by(BehaviorTrackingRecord.month, BehaviorTrackingRecord.day).all()
    
    print("数据库中的日期：")
    for d in dates:
        print(f"  {d.month}月{d.day}日")
    
    # 查询0526的数据
    records_0526 = BehaviorTrackingRecord.query.filter_by(month=5, day=26).all()
    print(f"\n5月26日的记录数: {len(records_0526)}")
    
    if records_0526:
        print("前5条记录：")
        for r in records_0526[:5]:
            print(f"  user_id={r.user_id}, nickname={r.nickname}, play_status={r.play_status}")
