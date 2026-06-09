# -*- coding: utf-8 -*-
"""
企微账号托管 - 路由层
===================

核心接口（多账号并发，session_id 隔离）：

    POST /admin/wecom-scrm/api/login/start        → 开始扫码登录，返回 session_id + 二维码
    GET  /admin/wecom-scrm/api/login/status/<sid>  → 轮询登录状态
    POST /admin/wecom-scrm/api/login/confirm/<sid> → 登录成功后创建/绑定账号
    GET  /admin/wecom-scrm/api/accounts            → 获取当前用户托管账号列表
    DELETE /admin/wecom-scrm/api/accounts/<id>     → 删除账号
    GET  /admin/wecom-scrm/api/sessions/<sid>/contacts → 获取联系人
    POST /admin/wecom-scrm/api/sessions/<sid>/send    → 发送消息
    GET  /admin/wecom-scrm/api/protocols           → 获取可用协议列表

设计原则：
    - 所有 session 都有 session_id，并发登录互不影响
    - 登录成功后通过 confirm 创建账号记录并保存 cookie 到 DB
    - 协议（ipad/mock/hook）透明切换
"""

import json
import threading
from datetime import datetime
from flask import (
    Blueprint, render_template, request, jsonify,
    current_app,
)
from flask_login import login_required, current_user

from models import db, WecomAccount
from wecom_hosting_service import (
    get_hosting_service,
    AccountHostingService,
)
from wecom_protocols import (
    LOGIN_STATUS_ONLINE,
    LOGIN_STATUS_SUCCESS,
    LOGIN_STATUS_PENDING,
    LOGIN_STATUS_SCANNED,
    LOGIN_STATUS_EXPIRED,
    LOGIN_STATUS_FAILED,
)


wecom_scrm_bp = Blueprint(
    'wecom_scrm', __name__,
    url_prefix='/admin/wecom-scrm',
    template_folder='templates',
)


# ============================================================
# 页面路由
# ============================================================

@wecom_scrm_bp.route('/')
@login_required
def index_page():
    """SCRM 首页"""
    return render_template('wecom_scrm/index.html')


# ============================================================
# 扫码登录 API（兼容旧版前端调用）
# ============================================================

@wecom_scrm_bp.route('/api/qrlogin/create')
@login_required
def api_qrlogin_create():
    """创建登录二维码（兼容旧版前端）"""
    login_type = request.args.get('login_type', 'wwclient')
    try:
        service: AccountHostingService = get_hosting_service()
        ok, msg, session = service.start_login(
            user_id=current_user.id,
            protocol_name='ipad',
            account_id=None,
        )

        if not ok or session is None:
            return jsonify({
                'success': False,
                'message': msg or '创建登录失败',
            })

        return jsonify({
            'success': True,
            'data': {
                'session_id': session.session_id,
                'qrcode': session.qrcode_data_url,
                'protocol': session.protocol.protocol_name,
            },
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'启动失败: {e}'})


@wecom_scrm_bp.route('/api/qrlogin/status/<session_id>')
@login_required
def api_qrlogin_status(session_id: str):
    """查询扫码状态（兼容旧版前端）"""
    service: AccountHostingService = get_hosting_service()
    session = service.get_session(session_id)
    if session is None:
        return jsonify({
            'success': False,
            'message': 'session 不存在或已过期',
            'data': {'status': 'expired'},
        })
    if session.user_id != current_user.id:
        return jsonify({'success': False, 'message': '无权限'})

    status = service.poll_status(session_id) or {}
    return jsonify({'success': True, 'data': status})


@wecom_scrm_bp.route('/api/qrlogin/result/<session_id>')
@login_required
def api_qrlogin_result(session_id: str):
    """获取登录结果（兼容旧版前端）"""
    service: AccountHostingService = get_hosting_service()
    session = service.get_session(session_id)
    if session is None or session.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'session 不存在'})

    info = session.protocol.get_login_info() or {}
    return jsonify({
        'success': True,
        'data': {
            'login_info': info,
            'account': {
                'account_name': info.get('name') or info.get('user_id') or '企业微信账号',
            } if info else None,
        },
    })


# ============================================================
# 元信息 API
# ============================================================

@wecom_scrm_bp.route('/api/protocols')
@login_required
def api_protocols():
    """返回当前系统可用协议（给前端展示）"""
    service: AccountHostingService = get_hosting_service()
    return jsonify({
        'success': True,
        'data': {
            'protocols': service.get_available_protocols_info(),
            'default': service.get_default_protocol(),
            'stats': service.stats(),
        },
    })


# ============================================================
# 登录流程 API
# ============================================================

@wecom_scrm_bp.route('/api/login/start', methods=['POST'])
@login_required
def api_login_start():
    """开始登录流程

    请求体（可选）：{ "protocol": "ipad", "account_id": null }
    返回：{ success, data: { session_id, qrcode, protocol } }
        qrcode 是 data:image/png;base64,... 或 null (hook 协议无二维码)
    """
    try:
        data = request.get_json(silent=True) or {}
        protocol_name = data.get('protocol') or 'ipad'
        account_id = data.get('account_id')  # 可能为 None
        if isinstance(account_id, int) and account_id <= 0:
            account_id = None

        service: AccountHostingService = get_hosting_service()
        ok, msg, session = service.start_login(
            user_id=current_user.id,
            protocol_name=protocol_name,
            account_id=account_id,
        )

        if not ok or session is None:
            return jsonify({
                'success': False,
                'message': msg or '创建登录失败',
                'data': {'protocols': service.get_available_protocols_info()},
            })

        return jsonify({
            'success': True,
            'message': '请使用企业微信扫描二维码登录',
            'data': {
                'session_id': session.session_id,
                'qrcode': session.qrcode_data_url,
                'protocol': session.protocol.protocol_name,
                'status': session.protocol.status,
            },
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'启动失败: {e}'})


@wecom_scrm_bp.route('/api/login/status/<session_id>')
@login_required
def api_login_status(session_id: str):
    """轮询某个 session 的登录状态"""
    try:
        service: AccountHostingService = get_hosting_service()
        # 安全校验：只允许查询自己的 session
        session = service.get_session(session_id)
        if session is None:
            return jsonify({
                'success': False,
                'message': 'session 不存在或已过期',
                'data': {'status': 'expired'},
            })
        if session.user_id != current_user.id:
            return jsonify({'success': False, 'message': '无权限'})

        status = service.poll_status(session_id) or {}

        # 如果登录成功，自动创建账号记录（仅第一次，且 account_id 为空时）
        if status.get('status') in (LOGIN_STATUS_SUCCESS, LOGIN_STATUS_ONLINE):
            if not session.account_id:
                _auto_create_account_locked(session)

        return jsonify({'success': True, 'data': status})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


_account_creation_lock = threading.Lock()


def _auto_create_account_locked(session):
    """登录成功后自动创建账号记录（带锁，避免重复创建）"""
    with _account_creation_lock:
        if session.account_id:
            return  # 已创建
        try:
            with current_app.app_context():
                info = session.protocol.get_login_info() or {}
                name = info.get('name') or info.get('user_id') or f'企微账号_{session.session_id[:8]}'
                real_name = info.get('name') or ''
                alias = info.get('corp_name') or ''

                # 检查是否已存在同名账号
                existing = WecomAccount.query.filter_by(
                    user_id=session.user_id,
                    account_name=name,
                    is_active=True,
                ).first()
                if existing:
                    session.account_id = existing.id
                    # 更新状态
                    existing.status = 'online'
                    existing.last_login_time = datetime.now()
                    # 保存 session 数据
                    try:
                        sess_data = session.protocol.get_session_data()
                        existing.cookies = json.dumps(sess_data, ensure_ascii=False)
                    except Exception:
                        pass
                    db.session.commit()
                    return

                account = WecomAccount(
                    user_id=session.user_id,
                    account_name=name,
                    real_name=real_name,
                    wecom_alias=alias,
                    status='online',
                    last_login_time=datetime.now(),
                )
                # 保存 cookies/session 数据
                try:
                    sess_data = session.protocol.get_session_data()
                    account.cookies = json.dumps(sess_data, ensure_ascii=False)
                except Exception:
                    pass

                db.session.add(account)
                db.session.commit()
                session.account_id = account.id
        except Exception as e:
            print(f'[WeComSCRM] 自动创建账号失败: {e}')
            try:
                db.session.rollback()
            except Exception:
                pass


@wecom_scrm_bp.route('/api/login/close/<session_id>', methods=['POST'])
@login_required
def api_login_close(session_id: str):
    """关闭某个登录会话（取消扫码/释放资源）"""
    service: AccountHostingService = get_hosting_service()
    session = service.get_session(session_id)
    if session and session.user_id == current_user.id:
        service.close_session(session_id)
        return jsonify({'success': True, 'message': '已关闭'})
    return jsonify({'success': False, 'message': 'session 不存在或无权限'})


# ============================================================
# 账号管理 API
# ============================================================

@wecom_scrm_bp.route('/api/accounts')
@login_required
def api_accounts_list():
    """当前用户托管账号列表"""
    try:
        accounts = WecomAccount.query.filter_by(
            user_id=current_user.id,
            is_active=True,
        ).order_by(WecomAccount.update_time.desc()).all()

        service: AccountHostingService = get_hosting_service()
        sessions_by_id = {
            s.account_id: s for s in service.get_user_sessions(current_user.id)
            if s.account_id
        }

        data = []
        for acc in accounts:
            d = acc.to_dict()
            # 如果有活跃 session，更新状态
            if acc.id in sessions_by_id:
                s = sessions_by_id[acc.id]
                d['status'] = s.protocol.status if s.protocol.status != LOGIN_STATUS_PENDING else d.get('status', 'online')
                d['has_active_session'] = True
                d['session_id'] = s.session_id
            else:
                d['has_active_session'] = False
            data.append(d)

        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/accounts', methods=['POST'])
@login_required
def api_accounts_create():
    """手动创建账号（通常不需要，登录成功会自动创建）"""
    try:
        data = request.get_json(silent=True) or {}
        name = (data.get('account_name') or '').strip()
        if not name:
            return jsonify({'success': False, 'message': '请填写账号名称'})
        account = WecomAccount(
            user_id=current_user.id,
            account_name=name,
            real_name=data.get('real_name', ''),
            wecom_alias=data.get('wecom_alias', ''),
            status='offline',
        )
        db.session.add(account)
        db.session.commit()
        return jsonify({'success': True, 'data': account.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/accounts/<int:account_id>', methods=['DELETE'])
@login_required
def api_accounts_delete(account_id: int):
    """删除/停用账号"""
    try:
        account = WecomAccount.query.get(account_id)
        if not account or account.user_id != current_user.id:
            return jsonify({'success': False, 'message': '账号不存在'})

        account.is_active = False
        account.status = 'offline'

        # 同时关闭可能存在的活跃 session
        service: AccountHostingService = get_hosting_service()
        for s in service.get_user_sessions(current_user.id):
            if s.account_id == account_id:
                service.close_session(s.session_id)

        db.session.commit()
        return jsonify({'success': True, 'message': '已删除'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


# ============================================================
# 数据与消息 API
# ============================================================

@wecom_scrm_bp.route('/api/sessions/<session_id>/contacts')
@login_required
def api_session_contacts(session_id: str):
    """获取 session 的联系人列表"""
    service: AccountHostingService = get_hosting_service()
    session = service.get_session(session_id)
    if not session or session.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'session 不存在'})
    try:
        contacts = service.get_contacts(session_id)
        return jsonify({'success': True, 'data': contacts or []})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/sessions/<session_id>/rooms')
@login_required
def api_session_rooms(session_id: str):
    """获取 session 的群列表"""
    service: AccountHostingService = get_hosting_service()
    session = service.get_session(session_id)
    if not session or session.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'session 不存在'})
    try:
        rooms = service.get_rooms(session_id)
        return jsonify({'success': True, 'data': rooms or []})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@wecom_scrm_bp.route('/api/sessions/<session_id>/send', methods=['POST'])
@login_required
def api_session_send(session_id: str):
    """通过 session 发送消息

    请求体: { "conversation_id": "xxx", "content": "消息内容", "msg_type": "text" }
    """
    service: AccountHostingService = get_hosting_service()
    session = service.get_session(session_id)
    if not session or session.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'session 不存在'})

    try:
        data = request.get_json(silent=True) or {}
        conversation_id = (data.get('conversation_id') or '').strip()
        content = (data.get('content') or '').strip()
        msg_type = data.get('msg_type') or 'text'

        if not conversation_id or not content:
            return jsonify({'success': False, 'message': '参数不完整'})

        ok = service.send_message(session_id, conversation_id, content, msg_type)
        if ok:
            # 更新账号最后活跃时间
            if session.account_id:
                try:
                    with current_app.app_context():
                        acc = WecomAccount.query.get(session.account_id)
                        if acc:
                            acc.message_count = (acc.message_count or 0) + 1
                            db.session.commit()
                except Exception:
                    pass
            return jsonify({'success': True, 'message': '已发送'})
        return jsonify({'success': False, 'message': '发送失败（可能需要重新登录）'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
