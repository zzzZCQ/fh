# -*- coding: utf-8 -*-
"""查询最近几天的通话记录"""
from app import app
from wework_partition import get_partition_model, get_available_dates
from datetime import datetime, date, timedelta
from models import User

with app.app_context():
    print('查询最近几天的通话记录')
    print('=' * 60)
    
    try:
        dates = get_available_dates()
        print(f'可用日期: {len(dates)} 个')
        for d in dates:
            print(f'  - {d.strftime("%Y-%m-%d")}')
        print()
        
        if not dates:
            print('暂无任何通话记录')
        else:
            # 查询最新的日期
            for target_date in dates[:1]:
                print(f'\n查询日期: {target_date.strftime("%Y-%m-%d")}')
                print('-' * 60)
                
                PartitionModel = get_partition_model(target_date)
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
                        
                        # 获取上传者姓名
                        uploader_name = '未知'
                        if rec.uploader_id:
                            user = User.query.get(rec.uploader_id)
                            if user:
                                uploader_name = user.name or user.username
                        
                        print(f'{i}. [{start_time} ~ {end_time}] {rec.user_name}')
                        print(f'   时长: {duration} | 状态: {status} | 上传者: {uploader_name}')
                        print()
            
    except Exception as e:
        print(f'查询出错: {e}')
        import traceback
        traceback.print_exc()
