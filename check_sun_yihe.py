# -*- coding: utf-8 -*-
"""查询孙义和的订单"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Order


def check_sun_yihe():
    with app.app_context():
        # 搜索客户名
        orders = Order.query.filter(Order.customer_name.like('%孙义和%')).all()
        
        print(f"找到 {len(orders)} 个相关订单")
        print("=" * 80)
        
        for order in orders:
            print(f"ID={order.id}")
            print(f"  客户={repr(order.customer_name)}, 组别={repr(order.group_name)}")
            print(f"  status={repr(order.status)}, logistics_status={repr(order.logistics_status)}")
            print(f"  express_type={repr(order.express_type)}, tracking={repr(order.tracking_number)}")
            print(f"  category={repr(order.category)}")
            print("-" * 80)
        

if __name__ == '__main__':
    check_sun_yihe()
