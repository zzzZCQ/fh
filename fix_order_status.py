# -*- coding: utf-8 -*-
"""
批量修复订单状态的脚本
修复：有运单号但状态仍是 submitted 的订单，改为 shipped
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Order, Category


def fix_order_status():
    with app.app_context():
        # 查询需要修复的订单
        # 条件：有运单号、状态是 submitted
        orders_to_fix = Order.query.filter(
            Order.tracking_number.isnot(None),
            Order.tracking_number != '',
            Order.tracking_number != '0',
            Order.status == 'submitted'
        ).all()
        
        print(f"找到 {len(orders_to_fix)} 个需要修复的订单")
        
        if not orders_to_fix:
            print("没有需要修复的订单")
            return
        
        fixed_count = 0
        
        for order in orders_to_fix:
            print(f"  订单ID={order.id}: 客户={order.customer_name}, 单号={order.tracking_number}, 类别={order.category}")
            
            # 改为已发货状态
            order.status = 'shipped'
            
            # 处理物流状态
            category = Category.query.filter_by(name=order.category).first()
            
            if category and not category.is_main_product:
                # 非主品：发货即签收
                order.logistics_status = '已签收'
                print(f"    → 非主品，标记为已签收")
            elif order.express_type == '顺丰':
                # 主品且顺丰：标记为已发货
                order.logistics_status = '已发货'
                print(f"    → 主品+顺丰，标记为已发货")
            else:
                # 其他情况：标记为已发货
                order.logistics_status = '已发货'
                print(f"    → 标记为已发货")
            
            fixed_count += 1
        
        # 提交到数据库
        if fixed_count > 0:
            db.session.commit()
            print(f"\n修复完成！共更新了 {fixed_count} 个订单")
        else:
            print("\n没有需要修复的订单")


if __name__ == '__main__':
    fix_order_status()
