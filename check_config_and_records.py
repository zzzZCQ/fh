# -*- coding: utf-8 -*-
"""检查通话录音配置和昨天的记录"""
from app import app
from wework_partition import get_partition_model
from datetime import datetime, date, timedelta
from models import User, db
from sqlalchemy import text

with app.app_context():
    print('检查通话录音配置状态')
    print('=' * 60)
    
    # 查询配置
    try:
        result = db.session.execute(text("SELECT config_key, config_value FROM app_config WHERE config_key='call_recording_enabled'"))
        row = result.fetchone()
        if row:
            print(f'配置键: {row[0]}')
            print(f'配置值: {row[1]}')
            enabled = str(row[1]).lower() == 'true'
            print(f'当前状态: {"✅ 已启用" if enabled else "❌ 已停用"}')
        else:
            print('❌ 数据库中未找到该配置')
    except Exception as e:
        print(f'查询数据库配置出错: {e}')
        import traceback
        traceback.print_exc()
    
    print()
    
    # 查询昨天的记录
    yesterday = date.today() - timedelta(days=1)
    print(f'查询昨天的记录: {yesterday.strftime("%Y-%m-%d")}')
    print('-' * 60)
    
    try:
        PartitionModel = get_partition_model(yesterday)
        records = PartitionModel.query.order_by(PartitionModel.call_start_time.desc()).all()
        
        print(f'共找到 {len(records)} 条通话记录\n')
        
        if records:
            for i, rec in enumerate(records[:10], 1):
                start_time = rec.call_start_time.strftime('%H:%M:%S') if rec.call_start_time else '-'
                end_time = rec.call_end_time.strftime('%H:%M:%S') if rec.call_end_time else '-'
                
                duration = '-'
                if rec.call_duration_seconds:
                    mins, secs = divmod(rec.call_duration_seconds, 60)
                    if mins > 0:
                        duration = f'{mins}分{secs}秒'
                    else:
                        duration = f'{secs}秒'
                
                status = '已完成' if rec.status == 'completed' else '进行中'
                
                # 获取上传者姓名
                uploader_name = '未知'
                if rec.uploader_id:
                    user = User.query.get(rec.uploader_id)
                    if user:
                        uploader_name = user.name or user.username
                
                print(f'{i}. [{start_time} ~ {end_time}] {rec.user_name}')
                print(f'   时长: {duration} | 状态: {status} | 上传者: {uploader_name}')
                print()
            
            if len(records) > 10:
                print(f'... 还有 {len(records) - 10} 条记录')
            
    except Exception as e:
        print(f'查询出错: {e}')
        import traceback
        traceback.print_exc()
