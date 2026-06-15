"""为 attendance_config 表添加新字段（安全增量迁移，不删数据）。
直接运行: python migrate_attendance_config.py
"""
import sys
from app import app
from models import db


def column_exists(table_name, column_name):
    result = db.session.execute(
        db.text(f"SHOW COLUMNS FROM `{table_name}` LIKE :col"),
        {'col': column_name}
    ).fetchall()
    return len(result) > 0


def add_column_if_missing(table_name, column_name, column_def):
    """安全地添加列：存在则跳过，不存在则 ALTER TABLE ADD。"""
    if column_exists(table_name, column_name):
        print(f'  [SKIP]  {table_name}.{column_name} 已存在')
        return
    sql = f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {column_def}"
    print(f'  [ADD ]  {sql}')
    db.session.execute(db.text(sql))
    db.session.commit()


with app.app_context():
    print('>>> 检查 attendance_config 表字段...')

    # 如果表不存在，先尝试用 create_all 建它（极端情况）
    table_result = db.session.execute(
        db.text("SHOW TABLES LIKE 'attendance_config'")
    ).fetchall()
    if not table_result:
        print('表不存在，尝试 db.create_all() 创建')
        db.create_all()
    else:
        print('表已存在，开始增量检查字段')

    columns_to_add = [
        # (列名, 列定义)
        ('applicable_group_ids', 'TEXT DEFAULT NULL'),
        ('commission_rule_type', 'VARCHAR(20) DEFAULT NULL'),
        ('commission_fixed_rate', 'FLOAT DEFAULT 0'),
        ('commission_tiered_config', 'TEXT DEFAULT NULL'),
    ]

    for col_name, col_def in columns_to_add:
        add_column_if_missing('attendance_config', col_name, col_def)

    print('>>> 迁移完成。当前字段：')
    cols = db.session.execute(db.text("SHOW COLUMNS FROM attendance_config")).fetchall()
    for c in cols:
        print(f'  - {c[0]} ({c[1]})')

print('OK')
