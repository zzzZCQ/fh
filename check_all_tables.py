# -*- coding: utf-8 -*-
"""检查所有表，包括 order_old"""

import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'delivery.db')

if not os.path.exists(db_path):
    db_path = os.path.join(os.path.dirname(__file__), 'fh.db')

print(f'Database: {db_path}')
print()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 列出所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()

print('All tables:')
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM [{t[0]}]")
    count = cursor.fetchone()[0]
    print(f'  {t[0]}: {count} rows')
print()

# 检查 order_old 是否有数据
if any(t[0] == 'order_old' for t in tables):
    print('=== order_old table ===')
    cursor.execute("SELECT COUNT(*) FROM [order_old]")
    old_count = cursor.fetchone()[0]
    print(f'Rows: {old_count}')
    
    if old_count > 0:
        cursor.execute("SELECT id, group_name, customer_name, status FROM [order_old] ORDER BY id DESC LIMIT 10")
        rows = cursor.fetchall()
        print('Recent orders:')
        for row in rows:
            print(f'  ID={row[0]}, Group={row[1]}, Customer={row[2]}, Status={row[3]}')
else:
    print('order_old table not found')

conn.close()
