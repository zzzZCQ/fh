# -*- coding: utf-8 -*-
"""验证两种二维码扫码后的实际跳转"""
import requests
import base64
import time

# 生成两种二维码
from wecom_app_login_service import get_wecom_app_login_service

service = get_wecom_app_login_service()

print('='*60)
print('生成并分析两种二维码')
print('='*60)

# 1. wwclient 类型
sid1, err1 = service.create_session(login_type='wwclient')
qr1 = service.get_qrcode_bytes(sid1)
with open('qr_wwclient.png', 'wb') as f:
    f.write(qr1)
print(f'[1] wwclient 二维码: {len(qr1)} bytes -> qr_wwclient.png')

# 2. login_admin 类型
sid2, err2 = service.create_session(login_type='login_admin')
qr2 = service.get_qrcode_bytes(sid2)
with open('qr_admin.png', 'wb') as f:
    f.write(qr2)
print(f'[2] login_admin 二维码: {len(qr2)} bytes -> qr_admin.png')

print('\n请用企业微信扫描这两个二维码，观察扫码后的页面差异')
print('wwclient: 应该显示"企业微信"相关页面')
print('login_admin: 应该显示"企业微信管理后台"页面')
