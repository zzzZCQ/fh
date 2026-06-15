# -*- coding: utf-8 -*-
"""发货通知系统 - 后台服务启动入口"""
import os
import sys
import time
import threading
import logging
from logging.handlers import RotatingFileHandler

# 设置工作目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 配置日志
log_path = os.path.join(os.path.dirname(__file__), 'server.log')
handler = RotatingFileHandler(log_path, maxBytes=1024*1024*5, backupCount=5, encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = logging.getLogger('fh_server')
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def check_dependencies():
    """检查依赖是否安装"""
    try:
        import flask
        import flask_sqlalchemy
        import flask_login
        import flask_socketio
        import apscheduler
        import requests
        return True
    except ImportError as e:
        logger.error(f'缺少依赖: {e}')
        return False

def start_server():
    """启动Flask服务器"""
    try:
        logger.info('=== 发货通知系统启动 ===')
        
        # 导入并启动应用
        from app import socketio, app
        
        logger.info(f'服务启动时间: {time.strftime("%Y-%m-%d %H:%M:%S")}')
        logger.info(f'监听地址: 0.0.0.0:5000')
        
        # 启动服务器
        socketio.run(
            app, 
            host='0.0.0.0', 
            port=5000, 
            debug=False, 
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
        
    except Exception as e:
        logger.error(f'服务器启动失败: {e}', exc_info=True)
        raise

if __name__ == '__main__':
    if not check_dependencies():
        print('请先安装依赖: pip install -r requirements.txt')
        sys.exit(1)
    
    # 启动服务器
    start_server()