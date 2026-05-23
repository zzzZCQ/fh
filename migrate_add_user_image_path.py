# -*- coding: utf-8 -*-
"""数据库迁移脚本 - 为BroadcastNotification添加user_image_path字段"""
import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), 'notification_system.db')
    
    if not os.path.exists(db_path):
        print("数据库文件不存在，无需迁移")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查列是否已存在
        cursor.execute("PRAGMA table_info(broadcast_notification)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'user_image_path' not in columns:
            print("正在添加 user_image_path 字段...")
            cursor.execute("ALTER TABLE broadcast_notification ADD COLUMN user_image_path VARCHAR(500)")
            conn.commit()
            print("迁移成功！")
        else:
            print("字段已存在，无需迁移")
    
    except Exception as e:
        print(f"迁移失败: {e}")
        conn.rollback()
    
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
