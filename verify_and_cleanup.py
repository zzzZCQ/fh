# -*- coding: utf-8 -*-
"""验证数据恢复并清理临时表"""

import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'delivery.db')

print(f'Database: {db_path}')
print()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 验证 order 表
cursor.execute("SELECT COUNT(*) FROM [order]")
order_count = cursor.fetchone()[0]
print(f'order table: {order_count} rows')

cursor.execute("SELECT id, group_name, customer_name, status, create_time FROM [order] ORDER BY id DESC LIMIT 10")
rows = cursor.fetchall()
print('\nRecent orders:')
for row in rows:
    print(f'  ID={row[0]}, Group={row[1]}, Customer={row[2]}, Status={row[3]}, Time={row[4]}')

# 删除临时表
print('\nDropping order_old table...')
cursor.execute("DROP TABLE IF EXISTS [order_old]")
conn.commit()
print('Done!')

conn.close()
