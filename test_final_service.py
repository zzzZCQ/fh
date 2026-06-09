import time, base64
from wecom_app_login_service import get_wecom_app_login_service

service = get_wecom_app_login_service()

print('=' * 60)
print('测试 wwclient (企微APP客户端) 登录')
print('=' * 60)
sid, err = service.create_session(login_type='wwclient')
print('session_id:', sid)
print('err:', repr(err))
qr = service.get_qrcode_b64(sid)
if qr:
    with open('final_wwclient.png', 'wb') as f:
        f.write(base64.b64decode(qr))
    qsize = len(base64.b64decode(qr))
    print('二维码:', len(qr), 'chars, size:', qsize, 'bytes')

print()
print('状态:')
for i in range(6):
    time.sleep(3)
    status = service.get_status(sid)
    print('  [' + str((i+1)*3) + 's] ' + str(status['status']))
    if status['status'] not in ('pending', 'scanned'):
        break

print()
print('测试完成!')
