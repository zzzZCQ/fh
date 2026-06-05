# -*- coding: utf-8 -*-
"""
修复订单状态的脚本
处理：logistics_status=已发货 但 status=submitted 的订单
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Order


def fix_logistics_status():
    with app.app_context():
        # 查询需要修复的订单
        orders_to_fix = Order.query.filter(
            Order.logistics_status == '已发货',
            Order.status == 'submitted'
        ).all()
        
        print(f"找到 {len(orders_to_fix)} 个需要修复的订单")
        print("-" * 80)
        
        fixed_count = 0
        
        for order in orders_to_fix:
            print(f"ID={order.id}, 客户={order.customer_name}, 单号={repr(order.tracking_number)}")
            
            # 改为已发货状态
            order.status = 'shipped'
            fixed_count += 1
        
        # 提交到数据库
        if fixed_count > 0:
            db.session.commit()
            print(f"\n修复完成！共更新了 {fixed_count} 个订单状态为 shipped")
        else:
            print("\n没有需要修复的订单")
        

if __name__ == '__main__':
    fix_logistics_status()
