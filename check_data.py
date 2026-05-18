# -*- coding: utf-8 -*-
"""检查数据库订单数据"""

import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'delivery.db')

if not os.path.exists(db_path):
    db_path = os.path.join(os.path.dirname(__file__), 'fh.db')

print(f'Database: {db_path}')
print()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查订单数量
cursor.execute("SELECT COUNT(*) FROM [order]")
count = cursor.fetchone()[0]
print(f'Order count: {count}')
print()

# 检查表结构
cursor.execute("PRAGMA table_info([order])")
columns = cursor.fetchall()
print(f'Order table columns ({len(columns)}):')
for col in columns:
    print(f'  {col[1]} ({col[2]})')
print()

# 列出最近的订单
if count > 0:
    cursor.execute("SELECT id, group_name, customer_name, status, create_time FROM [order] ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    print('Recent orders:')
    for row in rows:
        print(f'  ID={row[0]}, Group={row[1]}, Customer={row[2]}, Status={row[3]}, Time={row[4]}')

conn.close()
