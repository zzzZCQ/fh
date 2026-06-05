#!/usr/bin/env python3
"""修复邵玉萍的订单"""

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
cursor = conn.cursor()

print("开始修复邵玉萍的固本回元口服液（0526）订单...")
print("-" * 80)

# 更新订单
sql = """
    UPDATE `order`
    SET status = 'submitted',
        logistics_status = NULL,
        tracking_number = NULL
    WHERE customer_name = '邵玉萍'
    AND category = '固本回元口服液（0526）'
"""

cursor.execute(sql)
conn.commit()

print(f"已更新 {cursor.rowcount} 条订单")

# 验证结果
cursor.execute("""
    SELECT id, category, status, logistics_status, tracking_number
    FROM `order`
    WHERE customer_name = '邵玉萍'
    AND category = '固本回元口服液（0526）'
""")
result = cursor.fetchone()

print("\n修复后的订单状态:")
print("-" * 80)
print(f"ID: {result[0]}")
print(f"类别: {result[1]}")
print(f"status: {result[2]}")
print(f"logistics_status: {result[3]}")
print(f"tracking_number: {result[4]}")

conn.close()
print("\n修复完成！")
