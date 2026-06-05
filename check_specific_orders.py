# -*- coding: utf-8 -*-
"""详细检查订单状态的脚本"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Order


def check_specific_orders():
    order_ids = [420, 419, 418, 64, 416, 376, 271, 253, 254, 252, 247, 250, 249, 248, 266, 270, 269, 251, 263, 246]
    
    with app.app_context():
        print("=" * 80)
        print("检查指定订单")
        print("=" * 80)
        
        for order_id in order_ids:
            order = Order.query.get(order_id)
            if order:
                print(f"ID={order.id}")
                print(f"  status={repr(order.status)}, logistics_status={repr(order.logistics_status)}")
                print(f"  express_type={repr(order.express_type)}, tracking_number={repr(order.tracking_number)}")
                print(f"  category={repr(order.category)}, customer={repr(order.customer_name)}")
            else:
                print(f"ID={order_id} 不存在")
            print("-" * 80)
        

if __name__ == '__main__':
    check_specific_orders()
