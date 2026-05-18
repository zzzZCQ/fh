# -*- coding: utf-8 -*-
"""迁移脚本：添加用户广播权限字段"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'delivery.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # 检查字段是否已存在
    cursor.execute("PRAGMA table_info(user)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'can_broadcast' not in columns:
        print("添加 can_broadcast 字段到 user 表...")
        cursor.execute("ALTER TABLE user ADD COLUMN can_broadcast BOOLEAN DEFAULT 0")
        conn.commit()
        print("字段添加成功！")
    else:
        print("can_broadcast 字段已存在，无需添加。")

except Exception as e:
    print(f"迁移失败：{e}")
    conn.rollback()
finally:
    conn.close()
