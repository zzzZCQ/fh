# -*- coding: utf-8 -*-
"""
回滚刚才修改的订单状态
把刚才修改的33个订单状态从shipped改回submitted
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Order


def rollback_orders():
    order_ids = [64, 69, 245, 246, 247, 248, 249, 250, 251, 252, 
                 253, 254, 255, 256, 257, 258, 259, 260, 261, 262,
                 263, 264, 265, 266, 267, 269, 270, 271, 376, 416,
                 418, 419, 420]
    
    with app.app_context():
        print(f"准备回滚 {len(order_ids)} 个订单...")
        print("-" * 80)
        
        rollback_count = 0
        
        for order_id in order_ids:
            order = Order.query.get(order_id)
            if order:
                print(f"ID={order.id}, 客户={order.customer_name}, 当前状态={order.status} → 改为 submitted")
                order.status = 'submitted'
                rollback_count += 1
        
        if rollback_count > 0:
            db.session.commit()
            print(f"\n回滚完成！共回滚了 {rollback_count} 个订单")
        else:
            print("\n没有需要回滚的订单")
        

if __name__ == '__main__':
    rollback_orders()
