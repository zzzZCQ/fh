# -*- coding: utf-8 -*-
"""检查订单415的类别是否是主品"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Order, Category


def check_order_415():
    with app.app_context():
        order = Order.query.get(415)
        
        if order:
            print(f"订单ID={order.id}")
            print(f"  category={repr(order.category)}")
            
            category = Category.query.filter_by(name=order.category).first()
            if category:
                print(f"  是主品: {category.is_main_product}")
            else:
                print("  类别不存在！")
        

if __name__ == '__main__':
    check_order_415()
