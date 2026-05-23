# -*- coding: utf-8 -*-
"""迁移脚本：为Category模型添加unit_price字段"""
import sqlite3
import os

db_path = 'instance/delivery.db'

if not os.path.exists(db_path):
    print(f"数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # 检查字段是否已存在
    cursor.execute("PRAGMA table_info(category)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'unit_price' in columns:
        print("字段 unit_price 已存在，无需迁移")
    else:
        # 添加unit_price字段
        cursor.execute("ALTER TABLE category ADD COLUMN unit_price REAL DEFAULT 0.0")
        conn.commit()
        print("成功添加 unit_price 字段")
        
except Exception as e:
    print(f"迁移失败: {e}")
    conn.rollback()
finally:
    conn.close()
