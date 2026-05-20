# -*- coding: utf-8 -*-
"""后台静默启动Flask服务"""
import sys
import os

if __name__ == '__main__':
    # 添加当前目录到路径
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    from app import socketio, app
    
    # 生产模式运行，关闭debug
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)