# -*- coding: utf-8 -*-
"""检查通话录音配置状态"""
from app import app
from routes_wework import get_call_recording_enabled

with app.app_context():
    print('检查通话录音配置状态')
    print('=' * 60)
    
    enabled = get_call_recording_enabled()
    print(f'当前配置: {"✅ 已启用" if enabled else "❌ 已停用"}')
    
    from models import db
    from sqlalchemy import text
    
    try:
        result = db.session.execute(text("SELECT * FROM app_config WHERE config_key='call_recording_enabled'"))
        row = result.fetchone()
        if row:
            print(f'数据库值: {row[1]}')
        else:
            print('数据库中未找到该配置')
    except Exception as e:
        print(f'查询数据库配置出错: {e}')
