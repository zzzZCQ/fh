# -*- coding: utf-8 -*-
"""
企业微信自动化营销管理路由
"""
from flask import Blueprint, render_template, request, jsonify
from wecom_auto_bot import WeComAutoBot
import json
import os
import threading
from datetime import datetime
from flask_login import current_user
from models import db, Order


wecom_auto_bp = Blueprint('wecom_auto', __name__, url_prefix='/admin/wecom-auto')

# 全局机器人实例
bot = WeComAutoBot()

# 登录状态监控线程
login_monitor_thread = None
login_monitor_active = False


@wecom_auto_bp.route('/')
def index():
    """首页"""
    unread_count = 0
    if current_user.is_authenticated:
        unread_count = Order.query.filter_by(status='待发货').count()
    return render_template('wecom_auto/index.html', unread_count=unread_count)


@wecom_auto_bp.route('/api/status')
def get_status():
    """获取当前状态"""
    try:
        is_running = bot.is_browser_running()
        is_logged_in = bot.is_logged_in
        
        return jsonify({
            'success': True,
            'data': {
                'browser_running': is_running,
                'logged_in': is_logged_in
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_auto_bp.route('/api/start-login', methods=['POST'])
def start_login():
    """开始登录流程"""
    try:
        # 启动浏览器
        if not bot.launch_browser(headless=False):
            return jsonify({'success': False, 'message': '启动浏览器失败'})
        
        # 打开登录页面
        url = bot.get_login_qrcode_url()
        if not url:
            return jsonify({'success': False, 'message': '打开登录页面失败'})
        
        # 启动后台监控线程
        global login_monitor_thread, login_monitor_active
        login_monitor_active = True
        if not login_monitor_thread or not login_monitor_thread.is_alive():
            login_monitor_thread = threading.Thread(target=_wait_for_login_background, daemon=True)
            login_monitor_thread.start()
        
        return jsonify({
            'success': True,
            'message': '浏览器已打开，请扫码登录'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


def _wait_for_login_background():
    """后台等待登录"""
    try:
        success = bot.wait_for_login(timeout=300)
        if success:
            print("[WeComAuto] 登录成功！")
    except Exception as e:
        print(f"[WeComAuto] 登录监控异常: {e}")


@wecom_auto_bp.route('/api/check-login')
def check_login():
    """检查登录状态"""
    try:
        if not bot.is_browser_running():
            return jsonify({
                'success': True,
                'data': {
                    'logged_in': False,
                    'browser_running': False
                }
            })
        
        # 检查登录状态
        is_logged_in = bot.check_login_status() if bot.is_browser_running() else False
        
        return jsonify({
            'success': True,
            'data': {
                'logged_in': is_logged_in,
                'browser_running': True
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_auto_bp.route('/api/customers')
def get_customers():
    """获取客户列表"""
    try:
        if not bot.is_logged_in:
            return jsonify({'success': False, 'message': '请先登录'})
        
        customers = bot.get_customer_list()
        return jsonify({
            'success': True,
            'data': customers
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_auto_bp.route('/api/send-message', methods=['POST'])
def send_message():
    """发送消息"""
    try:
        data = request.get_json()
        customer_name = data.get('customer_name')
        content = data.get('content')
        
        if not customer_name or not content:
            return jsonify({'success': False, 'message': '请填写客户名称和消息内容'})
        
        if not bot.is_logged_in:
            return jsonify({'success': False, 'message': '请先登录'})
        
        success = bot.send_message_to_customer(customer_name, content)
        if success:
            return jsonify({'success': True, 'message': '消息发送成功'})
        else:
            return jsonify({'success': False, 'message': '消息发送失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_auto_bp.route('/api/templates')
def get_templates():
    """获取消息模板列表"""
    try:
        templates = bot.get_message_templates()
        return jsonify({
            'success': True,
            'data': templates
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_auto_bp.route('/api/templates', methods=['POST'])
def add_template():
    """添加消息模板"""
    try:
        data = request.get_json()
        name = data.get('name')
        content = data.get('content')
        
        if not name or not content:
            return jsonify({'success': False, 'message': '请填写模板名称和内容'})
        
        bot.add_message_template(name, content)
        return jsonify({'success': True, 'message': '模板添加成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_auto_bp.route('/api/templates/<int:template_id>', methods=['DELETE'])
def delete_template(template_id):
    """删除消息模板"""
    try:
        bot.delete_message_template(template_id)
        return jsonify({'success': True, 'message': '模板删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_auto_bp.route('/api/sent-messages')
def get_sent_messages():
    """获取已发送消息记录"""
    try:
        messages = bot.get_sent_messages()
        return jsonify({
            'success': True,
            'data': messages[-100:]  # 最近100条
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_auto_bp.route('/api/close-browser', methods=['POST'])
def close_browser():
    """关闭浏览器"""
    try:
        global login_monitor_active
        login_monitor_active = False
        
        bot.close()
        return jsonify({'success': True, 'message': '浏览器已关闭'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
