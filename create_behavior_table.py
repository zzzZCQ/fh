# -*- coding: utf-8 -*-
"""添加行为轨迹记录表"""
import pymysql

# 数据库连接配置
db_config = {
    'host': 'localhost',
    'port': 3306,
    'user': 'fh',
    'password': '123456',
    'database': 'delivery_db',
    'charset': 'utf8mb4'
}

try:
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    
    # 检查表是否已存在
    cursor.execute("SHOW TABLES LIKE 'behavior_tracking_record'")
    if cursor.fetchone():
        print("⚠ 表 behavior_tracking_record 已存在")
    else:
        # 创建表
        sql = """
        CREATE TABLE `behavior_tracking_record` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `user_id` INT NOT NULL,
            `nickname` VARCHAR(200) NOT NULL,
            `month` INT NOT NULL,
            `day` INT NOT NULL,
            `play_status` INT NOT NULL DEFAULT 3,
            `call_duration_seconds` INT DEFAULT 0,
            `play_order` INT DEFAULT 0,
            `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON DELETE CASCADE,
            INDEX `idx_bt_user_nickname` (`user_id`, `nickname`),
            INDEX `idx_bt_date` (`month`, `day`),
            INDEX `idx_bt_user_date` (`user_id`, `month`, `day`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        cursor.execute(sql)
        print("✅ 表 behavior_tracking_record 创建成功")
    
    conn.commit()
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ 错误: {e}")
