# -*- coding: utf-8 -*-
"""添加物流异常字段到数据库"""
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
    # 连接数据库
    print("正在连接数据库...")
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor()
    
    # 检查字段是否已存在
    cursor.execute("DESCRIBE `order`")
    columns = [row[0] for row in cursor.fetchall()]
    
    sql_statements = []
    
    if 'logistics_warning' not in columns:
        sql_statements.append("ALTER TABLE `order` ADD COLUMN `logistics_warning` TINYINT(1) DEFAULT 0 COMMENT '是否有物流异常' AFTER `sign_time`")
        print("✓ 添加 logistics_warning 字段")
    else:
        print("⚠ logistics_warning 字段已存在")
    
    if 'logistics_warning_remark' not in columns:
        sql_statements.append("ALTER TABLE `order` ADD COLUMN `logistics_warning_remark` TEXT COMMENT '物流异常备注' AFTER `logistics_warning`")
        print("✓ 添加 logistics_warning_remark 字段")
    else:
        print("⚠ logistics_warning_remark 字段已存在")
    
    # 执行SQL
    for sql in sql_statements:
        cursor.execute(sql)
        print(f"执行: {sql}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    if sql_statements:
        print("\n✅ 数据库字段添加成功！")
    else:
        print("\n⚠ 所有字段已存在，无需添加")
    
except Exception as e:
    print(f"❌ 错误: {e}")
