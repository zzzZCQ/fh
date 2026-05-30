# -*- coding: utf-8 -*-
"""添加客户跟踪路由到routes_behavior.py"""

file_path = 'd:/fh/routes_behavior.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 新的客户跟踪路由
new_route = '''

@bp.route('/admin/customer_tracking')
@role_required('admin')
def customer_tracking():
    """客户跟踪页面 - 管理员查看业务员的行为轨迹数据"""
    from models import User, Group
    
    # 获取筛选参数
    group_id = request.args.get('group_id', type=int)
    salesman_id = request.args.get('salesman_id', type=int)
    data_scope = request.args.get('data_scope', 'all')
    
    # 获取组别列表
    groups = Group.query.all()
    
    # 获取业务员列表
    if group_id:
        salesmen = User.query.filter_by(group_id=group_id, role='salesman').all()
    else:
        salesmen = User.query.filter_by(role='salesman').all()
    
    # 获取可选的日期
    dates = db.session.query(
        BehaviorTrackingRecord.month,
        BehaviorTrackingRecord.day
    ).distinct().order_by(BehaviorTrackingRecord.month, BehaviorTrackingRecord.day).all()
    
    # 根据筛选条件查询数据
    query = BehaviorTrackingRecord.query
    
    if salesman_id:
        query = query.filter_by(user_id=salesman_id)
    elif group_id and data_scope == 'all':
        group = Group.query.get(group_id)
        if group:
            child_groups = [g.id for g in group.get_descendants()] + [group_id]
            query = query.join(User).filter(User.group_id.in_(child_groups))
    
    records = query.all()
    
    # 构建数据结构
    data = {}
    for record in records:
        key = (record.user_id, record.nickname)
        if key not in data:
            user = User.query.get(record.user_id)
            data[key] = {
                'user_id': record.user_id,
                'salesman_name': user.name if user else '',
                'group_name': user.group.name if user and user.group else '',
                'nickname': record.nickname,
                'dates': {}
            }
        date_key = f"{record.month:02d}{record.day:02d}"
        data[key]['dates'][date_key] = {
            'play_status': record.play_status,
            'call_duration': record.call_duration_seconds
        }
    
    rows_data = list(data.values())
    date_list = [f"{m:02d}{d:02d}" for m, d in dates]
    
    return render_template('customer_tracking.html',
                           groups=groups,
                           salesmen=salesmen,
                           dates=date_list,
                           rows_data=rows_data,
                           selected_group=group_id,
                           selected_salesman=salesman_id,
                           data_scope=data_scope,
                           unread_count=get_unread_count(current_user.id))
'''

# 在文件末尾添加新路由
content += new_route

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 客户跟踪路由已添加")
