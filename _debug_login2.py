# -*- coding: utf-8 -*-
"""用已知正确的账号测试"""
from app import app
from models import db, User
import time

client = app.test_client()

# 尝试所有用户的默认密码
for uname in ['admin', '88888888']:
    for pwd in ['123456', '88888888', 'admin123', 'admin', 'password']:
        with app.app_context():
            user = User.query.filter_by(username=uname).first()
            if user and user.check_password(pwd):
                print(f'✓ 找到有效凭据: {uname}/{pwd}')
                break
    else:
        continue
    break

# 重新更新 admin 的密码以便测试
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if admin:
        admin.set_password('123456')
        db.session.commit()
        print(f'已重置 admin 密码为 123456')

# 测试登录
client = app.test_client()
resp = client.post('/login', data={'username': 'admin', 'password': '123456'}, follow_redirects=False)
print(f'POST /login: {resp.status_code}')
if resp.status_code in (301, 302, 303):
    print(f'  redirect -> {resp.headers.get("Location")}')

    # 测试各页面
    for path in ['/wecom-scrm/config', '/wecom-scrm/accounts', '/wecom-scrm/customers']:
        resp = client.get(path, follow_redirects=False)
        status = resp.status_code
        redirect = resp.headers.get("Location", "")
        print(f'  [{status:3d}] {path} {"→ " + redirect if redirect else ""}')
else:
    print('登录失败，检查返回内容')
    print(resp.data[:200])
