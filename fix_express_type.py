# -*- coding: utf-8 -*-
"""检查快递类型的脚本"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Order


def check_express():
    with app.app_context():
        # 查询有运单号但没有快递类型的订单
        orders = Order.query.filter(
            Order.tracking_number.isnot(None),
            Order.tracking_number != '',
            Order.tracking_number != '0',
            (Order.express_type.is_(None) | (Order.express_type == ''))
        ).all()
        
        print(f"找到 {len(orders)} 个有运单号但无快递类型的订单")
        
        if not orders:
            print("没有需要修复的订单")
            return
        
        print("-" * 80)
        
        # 假设默认是顺丰
        fixed_count = 0
        
        for order in orders:
            print(f"ID={order.id}, 客户={order.customer_name}, 单号={repr(order.tracking_number)}, 快递={repr(order.express_type)}")
            
            # 设为顺丰
            order.express_type = '顺丰'
            
            # 如果是主品，物流状态设为已发货
            fixed_count += 1
        
        if fixed_count > 0:
            db.session.commit()
            print(f"\n修复完成！共更新了 {fixed_count} 个订单的快递类型为「顺丰」")
        

if __name__ == '__main__':
    check_express()
