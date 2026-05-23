"""
企业微信通话记录迁移脚本
将旧表 wework_call_record 的数据按日期迁移到分表
"""
from datetime import datetime
from models import db, WeworkCallRecord, _now_bj
from wework_partition import get_partition_model


def migrate_data():
    """迁移旧数据到分表"""
    print('[迁移] 开始迁移数据...')
    
    # 获取所有旧数据
    all_records = WeworkCallRecord.query.order_by(WeworkCallRecord.call_start_time).all()
    print(f'[迁移] 找到 {len(all_records)} 条记录')
    
    migrated_count = 0
    failed_count = 0
    
    for record in all_records:
        try:
            # 获取分表模型
            call_date = record.call_start_time.date()
            PartitionModel = get_partition_model(call_date)
            
            # 检查分表中是否已有该记录
            existing = PartitionModel.query.filter_by(
                user_name=record.user_name,
                call_start_time=record.call_start_time
            ).first()
            
            if existing:
                continue
            
            # 创建新记录到分表
            new_record = PartitionModel(
                user_name=record.user_name,
                call_start_time=record.call_start_time,
                call_end_time=record.call_end_time,
                call_duration_seconds=record.call_duration_seconds,
                status=record.status,
                uploader_id=record.uploader_id,
                upload_time=record.upload_time,
                create_time=record.create_time
            )
            db.session.add(new_record)
            db.session.commit()
            migrated_count += 1
            
            if migrated_count % 100 == 0:
                print(f'[迁移] 已迁移 {migrated_count} 条记录...')
                
        except Exception as e:
            failed_count += 1
            db.session.rollback()
            print(f'[迁移] 记录 {record.id} 迁移失败: {e}')
            continue
    
    print(f'[迁移] 完成! 成功迁移 {migrated_count} 条, 失败 {failed_count} 条')
    return migrated_count, failed_count


if __name__ == '__main__':
    # 确保应用已初始化
    try:
        from app import app
        with app.app_context():
            migrate_data()
    except ImportError:
        print('[迁移] 请确保在项目根目录下运行')
