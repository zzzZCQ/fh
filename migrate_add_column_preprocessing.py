"""数据库迁移脚本：为 import_template 表添加 column_preprocessing 字段"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from sqlalchemy import text


def migrate():
    """执行迁移"""
    with app.app_context():
        try:
            # 检查字段是否已存在
            from sqlalchemy import inspect
            inspector = inspect(db.engine)

            columns = [col['name'] for col in inspector.get_columns('import_template')]
            print(f"当前 import_template 表字段: {columns}")

            if 'column_preprocessing' in columns:
                print("✅ column_preprocessing 字段已存在，跳过")
                return True

            # 添加字段（TEXT 类型不能有默认值，分两步执行）
            db.session.execute(text(
                "ALTER TABLE import_template ADD COLUMN column_preprocessing TEXT"
            ))
            db.session.commit()
            print("✅ column_preprocessing 字段添加成功！")

            # 验证
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('import_template')]
            print(f"更新后字段: {columns}")

        except Exception as e:
            db.session.rollback()
            print(f"❌ 迁移失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    return True


if __name__ == '__main__':
    if migrate():
        print("\n迁移完成！")
    else:
        print("\n迁移失败，请检查错误")
        sys.exit(1)
