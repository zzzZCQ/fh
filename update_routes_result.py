# -*- coding: utf-8 -*-
"""修改routes_behavior.py，展示页面从数据库读取"""

file_path = 'd:/fh/routes_behavior.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 替换 behavior_tracking_result 函数
old_function = '''@bp.route('/behavior_tracking/result')
@role_required('salesman')
def behavior_tracking_result():
    """行为轨迹处理结果展示页面"""
    user_dir = get_user_behavior_dir(current_user.id)
    base_file_path = os.path.join(user_dir, '行为轨迹表.xlsx')
    
    if not os.path.exists(base_file_path):
        flash('请先上传并处理行为轨迹表！', 'warning')
        return redirect(url_for('behavior.behavior_tracking_page'))
    
    try:
        wb = load_workbook(base_file_path, read_only=True, data_only=True)
        sheet = wb.active
        
        headers = []
        date_cols = {}
        
        for col_idx in range(1, sheet.max_column + 1):
            cell_value = sheet.cell(row=4, column=col_idx).value
            headers.append(cell_value)
            if isinstance(cell_value, int):
                date_cols[col_idx] = cell_value
        
        rows_data = []
        for row_idx in range(5, sheet.max_row + 1):
            row_data = []
            has_data = False
            for col_idx in range(1, sheet.max_column + 1):
                cell = sheet.cell(row=row_idx, column=col_idx)
                cell_value = cell.value
                fill_color = None
                if cell.fill and cell.fill.fgColor and cell.fill.fgColor.rgb:
                    fill_color = cell.fill.fgColor.rgb
                row_data.append({
                    'value': cell_value,
                    'fill_color': fill_color
                })
                if cell_value:
                    has_data = True
            if has_data:
                rows_data.append(row_data)
        
        wb.close()
        
        return render_template('behavior_tracking_result.html',
                               headers=headers,
                               rows_data=rows_data,
                               date_cols=date_cols,
                               unread_count=get_unread_count(current_user.id))
    
    except Exception as e:
        print(f"读取行为轨迹表失败: {e}")
        flash('读取行为轨迹表失败！', 'danger')
        return redirect(url_for('behavior.behavior_tracking_page'))'''

new_function = '''@bp.route('/behavior_tracking/result')
@role_required('salesman')
def behavior_tracking_result():
    """行为轨迹处理结果展示页面（从数据库读取）"""
    user_id = current_user.id
    
    # 获取所有已处理的日期
    processed_dates = BehaviorTrackingRecord.query.filter_by(user_id=user_id) \\
        .with_entities(BehaviorTrackingRecord.month, BehaviorTrackingRecord.day) \\
        .distinct().all()
    
    if not processed_dates:
        flash('请先上传并处理行为轨迹表！', 'warning')
        return redirect(url_for('behavior.behavior_tracking_page'))
    
    # 整理日期列表并排序
    date_list = sorted(set((d.month, d.day) for d in processed_dates))
    
    # 获取所有昵称及其完播次数（用于排序）
    nickname_counts = db.session.query(
        BehaviorTrackingRecord.nickname,
        db.func.count(db.case((BehaviorTrackingRecord.play_status == 1, 1))).label('play_count')
    ).filter(
        BehaviorTrackingRecord.user_id == user_id
    ).group_by(BehaviorTrackingRecord.nickname).all()
    
    # 按完播次数降序排序
    sorted_nicknames = sorted(nickname_counts, key=lambda x: (-x[1], x[0]))
    
    # 构建表头
    headers = ['序号', '昵称'] + [f"{m:02d}{d:02d}" for m, d in date_list]
    
    # 构建数据
    rows_data = []
    for idx, (nickname, _) in enumerate(sorted_nicknames, 1):
        row = [{'value': idx}, {'value': nickname}]
        
        for month, day in date_list:
            record = BehaviorTrackingRecord.query.filter_by(
                user_id=user_id,
                nickname=nickname,
                month=month,
                day=day
            ).first()
            
            if record:
                # 通话时长
                call_str = f"（{format_call_duration(record.call_duration_seconds)}）" if record.call_duration_seconds > 0 else ""
                value = f"{record.play_status}{call_str}"
                
                # 颜色：1=绿色, 2=黄色, 3=红色
                color_map = {1: 'FF00FF00', 2: 'FFFFFF00', 3: 'FFFF0000'}
                fill_color = color_map.get(record.play_status, 'FFFFFFFF')
                
                row.append({
                    'value': value,
                    'fill_color': fill_color
                })
            else:
                row.append({'value': '', 'fill_color': None})
        
        rows_data.append(row)
    
    return render_template('behavior_tracking_result.html',
                           headers=headers,
                           rows_data=rows_data,
                           date_cols=[],
                           unread_count=get_unread_count(current_user.id))'''

content = content.replace(old_function, new_function)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ routes_behavior.py 已更新，展示页面现在从数据库读取数据")
