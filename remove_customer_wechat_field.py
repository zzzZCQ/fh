# -*- coding: utf-8 -*-
"""从 order 表删除 customer_wechat 字段"""

import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'delivery.db')

if not os.path.exists(db_path):
    db_path = os.path.join(os.path.dirname(__file__), 'fh.db')

print(f'Database: {db_path}')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查字段是否存在
cursor.execute("PRAGMA table_info([order])")
columns = cursor.fetchall()

has_field = any(col[1] == 'customer_wechat' for col in columns)

if not has_field:
    print('customer_wechat column does not exist - nothing to remove')
else:
    print('Removing customer_wechat column...')
    
    # 获取所有列（排除 customer_wechat）
    cols = [col[1] for col in columns if col[1] != 'customer_wechat']
    
    # 重命名旧表
    cursor.execute("ALTER TABLE [order] RENAME TO [order_old]")
    
    # 创建新表（不含 customer_wechat）
    cursor.execute("""
        CREATE TABLE [order] (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name VARCHAR(80) NOT NULL,
            salesman_id INTEGER NOT NULL,
            product_info TEXT NOT NULL,
            category VARCHAR(20) NOT NULL,
            phone VARCHAR(20) NOT NULL,
            address TEXT NOT NULL,
            remark TEXT,
            status VARCHAR(20) DEFAULT 'draft',
            tracking_number VARCHAR(50),
            express_type VARCHAR(20),
            customer_name VARCHAR(80),
            paid_amount VARCHAR(200),
            pay_date DATE,
            collect_amount FLOAT,
            has_gift BOOLEAN DEFAULT 0,
            gift_info VARCHAR(200),
            logistics_status VARCHAR(20) DEFAULT '已发货',
            sign_time DATETIME,
            group_id INTEGER,
            create_time DATETIME,
            update_time DATETIME,
            delete_requested BOOLEAN DEFAULT 0,
            delete_request_time DATETIME,
            export_marked BOOLEAN DEFAULT 0,
            export_mark_time DATETIME,
            FOREIGN KEY (salesman_id) REFERENCES [user] (id),
            FOREIGN KEY (group_id) REFERENCES [group] (id)
        )
    """)
    
    # 复制数据
    col_list = ', '.join(cols)
    cursor.execute(f"INSERT INTO [order] ({col_list}) SELECT {col_list} FROM [order_old]")
    
    # 删除旧表
    cursor.execute("DROP TABLE [order_old]")
    
    conn.commit()
    print('Done!')
    
    # 验证
    cursor.execute("PRAGMA table_info([order])")
    columns = cursor.fetchall()
    print('\nUpdated columns:')
    for col in columns:
        print(f'  {col[1]} ({col[2]})')

conn.close()
