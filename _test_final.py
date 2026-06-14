# -*- coding: utf-8 -*-
from app import app
client = app.test_client()

resp = client.post('/login', data={'username': 'admin', 'password': '123456'}, follow_redirects=False)
print('登录: %d -> %s' % (resp.status_code, resp.headers.get('Location', '')))

tests = [
    ('配置页', '/wecom-scrm/config', 'GET'),
    ('账号列表', '/wecom-scrm/accounts', 'GET'),
    ('客户列表', '/wecom-scrm/customers', 'GET'),
    ('测试连接', '/wecom-scrm/config/test', 'POST'),
    ('新增账号', '/wecom-scrm/account/add', 'POST'),
]

for name, path, method in tests:
    try:
        if method == 'GET':
            resp = client.get(path)
        elif 'test' in path:
            resp = client.post(path, data={'corp_id': 'test', 'contact_secret': 'test'})
        else:
            resp = client.post(path, data={'account_name': 'test', 'wecom_id': 'test'})
        print('  [%3d] %s: %s' % (resp.status_code, name, path))
    except Exception as e:
        print('  [ERR] %s: %s' % (name, e))
print('完成')
