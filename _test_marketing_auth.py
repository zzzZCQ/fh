# -*- coding: utf-8 -*-
"""权限验证 - 精确检查按钮可见性"""
import sys
sys.path.insert(0, '.')
from app import app, db
from models import User, Group, MarketingPeriod, MarketingSchedule
from datetime import date

# 先确保有测试数据
with app.app_context():
    group = Group.query.first()
    period = MarketingPeriod.query.filter_by(group_id=group.id).order_by(MarketingPeriod.id.desc()).first()
    if not period:
        period = MarketingPeriod(
            group_id=group.id, period_name='测试栏目',
            start_date=date.today(), end_date=date.today(),
            status='active',
            created_by=User.query.filter(User.username == 'admin').first().id
        )
        db.session.add(period)
        db.session.flush()
        sched = MarketingSchedule(
            period_id=period.id, schedule_date=date.today(),
            time_point='09:00', content='测试话术内容',
            created_by=User.query.filter(User.username == 'admin').first().id
        )
        db.session.add(sched)
        db.session.commit()
    print(f'测试栏目: {period.period_name} (id={period.id})')
    print(f'测试话术: {MarketingSchedule.query.filter_by(period_id=period.id).count()} 条')

# === 管理员测试 ===
print('\n=== Admin view ===')
client = app.test_client()
client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
r = client.get('/marketing')
html = r.data.decode('utf-8')

# 精确检查按钮：找有 onclick/链接的实际按钮（不是JS函数定义）
# 管理员按钮特征：
# 1. 顶部的"新增栏目"链接
# 2. 卡片上的"删除"按钮（有deleteSchedule函数调用）
# 3. contenteditable="true"
# 4. "编辑栏目"按钮
# 5. showNewScheduleModal 的卡片
admin_btns = {
    '新增栏目按钮': 'btn btn-success' in html and '新增栏目' in html,
    '编辑栏目按钮': '编辑栏目' in html,
    '编辑模式(contenteditable)': 'contenteditable="true"' in html,
    '删除话术按钮': 'onclick="deleteSchedule(' in html,
    '添加话术卡片(+)': 'onclick="showNewScheduleModal(' in html and 'schedule-add-card' in html,
}
for k, v in admin_btns.items():
    print(f'  ✅ {k}' if v else f'  ❌ {k}')

# 业务员按钮
sales_btns = {
    '复制话术按钮': '复制话术' in html,
    '已执行按钮': '已执行' in html,
}
print()
for k, v in sales_btns.items():
    print(f'  ✅ {k}' if v else f'  ❌ {k}')

# === 业务员测试 ===
print('\n=== Salesman view ===')
with app.app_context():
    users = User.query.all()
    non_admin = next((u for u in users if not u.has_role('admin') and u.is_active), None)

if non_admin:
    print(f'测试用户: {non_admin.username}')
    client2 = app.test_client()
    client2.post('/login', data={'username': non_admin.username, 'password': '123456'}, follow_redirects=True)
    r2 = client2.get('/marketing')
    html2 = r2.data.decode('utf-8')

    # 业务员不应看到这些
    admin_only = {
        '新增栏目按钮': 'btn btn-success' in html2 and '新增栏目' in html2[:500],
        '编辑栏目按钮': '编辑栏目' in html2[:1500],
        '编辑模式(contenteditable)': 'contenteditable="true"' in html2,
        '删除话术按钮': 'onclick="deleteSchedule(' in html2 and 'onclick=\"deleteSchedule(' not in html2.split('<script>')[0],
    }
    print('--- 管理员专属元素（应全部为 False） ---')
    for k, v in admin_only.items():
        print(f'  ❌ {k}' if v else f'  ✅ 已隐藏: {k}')

    # 业务员应看到这些
    sales_see = {
        '复制话术按钮': '复制话术' in html2,
        '已执行按钮': '已执行' in html2,
        '今日营销话术提示': '今日营销话术' in html2,
    }
    print('--- 业务员可见元素（应全部为 True） ---')
    for k, v in sales_see.items():
        print(f'  ✅ {k}' if v else f'  ❌ {k}')

    # API权限
    post = client2.post('/marketing/api/schedule',
        json={'period_id': period.id, 'schedule_date': '2025-01-01', 'time_point': '09:00', 'content': 'test'},
        content_type='application/json')
    print(f'\n--- API 权限测试 ---')
    print(f'  POST /marketing/api/schedule: {post.status_code}')
    try:
        data = post.get_json()
        print(f'  响应: {data}')
        print(f'  ✅ 正确拒绝' if not data.get('success') else f'  ❌ 错误允许')
    except:
        print(f'  响应非JSON (可能是重定向)')

else:
    print('没有非管理员用户')

print('\n=== 验证完成 ===')
