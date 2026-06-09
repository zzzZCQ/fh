"""数据库迁移脚本：为 import_template 表添加 skip_rows 字段"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text


def migrate():
    with app.app_context():
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('import_template')]
            print(f"当前字段: {columns}")

            if 'skip_rows' in columns:
                print("✅ skip_rows 字段已存在")
                return True

            db.session.execute(text(
                "ALTER TABLE import_template ADD COLUMN skip_rows INT DEFAULT 0"
            ))
            db.session.commit()
            print("✅ skip_rows 字段添加成功！")

        except Exception as e:
            db.session.rollback()
            print(f"❌ 迁移失败: {e}")
            return False
    return True


if __name__ == '__main__':
    if migrate():
        print("迁移完成！")
    else:
        print("迁移失败")
        sys.exit(1)
