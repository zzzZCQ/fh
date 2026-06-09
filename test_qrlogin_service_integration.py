# -*- coding: utf-8 -*-
import time
from wecom_qrlogin_service import get_qrlogin_service

# 测试服务
print('=' * 60)
print('测试企微扫码登录服务')
print('=' * 60)

service = get_qrlogin_service()
session_id, qrcode_data = service.create_qrcode()

print(f'session_id: {session_id}')
print(f'qrcode_data 类型: {"data-url" if qrcode_data.startswith("data:") else "error"}')
print(f'qrcode_data 长度: {len(qrcode_data)} 字符')

if qrcode_data.startswith('error:'):
    print(f'错误: {qrcode_data}')
else:
    # 保存二维码到文件
    import base64
    img_data = base64.b64decode(qrcode_data.split(',')[1])
    with open('service_qrcode.png', 'wb') as f:
        f.write(img_data)
    print(f'二维码已保存为 service_qrcode.png ({len(img_data)} bytes)')

# 测试状态查询
print('\n[状态测试] 5秒后将检查状态...')
for i in range(5):
    time.sleep(1)
    status = service.get_status(session_id)
    print(f'  [{i+1}s] status={status["status"] if status else "None"}')

print('\n测试完成!')
