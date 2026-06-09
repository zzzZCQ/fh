# -*- coding: utf-8 -*-
"""测试二维码API是否正常返回数据"""
import sys
sys.path.insert(0, 'd:/fh')

from wecom_ipad_protocol_v2 import WeComIPadProtocolV2

def test_qrcode():
    print('=== 测试 iPad 协议二维码获取 ===')
    protocol = WeComIPadProtocolV2()
    ok, err, qrcode = protocol.fetch_qrcode()
    
    print(f'成功: {ok}')
    print(f'错误: {err}')
    print(f'二维码数据: {"有数据" if qrcode else "None"}')
    if qrcode:
        print(f'二维码长度: {len(qrcode)}')
        print(f'前100字符: {qrcode[:100]}...')
        print(f'是否以 data:image/png;base64 开头: {qrcode.startswith("data:image/png;base64,")}')
        
        # 验证base64数据
        if qrcode.startswith('data:image/png;base64,'):
            import base64
            try:
                data = qrcode.split(',')[1]
                decoded = base64.b64decode(data)
                print(f'解码后二进制大小: {len(decoded)} 字节')
                # 检查是否是有效的PNG
                if decoded[:8] == b'\x89PNG\r\n\x1a\n':
                    print('✅ 是有效的PNG图片')
                else:
                    print('❌ 不是有效的PNG图片')
            except Exception as e:
                print(f'解码失败: {e}')

if __name__ == '__main__':
    test_qrcode()