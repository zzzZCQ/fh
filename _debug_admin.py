# -*- coding: utf-8 -*-
"""调试 admin 登录和 is_admin 传递"""
import sys
sys.path.insert(0, '.')
from app import app
from models import User

# 先确认 admin 用户
with app.app_context():
    admin = User.query.filter(User.username == 'admin').first()
    print(f'Admin user: {admin.username}, roles: {admin.roles}')
    print(f'has_role(admin): {admin.has_role("admin")}')

# 测试登录流程
client = app.test_client()

# 1. 先 GET 登录页获取 session
r0 = client.get('/login')
print(f'\nGET /login: {r0.status_code}')

# 2. POST 登录
r1 = client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)
print(f'POST /login: {r1.status_code}, redirect to: {r1.headers.get("Location", "")}')

# 3. GET 主页
r2 = client.get('/')
print(f'GET /: {r2.status_code}')

# 4. GET 营销中心
r3 = client.get('/marketing')
print(f'GET /marketing: {r3.status_code}, len={len(r3.data)}')

# 检查响应内容
html = r3.data.decode('utf-8')

# 检查 is_admin 变量是否正确传递 - 通过检查 Jinja 模板
print(f'\n=== HTML 内容检查 ===')
print(f'  包含"营销中心": {"营销中心" in html}')
print(f'  包含"megaphone": {"megaphone" in html}')
print(f'  包含"calendar": {"calendar" in html}')

# 检查 is_admin 分支：如果 is_admin=True，应该有"编辑栏目"
print(f'  包含"编辑栏目": {"编辑栏目" in html}')
print(f'  包含"新增栏目": {"新增栏目" in html}')
print(f'  包含 contenteditable: {"contenteditable" in html}')

# 检查响应中是否有进行中的栏目
print(f'  包含"进行中": {"进行中" in html}')
print(f'  包含"schedule-card": {"schedule-card" in html}')

# 检查 session/user
from flask import session
with client.session_transaction() as sess:
    print(f'\nSession keys: {list(sess.keys())}')
    print(f'_user_id: {sess.get("_user_id", "NOT_SET")}')
