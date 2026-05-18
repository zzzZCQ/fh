# -*- coding: utf-8 -*-
"""检查数据库中 customer_wechat 字段状态"""

import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'delivery.db')

if not os.path.exists(db_path):
    db_path = os.path.join(os.path.dirname(__file__), 'fh.db')

print(f'Database: {db_path}')
print()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info([order])")
columns = cursor.fetchall()

print('Order table columns:')
for col in columns:
    marker = ' <<<< NEW' if col[1] == 'customer_wechat' else ''
    print(f'  {col[1]} ({col[2]}){marker}')

has_field = any(col[1] == 'customer_wechat' for col in columns)
print()
print(f'customer_wechat exists: {has_field}')

conn.close()
