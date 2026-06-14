# -*- coding: utf-8 -*-
"""测试登录状态"""
from app import app
from models import db, User
import sys

with app.app_context():
    # 看看有哪些用户
    users = User.query.all()
    print(f'数据库中的用户: {[(u.username, u.roles) for u in users]}')

    admin = User.query.filter_by(username='admin').first()
    if admin:
        print(f'admin 用户存在, password_hash={admin.password_hash[:20] if admin.password_hash else "NONE"}')

client = app.test_client()

# 先访问登录页
resp = client.get('/login')
print(f'GET /login: {resp.status_code}')

# 然后 POST 登录
resp = client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)
print(f'POST /login: {resp.status_code}')
if resp.status_code in (301, 302, 303):
    print(f'  redirect -> {resp.headers.get("Location")}')

# 检查 cookies
print(f'Cookies: {dict(client.cookie_jar._cookies.get("localhost", {}))}')

# 访问受保护页面
resp = client.get('/wecom-scrm/config', follow_redirects=False)
print(f'\nGET /wecom-scrm/config: {resp.status_code}')
if resp.status_code in (301, 302, 303):
    print(f'  redirect -> {resp.headers.get("Location")}')

# 访问不需要权限的首页
resp = client.get('/', follow_redirects=False)
print(f'GET /: {resp.status_code}')
if resp.status_code in (301, 302, 303):
    print(f'  redirect -> {resp.headers.get("Location")}')
