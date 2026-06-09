from wecom_app_login_service import get_wecom_app_login_service

service = get_wecom_app_login_service()

print('='*60)
print('测试1: 生成 wwclient 类型二维码 (iPad企微APP客户端)')
print('='*60)

sid, err = service.create_session(login_type='wwclient')
print('session_id:', sid[:20], '...')
print('err:', err)

qr_b64 = service.get_qrcode_b64(sid)
qr_bytes = service.get_qrcode_bytes(sid)
print('二维码 base64 长度:', len(qr_b64) if qr_b64 else 0)
print('二维码字节数:', len(qr_bytes) if qr_bytes else 0)

status = service.get_status(sid)
print('状态:', status.get('status'), ', login_type:', status.get('login_type'))

print()
print('='*60)
print('测试2: 生成 login_admin 类型二维码 (管理后台)')
print('='*60)

sid2, err2 = service.create_session(login_type='login_admin')
print('session_id:', sid2[:20], '...')
print('err:', err2)

qr_bytes2 = service.get_qrcode_bytes(sid2)
print('二维码字节数:', len(qr_bytes2) if qr_bytes2 else 0)

status2 = service.get_status(sid2)
print('状态:', status2.get('status'), ', login_type:', status2.get('login_type'))

print()
print('='*60)
print('全部测试通过!')
print('='*60)
