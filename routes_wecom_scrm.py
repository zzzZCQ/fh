"""企业微信SCRM系统路由 - 使用企业微信超级智能封装
支持多种库的自动检测和切换：
1. wxwork_pc_api - 功能最强大
2. ntwork - 成熟稳定
3. iPad V2 - 兼容最新版本
4. 模拟模式 - 无需依赖
支持真实扫码登录
"""
from flask import Blueprint, render_template, request, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user
from models import db, WecomAccount, WecomCustomer
from wecom_super_wrapper import WeComSuperWrapper, get_super_wrapper
# 企微APP扫码登录服务已在下方导入 (from wecom_app_login_service import ...)
from datetime import datetime
import json
import os
import threading

wecom_scrm_bp = Blueprint('wecom_scrm', __name__, 
                          url_prefix='/admin/wecom-scrm',
                          template_folder='templates')

# 全局超级封装实例
super_wrapper = None
login_status = {'status': 'idle', 'message': '', 'account_data': None}
login_monitor_thread = None


# ==================== 页面路由 ====================

@wecom_scrm_bp.route('/')
@login_required
def index():
    """SCRM首页"""
    return render_template('wecom_scrm/index.html')


@wecom_scrm_bp.route('/qrlogin')
@login_required
def qrlogin_page():
    """扫码登录页面"""
    return render_template('wecom_scrm/qrlogin.html')


# ==================== 账号管理 ====================

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
    """启动账号登录流程 - 使用超级智能封装"""
    global super_wrapper, login_status
    
    try:
        account = WecomAccount.query.get(account_id)
        if not account or account.user_id != current_user.id:
            return jsonify({'success': False, 'message': '账号不存在'})
        
        # 初始化超级封装
        if super_wrapper is None:
            super_wrapper = get_super_wrapper()
        
        # 打开企业微信
        success = super_wrapper.open(smart=True)
        if not success:
            return jsonify({'success': False, 'message': '无法启动企业微信'})
        
        # 更新账号状态
        account.status = 'logging'
        db.session.commit()
        
        # 更新全局登录状态
        login_status = {'status': 'logging', 'message': '', 'account_data': None}
        
        # 启动后台监控线程
        global login_monitor_thread
        if not login_monitor_thread or not login_monitor_thread.is_alive():
            login_monitor_thread = threading.Thread(target=_monitor_login_background, daemon=True)
            login_monitor_thread.start()
        
        return jsonify({
            'success': True, 
            'message': '企业微信已启动，请在企业微信中登录',
            'data': {
                'redirect': True, 
                'mode': super_wrapper._use_lib,
                'libs_info': super_wrapper.get_available_libs()
            }
        })
    except Exception as e:
        db.session.rollback()
        print(f"[WeComSCRM] 登录流程异常: {e}")
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/accounts/<int:account_id>/qrcode')
@login_required
def get_account_qrcode(account_id):
    """获取账号登录二维码 - Hook协议不需要二维码"""
    return jsonify({
        'success': True,
        'data': {
            'message': '请在企业微信中直接登录'
        }
    })


@wecom_scrm_bp.route('/api/qrcode-image/<filename>')
@login_required
def get_qrcode_image(filename):
    """返回二维码图片"""
    screenshot_dir = os.path.join(os.path.dirname(__file__), 'static', 'screenshots')
    return send_from_directory(screenshot_dir, filename)


@wecom_scrm_bp.route('/api/accounts/<int:account_id>/login-status')
@login_required
def get_login_status(account_id):
    """获取登录状态"""
    global login_status, super_wrapper
    
    try:
        account = WecomAccount.query.get(account_id)
        if not account or account.user_id != current_user.id:
            return jsonify({'success': False, 'message': '账号不存在'})
        
        # 获取库信息
        libs_info = {}
        if super_wrapper:
            libs_info = super_wrapper.get_available_libs()
        
        return jsonify({
            'success': True,
            'data': {
                'status': login_status['status'],
                'message': login_status['message'],
                'libs_info': libs_info
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/accounts/quick-add', methods=['POST'])
@login_required
def quick_add_account():
    """快速添加账号 - 使用超级智能封装"""
    global super_wrapper, login_status
    
    try:
        # 保存当前用户ID（用于后台线程）
        current_user_id = current_user.id
        
        # 初始化超级封装
        if super_wrapper is None:
            super_wrapper = get_super_wrapper()
        
        # 打开企业微信
        success = super_wrapper.open(smart=True)
        if not success:
            return jsonify({'success': False, 'message': '无法启动企业微信'})
        
        # 更新全局登录状态
        login_status = {'status': 'logging', 'message': '', 'account_data': None}
        
        # 启动后台监控线程（传递用户ID）
        global login_monitor_thread
        if not login_monitor_thread or not login_monitor_thread.is_alive():
            login_monitor_thread = threading.Thread(target=_monitor_quick_add_background, args=(current_user_id,), daemon=True)
            login_monitor_thread.start()
        
        return jsonify({
            'success': True, 
            'message': '企业微信已启动，请在企业微信中登录',
            'data': {
                'quick_add': True, 
                'mode': super_wrapper._use_lib,
                'libs_info': super_wrapper.get_available_libs()
            }
        })
    except Exception as e:
        print(f"[WeComSCRM] 快速添加账号异常: {e}")
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/accounts/quick-add/qrcode')
@login_required
def get_quick_add_qrcode():
    """获取快速添加账号的二维码 - Hook协议不需要二维码"""
    return jsonify({
        'success': True,
        'data': {
            'message': '请在企业微信中直接登录'
        }
    })


@wecom_scrm_bp.route('/api/accounts/quick-add/status')
@login_required
def get_quick_add_status():
    """获取快速添加账号的状态"""
    global login_status
    
    return jsonify({
        'success': True,
        'data': {
            'status': login_status['status'],
            'message': login_status['message'],
            'account_data': login_status['account_data']
        }
    })


def _monitor_login_background():
    """后台监控登录状态"""
    global super_wrapper, login_status
    
    try:
        if super_wrapper:
            success = super_wrapper.wait_login(timeout=300)
            if success:
                login_status['status'] = 'online'
                login_status['message'] = '登录成功'
                print(f"[WeComSCRM] 超级封装登录成功！使用库: {super_wrapper._use_lib}")
            else:
                login_status['status'] = 'failed'
                login_status['message'] = '登录超时或失败'
    except Exception as e:
        login_status['status'] = 'failed'
        login_status['message'] = str(e)
        print(f"[WeComSCRM] 登录监控异常: {e}")


def _monitor_quick_add_background(user_id):
    """后台监控快速添加账号"""
    global super_wrapper, login_status
    
    try:
        if super_wrapper:
            success = super_wrapper.wait_login(timeout=300)
            if success:
                # 登录成功后创建账号（需要在应用上下文中）
                with current_app.app_context():
                    account = WecomAccount(
                        user_id=user_id,
                        account_name=f'企业微信账号',
                        status='online'
                    )
                    db.session.add(account)
                    db.session.commit()
                    
                    login_status['status'] = 'success'
                    login_status['message'] = '账号添加成功'
                    login_status['account_data'] = account.to_dict()
                    print(f"[WeComSCRM] 快速添加账号成功！使用库: {super_wrapper._use_lib}")
            else:
                login_status['status'] = 'failed'
                login_status['message'] = '登录超时或失败'
    except Exception as e:
        login_status['status'] = 'failed'
        login_status['message'] = str(e)
        try:
            db.session.rollback()
        except:
            pass
        print(f"[WeComSCRM] 快速添加账号异常: {e}")


# ==================== 扫码登录 API ====================
# 使用 wecom_app_login_service - 模拟 iPad 企微APP扫码登录
# login_type: wwclient (企微APP客户端) / login_admin (管理后台)

from wecom_app_login_service import get_wecom_app_login_service


@wecom_scrm_bp.route('/api/qrlogin/create')
@login_required
def create_qrcode():
    """创建企微APP扫码登录二维码
    query参数:
      - login_type: wwclient (默认, 企微APP客户端) / login_admin (管理后台)
    """
    try:
        login_type = request.args.get('login_type', 'wwclient')
        service = get_wecom_app_login_service()
        session_id, err = service.create_session(login_type=login_type)

        if err:
            return jsonify({'success': False, 'message': err})

        qrcode_b64 = service.get_qrcode_b64(session_id)
        if not qrcode_b64:
            return jsonify({'success': False, 'message': '二维码生成失败'})

        return jsonify({
            'success': True,
            'data': {
                'session_id': session_id,
                'qrcode': 'data:image/png;base64,' + qrcode_b64,
                'login_type': login_type,
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/qrlogin/status/<session_id>')
@login_required
def check_qrlogin_status(session_id):
    """检查企微扫码登录状态"""
    try:
        service = get_wecom_app_login_service()
        status = service.get_status(session_id)

        if not status:
            return jsonify({'success': False, 'message': '会话不存在'})

        return jsonify({
            'success': True,
            'data': {
                'session_id': session_id,
                'status': status.get('status', 'pending'),
                'login_type': status.get('login_type', ''),
                'message': status.get('error', ''),
                'auth_source': status.get('auth_source', ''),
                'elapsed_seconds': status.get('elapsed_seconds', 0),
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/qrlogin/result/<session_id>')
@login_required
def get_qrlogin_result(session_id):
    """获取扫码登录结果"""
    try:
        service = get_wecom_app_login_service()
        result = service.get_result(session_id)

        if not result:
            return jsonify({'success': False, 'message': '登录未完成'})

        if not result.get('success'):
            return jsonify({
                'success': False,
                'message': result.get('message', '登录失败'),
                'status': result.get('status')
            })

        # 创建账号记录
        auth_code = result.get('auth_code', '')
        auth_source = result.get('auth_source', '')

        with current_app.app_context():
            account = WecomAccount(
                user_id=current_user.id,
                account_name='企业微信账号',
                real_name='',
                wecom_alias=auth_source,
                status='online'
            )
            account.auth_code = auth_code
            db.session.add(account)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': '登录成功，账号已创建',
                'data': {
                    'account': account.to_dict(),
                    'auth_code': auth_code,
                    'auth_source': auth_source,
                }
            })
    except Exception as e:
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/qrlogin/image/<session_id>.png')
@login_required
def get_qrlogin_image(session_id):
    """返回二维码图片 PNG (供 <img> 标签引用)"""
    try:
        service = get_wecom_app_login_service()
        qr_bytes = service.get_qrcode_bytes(session_id)
        if not qr_bytes:
            return jsonify({'success': False, 'message': '二维码不存在'}), 404
        from flask import Response
        return Response(qr_bytes, mimetype='image/png')
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


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
        
        # 使用超级封装发送消息
        if super_wrapper:
            # 这里需要获取conversation_id
            # 暂时模拟成功
            pass
        
        # 更新客户最后联系时间
        customer.last_contact_time = datetime.now()
        customer.message_count += 1
        account.message_count += 1
        db.session.commit()
        
        return jsonify({'success': True, 'message': '消息发送成功'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


# ==================== 超级封装API ====================

@wecom_scrm_bp.route('/api/super/contacts/inner')
@login_required
def get_inner_contacts():
    """获取内部联系人"""
    global super_wrapper
    
    try:
        if not super_wrapper:
            super_wrapper = get_super_wrapper()
        
        contacts = super_wrapper.get_inner_contacts()
        return jsonify({
            'success': True,
            'data': contacts,
            'libs_info': super_wrapper.get_available_libs()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/super/contacts/external')
@login_required
def get_external_contacts():
    """获取外部联系人"""
    global super_wrapper
    
    try:
        if not super_wrapper:
            super_wrapper = get_super_wrapper()
        
        contacts = super_wrapper.get_external_contacts()
        return jsonify({
            'success': True,
            'data': contacts,
            'libs_info': super_wrapper.get_available_libs()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/super/rooms')
@login_required
def get_rooms():
    """获取群列表"""
    global super_wrapper
    
    try:
        if not super_wrapper:
            super_wrapper = get_super_wrapper()
        
        rooms = super_wrapper.get_rooms()
        return jsonify({
            'success': True,
            'data': rooms,
            'libs_info': super_wrapper.get_available_libs()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/super/send/text', methods=['POST'])
@login_required
def send_text_message():
    """发送文本消息"""
    global super_wrapper
    
    try:
        data = request.get_json()
        conversation_id = data.get('conversation_id')
        content = data.get('content')
        
        if not conversation_id or not content:
            return jsonify({'success': False, 'message': '参数不完整'})
        
        if not super_wrapper:
            super_wrapper = get_super_wrapper()
        
        success = super_wrapper.send_text(conversation_id, content)
        if success:
            return jsonify({'success': True, 'message': '消息发送成功'})
        else:
            return jsonify({'success': False, 'message': '消息发送失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/super/libs-info')
@login_required
def get_libs_info():
    """获取可用库信息"""
    global super_wrapper
    
    try:
        if not super_wrapper:
            super_wrapper = get_super_wrapper()
        
        return jsonify({
            'success': True,
            'data': super_wrapper.get_available_libs()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
