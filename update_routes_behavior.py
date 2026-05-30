# -*- coding: utf-8 -*-
"""修改routes_behavior.py，添加数据库保存功能"""

file_path = 'd:/fh/routes_behavior.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 添加数据库模型导入（在文件开头的导入部分）
old_import = 'from helpers import role_required, get_unread_count'
new_import = '''from helpers import role_required, get_unread_count
from models import db, BehaviorTrackingRecord'''

content = content.replace(old_import, new_import)

# 2. 在保存Excel之后，添加数据库保存逻辑
old_save = '''    # 保存已处理日期
    processed_dates.update(new_processed_dates)
    with open(PROCESSED_FILE, 'w', encoding='utf-8') as f:
        for d in sorted(processed_dates):
            f.write(f"{d}\\n")

    # 保存文件
    wb.save(ORIGINAL_FILE)
    wb.close()

    return f"处理完成！填充了 {len(target_titles)} 个日期列，共 {len(user_rows_sorted)} 个用户，已按完播次数降序排序"'''

new_save = '''    # 保存已处理日期
    processed_dates.update(new_processed_dates)
    with open(PROCESSED_FILE, 'w', encoding='utf-8') as f:
        for d in sorted(processed_dates):
            f.write(f"{d}\\n")

    # 保存数据到数据库
    saved_count = 0
    try:
        # 先删除该用户当月的旧数据
        for title_num in sorted(target_titles):
            delta_days = title_num - ref_title_num
            target_date = ref_date + timedelta(days=delta_days)
            month = target_date.month
            day = target_date.day
            
            # 删除该用户的旧数据
            BehaviorTrackingRecord.query.filter_by(
                user_id=user_id,
                month=month,
                day=day
            ).delete()
        
        # 保存新数据
        for idx, user_info in enumerate(user_rows_sorted):
            nick = user_info['nick']
            play_count = user_info['play_count']
            
            for title_num in sorted(target_titles):
                delta_days = title_num - ref_title_num
                target_date = ref_date + timedelta(days=delta_days)
                month = target_date.month
                day = target_date.day
                
                fill_value = all_user_data.get(nick, {}).get(title_num, 3)
                call_duration = all_call_records.get(title_num, {}).get(nick, 0)
                
                record = BehaviorTrackingRecord(
                    user_id=user_id,
                    nickname=nick,
                    month=month,
                    day=day,
                    play_status=fill_value,
                    call_duration_seconds=call_duration,
                    play_order=play_count
                )
                db.session.add(record)
                saved_count += 1
        
        db.session.commit()
        print(f"[数据库] 已保存 {saved_count} 条行为轨迹记录")
    except Exception as db_err:
        db.session.rollback()
        print(f"[数据库] 保存失败: {db_err}")

    # 保存文件
    wb.save(ORIGINAL_FILE)
    wb.close()

    return f"处理完成！填充了 {len(target_titles)} 个日期列，共 {len(user_rows_sorted)} 个用户，已按完播次数降序排序"'''

content = content.replace(old_save, new_save)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ routes_behavior.py 已更新，添加了数据库保存功能")
