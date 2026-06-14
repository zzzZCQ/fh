# -*- coding: utf-8 -*-
"""完整测试：登录后访问各页面"""
from app import app
from models import db, User

with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        print('创建测试用户')
        admin = User(username='admin', name='管理员', roles='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
    print(f'用户: {admin.username}, role={admin.role}')

client = app.test_client()

# 登录
resp = client.post('/login', data={'username': admin.username, 'password': 'admin123'}, follow_redirects=True)
print(f'登录状态: {resp.status_code}, redirect_count={len(resp.history)}')

tests = [
    ('配置页', '/wecom-scrm/config', 'GET'),
    ('账号列表', '/wecom-scrm/accounts', 'GET'),
    ('客户列表', '/wecom-scrm/customers', 'GET'),
    ('测试连接', '/wecom-scrm/config/test', 'POST'),
    ('新增账号接口', '/wecom-scrm/account/add', 'POST'),
]

for name, path, method in tests:
    try:
        if method == 'GET':
            resp = client.get(path)
        else:
            if 'test' in path:
                resp = client.post(path, data={'corp_id': 'test_corp', 'contact_secret': 'test_secret'})
            elif 'account/add' in path:
                resp = client.post(path, data={'account_name': '测试账号', 'wecom_id': 'test_user'})
        print(f'  [{resp.status_code:3d}] {name:10s}: {path}')
    except Exception as e:
        print(f'  [ERR] {name:10s}: {e}')

print('\n所有测试完成')
