"""数据库迁移脚本：添加SCRM系统表"""
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import WecomAccount, WecomCustomer


def migrate():
    """执行迁移"""
    with app.app_context():
        try:
            # 创建表
            db.create_all()
            print("✅ 数据库表创建/更新成功！")
            
            # 检查新表是否创建成功
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            
            tables = inspector.get_table_names()
            print(f"\n当前数据库表: {tables}")
            
            if 'wecom_account' in tables and 'wecom_customer' in tables:
                print("✅ SCRM系统表创建成功！")
            else:
                print("⚠️  警告：未找到预期的表")
                
        except Exception as e:
            print(f"❌ 迁移失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True


if __name__ == "__main__":
    print("开始数据库迁移...")
    success = migrate()
    
    if success:
        print("\n✅ 迁移完成！")
    else:
        print("\n❌ 迁移失败！")
        sys.exit(1)
