# -*- coding: utf-8 -*-
"""检查订单状态的脚本"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Order


def check_orders():
    with app.app_context():
        # 查询所有订单，查看状态
        orders = Order.query.filter(Order.tracking_number.isnot(None)).all()
        
        print(f"共有 {len(orders)} 个有运单号的订单")
        print("-" * 80)
        
        submitted_count = 0
        shipped_count = 0
        other_count = 0
        
        for order in orders:
            if order.status == 'submitted':
                submitted_count += 1
                print(f"[待发货] ID={order.id}, 客户={order.customer_name}, 单号={repr(order.tracking_number)}, 物流={repr(order.logistics_status)}, 快递={repr(order.express_type)}")
            elif order.status == 'shipped':
                shipped_count += 1
            else:
                other_count += 1
        
        print("-" * 80)
        print(f"统计: 待发货={submitted_count}, 已发货={shipped_count}, 其他={other_count}")
        

if __name__ == '__main__':
    check_orders()
