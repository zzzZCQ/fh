# -*- coding: utf-8 -*-
"""测试企微 APP 扫码登录服务"""
import time
import base64
from wecom_app_login_service import get_wecom_app_login_service

service = get_wecom_app_login_service()

print('='*70)
print('测试企微 APP 客户端登录 (login_type=wwclient)')
print('='*70)

# 创建会话
session_id, err = service.create_session(login_type='wwclient')
print(f'session_id: {session_id}')
print(f'创建成功: {not err}, 错误: {err}')

# 获取二维码
qr_b64 = service.get_qrcode_b64(session_id)
if qr_b64:
    print(f'二维码: {len(qr_b64)} chars (base64)')
    # 保存为文件
    fname = 'app_qrcode.png'
    with open(fname, 'wb') as f:
        f.write(base64.b64decode(qr_b64))
    print(f'已保存为 {fname}')

# 轮询状态
print('\n开始轮询状态 (每5秒检查一次)...')
for i in range(20):  # 约100秒
    time.sleep(5)
    status = service.get_status(session_id)
    if status:
        print(f'  [{i*5:4d}s] status={status["status"]}, elapsed={status["elapsed_seconds"]}s')
        if status['status'] not in ('pending', 'scanned'):
            print(f'  => 状态不再等待，结束轮询')
            break
    else:
        print(f'  [{i*5:4d}s] 会话不存在')
        break

# 获取结果
result = service.get_result(session_id)
print(f'\n最终结果: {result}')

# 再测试 management 类型
print('\n' + '='*70)
print('测试企微管理后台登录 (login_type=login_admin)')
print('='*70)

session_id2, err2 = service.create_session(login_type='login_admin')
print(f'session_id: {session_id2}')
print(f'创建成功: {not err2}, 错误: {err2}')

qr_b64_2 = service.get_qrcode_b64(session_id2)
if qr_b64_2:
    print(f'二维码: {len(qr_b64_2)} chars (base64)')
    with open('admin_qrcode.png', 'wb') as f:
        f.write(base64.b64decode(qr_b64_2))
    print('已保存为 admin_qrcode.png')

print('\n测试完成！')
