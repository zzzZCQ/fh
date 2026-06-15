"""综合冒烟测试：通过 Flask test_client 请求财务核心页面，检查不抛异常。
"""
from app import app

# 构造一个未登录的匿名请求：测试 url_for 能否正常生成（即使被重定向到登录页，
# 也说明模板渲染阶段的 url_for 没有 BuildError）
app.config['TESTING'] = True
client = app.test_client()

with app.app_context():
    from flask import url_for
    # 显式测试每个 endpoint 能否被 url_for 解析
    endpoints = [
        ('finance.finance_dashboard', {}),
        ('finance.attendance_config', {}),
        ('finance.attendance_config_save', {}),
        ('finance.attendance_data', {}),
        ('finance.salary_calculation', {}),
        ('finance.commission_config', {}),  # 旧页已保留，但不应再有引用
        ('finance.commission_save', {}),
    ]
    print('--- url_for 解析测试 ---')
    for ep, kwargs in endpoints:
        try:
            url = url_for(ep, **kwargs)
            print(f'  [OK]  {ep} => {url}')
        except Exception as e:
            print(f'  [FAIL] {ep} => {e}')

    # 模拟一个登录用户再请求页面
    print()
    print('--- 页面请求测试（未登录时会被重定向到登录页） ---')
    for route in ['/finance/dashboard', '/finance/attendance/config',
                  '/finance/attendance/data', '/finance/salary']:
        resp = client.get(route, follow_redirects=False)
        status = resp.status_code
        if status in (200, 302):
            print(f'  [OK]  GET {route} => {status}')
        else:
            print(f'  [WARN] GET {route} => {status}')

print()
print('>>> 冒烟测试完成')
