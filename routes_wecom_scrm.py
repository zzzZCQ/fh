"""企业微信SCRM系统路由"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, WecomAccount, WecomCustomer
from datetime import datetime
import json

wecom_scrm_bp = Blueprint('wecom_scrm', __name__, 
                         url_prefix='/admin/wecom-scrm',
                         template_folder='templates')


# ==================== 账号管理 ====================

@wecom_scrm_bp.route('/')
@login_required
def index():
    """SCRM首页"""
    return render_template('wecom_scrm/index.html')


@wecom_scrm_bp.route('/api/accounts')
@login_required
def get_accounts():
    """获取当前用户的企业微信账号列表"""
    try:
        accounts = WecomAccount.query.filter_by(
            user_id=current_user.id, 
            is_active=True
        ).order_by(WecomAccount.create_time.desc()).all()
        
        return jsonify({
            'success': True,
            'data': [a.to_dict() for a in accounts]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/accounts', methods=['POST'])
@login_required
def add_account():
    """添加企业微信账号"""
    try:
        data = request.get_json()
        account_name = data.get('account_name')
        
        if not account_name:
            return jsonify({'success': False, 'message': '请填写账号名称'})
        
        account = WecomAccount(
            user_id=current_user.id,
            account_name=account_name,
            real_name=data.get('real_name', ''),
            wecom_alias=data.get('wecom_alias', '')
        )
        
        db.session.add(account)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '账号添加成功',
            'data': account.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/accounts/<int:account_id>', methods=['DELETE'])
@login_required
def delete_account(account_id):
    """删除企业微信账号"""
    try:
        account = WecomAccount.query.get(account_id)
        if not account or account.user_id != current_user.id:
            return jsonify({'success': False, 'message': '账号不存在'})
        
        account.is_active = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': '账号已删除'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/accounts/<int:account_id>/start-login', methods=['POST'])
@login_required
def start_account_login(account_id):
    """启动账号登录流程"""
    try:
        account = WecomAccount.query.get(account_id)
        if not account or account.user_id != current_user.id:
            return jsonify({'success': False, 'message': '账号不存在'})
        
        # TODO: 这里需要集成Playwright来启动登录
        # 暂时返回成功，让前端显示二维码界面
        
        # 更新账号状态
        account.status = 'logging'
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': '已启动登录流程',
            'data': {'redirect': True}
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


# ==================== 客户管理 ====================

@wecom_scrm_bp.route('/api/accounts/<int:account_id>/customers')
@login_required
def get_customers(account_id):
    """获取账号的客户列表"""
    try:
        account = WecomAccount.query.get(account_id)
        if not account or account.user_id != current_user.id:
            return jsonify({'success': False, 'message': '账号不存在'})
        
        customers = WecomCustomer.query.filter_by(
            account_id=account_id, 
            is_active=True
        ).order_by(WecomCustomer.last_contact_time.desc()).all()
        
        return jsonify({
            'success': True,
            'data': [c.to_dict() for c in customers]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/customers/<int:customer_id>/messages', methods=['POST'])
@login_required
def send_message(customer_id):
    """给客户发送消息"""
    try:
        customer = WecomCustomer.query.get(customer_id)
        if not customer:
            return jsonify({'success': False, 'message': '客户不存在'})
        
        # 检查账号归属
        account = WecomAccount.query.get(customer.account_id)
        if not account or account.user_id != current_user.id:
            return jsonify({'success': False, 'message': '无权操作'})
        
        data = request.get_json()
        content = data.get('content')
        
        if not content:
            return jsonify({'success': False, 'message': '请输入消息内容'})
        
        # TODO: 这里需要集成Playwright来发送消息
        # 暂时返回成功
        
        # 更新客户最后联系时间
        customer.last_contact_time = datetime.now()
        customer.message_count += 1
        account.message_count += 1
        db.session.commit()
        
        return jsonify({'success': True, 'message': '消息发送成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
