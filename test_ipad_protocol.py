
# -*- coding: utf-8 -*-
"""
测试企业微信iPad协议
验证移动端API是否能正确工作
"""
from wecom_ipad_protocol import WeComIPadProtocol

def test_protocol():
    """测试iPad协议"""
    print("="*60)
    print("企业微信iPad协议测试")
    print("目标: 访问移动端API (wx.work.weixin.qq.com)")
    print("="*60)
    
    protocol = WeComIPadProtocol()
    
    # 1. 获取ticket
    print("\n[1/3] 获取登录ticket...")
    ticket = protocol.get_login_ticket()
    if ticket:
        print(f"✅ SUCCESS: ticket获取成功")
        print(f"   ticket: {ticket[:20]}...")
    else:
        print(f"❌ FAILED: 未能获取ticket")
    
    # 2. 获取二维码URL
    print("\n[2/3] 获取二维码URL...")
    qrcode_url = protocol.get_qrcode_url()
    if qrcode_url:
        print(f"✅ SUCCESS: 二维码URL")
        print(f"   URL: {qrcode_url}")
    else:
        print(f"❌ FAILED: 未能获取二维码URL")
    
    # 3. 生成二维码图片
    print("\n[3/3] 生成二维码图片...")
    qrcode_file = protocol.generate_qrcode_image()
    if qrcode_file:
        print(f"✅ SUCCESS: 二维码图片已保存")
        print(f"   文件: {qrcode_file}")
    else:
        print(f"❌ FAILED: 未能生成二维码图片")
    
    # 关闭会话
    protocol.close()
    
    print("\n" + "="*60)
    print("测试完成")
    print("="*60)

if __name__ == "__main__":
    test_protocol()
