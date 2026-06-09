# -*- coding: utf-8 -*-
"""检查当前生成的二维码内容，确认URL是什么类型"""
import base64
import os

# 读取之前生成的二维码文件
qr_files = ['final_wwclient.png', 'app_qrcode.png', 'direct_wwclient.png']

for fname in qr_files:
    if os.path.exists(fname):
        print(f'文件: {fname}')
        with open(fname, 'rb') as f:
            qr_bytes = f.read()
        print(f'  大小: {len(qr_bytes)} bytes')
        
        # 尝试解码二维码
        try:
            import zbarlight
            codes = zbarlight.scan_codes(['qrcode'], qr_bytes)
            if codes:
                url = codes[0].decode('utf-8')
                print(f'  二维码内容: {url}')
                if 'wwclient' in url.lower():
                    print('  ✓ 是 wwclient 类型')
                elif 'admin' in url.lower() or 'loginpage' in url.lower():
                    print('  ✗ 是管理后台类型')
                else:
                    print('  ? 未知类型')
        except ImportError:
            print('  (需要 zbarlight 库来解码)')
        except Exception as e:
            print(f'  解码失败: {e}')
        print()

# 直接测试最新服务生成的二维码
print('='*60)
print('测试当前服务生成的二维码')
print('='*60)

from wecom_app_login_service import get_wecom_app_login_service

service = get_wecom_app_login_service()
sid, err = service.create_session(login_type='wwclient')
qr_b64 = service.get_qrcode_b64(sid)

if qr_b64:
    qr_bytes = base64.b64decode(qr_b64)
    print(f'会话ID: {sid[:20]}...')
    print(f'二维码大小: {len(qr_bytes)} bytes')
    
    # 保存并尝试解码
    with open('current_qr.png', 'wb') as f:
        f.write(qr_bytes)
    print('已保存为 current_qr.png')
    
    # 尝试解码
    try:
        import zbarlight
        codes = zbarlight.scan_codes(['qrcode'], qr_bytes)
        if codes:
            url = codes[0].decode('utf-8')
            print(f'\n二维码内容: {url}')
            if 'wwclient' in url.lower():
                print('✓ 是 wwclient 类型')
            elif 'admin' in url.lower() or 'loginpage' in url.lower() or 'frame' in url.lower():
                print('✗ 是管理后台类型')
            else:
                print('? 未知类型')
        else:
            print('无法识别二维码')
    except ImportError:
        print('需要安装 zbarlight 来解码二维码')
        print('pip install zbarlight')
