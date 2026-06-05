#!/usr/bin/env python3
"""查询数据库里的订单类别情况"""

import pymysql

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'fh',
    'password': '123456',
    'database': 'delivery_db',
    'charset': 'utf8mb4'
}

def check_orders():
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        print("=" * 80)
        print("查询订单类别分布")
        print("=" * 80)
        
        # 查询所有类别统计
        cursor.execute("""
            SELECT category, status, export_marked, COUNT(*) as count
            FROM `order`
            GROUP BY category, status, export_marked
            ORDER BY category, status
        """)
        results = cursor.fetchall()
        
        print("\n各类别订单统计:")
        print("-" * 80)
        for row in results:
            print(f"类别: {repr(row['category'])} | 状态: {repr(row['status'])} | export_marked: {row['export_marked']} | 数量: {row['count']}")
        
        print("\n" + "=" * 80)
        print("查询所有类别列表")
        print("=" * 80)
        
        cursor.execute("""
            SELECT DISTINCT category
            FROM `order`
            ORDER BY category
        """)
        categories = cursor.fetchall()
        
        print("\n数据库中存在的订单类别:")
        print("-" * 80)
        for cat in categories:
            print(f"  {repr(cat['category'])}")
        
        print("\n" + "=" * 80)
        print("查询固本类别的详细订单(前20条)")
        print("=" * 80)
        
        cursor.execute("""
            SELECT id, category, status, group_name, customer_name, export_marked, tracking_number
            FROM `order`
            WHERE category LIKE '%固本%'
            ORDER BY id DESC
            LIMIT 20
        """)
        orders = cursor.fetchall()
        
        print("\n固本类别订单详情:")
        print("-" * 80)
        for order in orders:
            print(f"ID: {order['id']} | 类别: {repr(order['category'])} | 状态: {repr(order['status'])} | export_marked: {order['export_marked']} | 组别: {repr(order['group_name'])} | 客户: {repr(order['customer_name'])} | 快递单号: {repr(order['tracking_number'])}")
        
        print("\n" + "=" * 80)
        print("查询完成!")
        print("=" * 80)
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

def check_shaoyuping():
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        print("\n" + "=" * 80)
        print("查询邵玉萍的订单")
        print("=" * 80)
        
        cursor.execute("""
            SELECT id, category, status, group_name, customer_name, salesman_id, export_marked, tracking_number
            FROM `order`
            WHERE customer_name LIKE '%邵玉萍%'
        """)
        orders = cursor.fetchall()
        
        print("\n邵玉萍的订单:")
        print("-" * 80)
        for order in orders:
            print(f"ID: {order['id']} | 类别: {repr(order['category'])} | 状态: {repr(order['status'])} | export_marked: {order['export_marked']} | 组别: {repr(order['group_name'])} | 客户: {repr(order['customer_name'])} | 快递单号: {repr(order['tracking_number'])}")
        
        print("\n" + "=" * 80)
        print("查询是否有同名客户")
        print("=" * 80)
        
        cursor.execute("""
            SELECT customer_name, COUNT(*) as count
            FROM `order`
            WHERE category LIKE '%固本%'
            GROUP BY customer_name
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        duplicates = cursor.fetchall()
        
        print("\n同名客户（固本类别）:")
        print("-" * 80)
        for dup in duplicates:
            print(f"客户名: {repr(dup['customer_name'])} | 数量: {dup['count']}")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_orders()
    check_shaoyuping()
