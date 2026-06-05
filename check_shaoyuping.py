#!/usr/bin/env python3
"""查询邵玉萍的订单状态"""

import pymysql

DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'fh',
    'password': '123456',
    'database': 'delivery_db',
    'charset': 'utf8mb4'
}

conn = pymysql.connect(**DB_CONFIG)
cursor = conn.cursor(pymysql.cursors.DictCursor)

print("邵玉萍的所有订单:")
print("-" * 80)

cursor.execute("""
    SELECT id, category, status, group_name, customer_name, export_marked, tracking_number, logistics_status
    FROM `order`
    WHERE customer_name = '邵玉萍'
    ORDER BY id DESC
""")
orders = cursor.fetchall()

for order in orders:
    print(f"ID: {order['id']} | 类别: {repr(order['category'])} | status: {repr(order['status'])} | logistics_status: {repr(order['logistics_status'])} | 快递单号: {repr(order['tracking_number'])}")

conn.close()
