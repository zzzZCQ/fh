# -*- coding: utf-8 -*-
"""从 order_old 恢复数据到 order 表"""

import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'delivery.db')

print(f'Database: {db_path}')
print()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查 order_old
cursor.execute("SELECT COUNT(*) FROM [order_old]")
old_count = cursor.fetchone()[0]
print(f'order_old rows: {old_count}')

if old_count == 0:
    print('No data to restore')
else:
    # 获取 order_old 的列
    cursor.execute("PRAGMA table_info([order_old])")
    old_cols = [col[1] for col in cursor.fetchall()]
    print(f'order_old columns: {old_cols}')
    
    # 获取 order 的列
    cursor.execute("PRAGMA table_info([order])")
    order_cols = [col[1] for col in cursor.fetchall()]
    print(f'order columns: {order_cols}')
    
    # 找出共同的列
    common_cols = [c for c in old_cols if c in order_cols]
    print(f'Common columns: {common_cols}')
    
    # 清空 order 表
    print('\nClearing order table...')
    cursor.execute("DELETE FROM [order]")
    
    # 恢复数据
    print('Restoring data from order_old...')
    col_list = ', '.join(common_cols)
    placeholders = ', '.join(['?' for _ in common_cols])
    
    cursor.execute(f"SELECT {col_list} FROM [order_old]")
    rows = cursor.fetchall()
    
    for row in rows:
        cursor.execute(f"INSERT INTO [order] ({col_list}) VALUES ({placeholders})", row)
    
    conn.commit()
    
    # 验证
    cursor.execute("SELECT COUNT(*) FROM [order]")
    new_count = cursor.fetchone()[0]
    print(f'\norder rows after restore: {new_count}')
    
    # 显示恢复的数据
    cursor.execute("SELECT id, group_name, customer_name, status FROM [order] ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    print('\nRecovered orders:')
    for row in rows:
        print(f'  ID={row[0]}, Group={row[1]}, Customer={row[2]}, Status={row[3]}')
    
    # 可选：删除 order_old
    # cursor.execute("DROP TABLE [order_old]")
    # conn.commit()
    # print('\norder_old table dropped')

conn.close()
print('\nDone!')
