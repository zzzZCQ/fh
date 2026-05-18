# -*- coding: utf-8 -*-
"""添加 customer_wechat 字段到 order 表"""

import sqlite3
import os

# 直接使用SQLite，不通过Flask-SQLAlchemy
db_path = os.path.join(os.path.dirname(__file__), 'instance', 'delivery.db')

if not os.path.exists(db_path):
    db_path = os.path.join(os.path.dirname(__file__), 'fh.db')

print(f'Using database: {db_path}')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查表结构
cursor.execute("PRAGMA table_info([order])")
columns = cursor.fetchall()

print('\nCurrent columns:')
for col in columns:
    print(f'  {col[1]} ({col[2]})')

# 检查是否已有 customer_wechat
has_field = any(col[1] == 'customer_wechat' for col in columns)

if not has_field:
    print('\nAdding customer_wechat column...')
    cursor.execute('ALTER TABLE [order] ADD COLUMN customer_wechat VARCHAR(50)')
    conn.commit()
    print('Done!')
    
    # 验证添加成功
    cursor.execute("PRAGMA table_info([order])")
    columns = cursor.fetchall()
    print('\nUpdated columns:')
    for col in columns:
        if col[1] == 'customer_wechat':
            print(f'  ✓ {col[1]} ({col[2]}) - ADDED SUCCESSFULLY')
        else:
            print(f'  {col[1]} ({col[2]})')
else:
    print('\ncustomer_wechat already exists')

conn.close()
