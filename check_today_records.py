# -*- coding: utf-8 -*-
"""查询今天的通话记录"""
from app import app
from wework_partition import get_partition_model
from datetime import datetime

with app.app_context():
    today = datetime.now()
    print(f'查询日期: {today.strftime("%Y-%m-%d")}')
    print('=' * 60)
    
    try:
        PartitionModel = get_partition_model(today)
        records = PartitionModel.query.order_by(PartitionModel.call_start_time.desc()).all()
        
        print(f'共找到 {len(records)} 条通话记录\n')
        
        if records:
            for i, rec in enumerate(records, 1):
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
                
                print(f'{i}. [{start_time} ~ {end_time}] {rec.user_name}')
                print(f'   时长: {duration} | 状态: {status} | 上传者ID: {rec.uploader_id}')
                print()
        else:
            print('暂无通话记录')
            
    except Exception as e:
        print(f'查询出错: {e}')
        import traceback
        traceback.print_exc()
