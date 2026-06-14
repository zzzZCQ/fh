# -*- coding: utf-8 -*-
"""
企业微信 SCRM 三方托管 - 路由层
================================
路由规划:
  GET  /wecom-scrm/config                  配置页（admin）
  POST /wecom-scrm/config/save             保存配置
  POST /wecom-scrm/config/test             测试连接

  GET  /wecom-scrm/accounts                托管账号列表
  POST /wecom-scrm/account/add             新增托管账号
  POST /wecom-scrm/account/delete/<id>     删除账号
  POST /wecom-scrm/account/update/<id>     更新账号信息
  GET  /wecom-scrm/account/sync/<id>       同步账号客户数据

  GET  /wecom-scrm/customers               客户管理（选择账号 + 搜索 + 分页）
  GET  /wecom-scrm/customer/detail/<id>    客户详情
"""

import json
import time
import threading
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import current_user, login_required

from models import db, WecomConfig, WecomAccount, WecomCustomer, _now_bj
from helpers import role_required, get_unread_count
from wecom_scrm_service import WecomScrmService, create_wecom_service, test_connection


bp = Blueprint('wecom_scrm', __name__)


# ============================================================
# 配置管理
# ============================================================

@bp.route('/wecom-scrm/config', methods=['GET'])
@role_required('admin')
def config_page():
    """SCRM 配置页面"""
    cfg = WecomConfig.get_active_config()
    account_count = WecomAccount.query.count()
    customer_count = WecomCustomer.query.count()
    return render_template(
        'wecom_scrm_config.html',
        config=cfg,
        account_count=account_count,
        customer_count=customer_count,
        unread_count=get_unread_count(current_user.id),
    )


@bp.route('/wecom-scrm/config/save', methods=['POST'])
@role_required('admin')
def config_save():
    """保存 SCRM 配置"""
    cfg = WecomConfig.get_active_config()

    cfg.corp_id = request.form.get('corp_id', '').strip()
    cfg.agent_id = request.form.get('agent_id', '').strip()
    cfg.secret = request.form.get('secret', '').strip()
    cfg.qr_app_id = request.form.get('qr_app_id', '').strip()
    cfg.qr_app_secret = request.form.get('qr_app_secret', '').strip()
    cfg.qr_redirect_uri = request.form.get('qr_redirect_uri', '').strip()
    cfg.contact_secret = request.form.get('contact_secret', '').strip()
    cfg.message_token = request.form.get('message_token', '').strip()
    cfg.message_aes_key = request.form.get('message_aes_key', '').strip()

    try:
        db.session.commit()
        flash('配置已保存！', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'保存失败: {e}', 'danger')

    return redirect(url_for('wecom_scrm.config_page'))


@bp.route('/wecom-scrm/config/test', methods=['POST'])
@role_required('admin')
def config_test():
    """测试企业微信 API 连接"""
    corp_id = request.form.get('corp_id', '').strip()
    contact_secret = request.form.get('contact_secret', '').strip()

    if not corp_id or not contact_secret:
        return jsonify({'success': False, 'message': '企业ID或客户联系Secret不能为空'})

    try:
        ok, msg = test_connection(corp_id, contact_secret)
        return jsonify({'success': ok, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': f'测试异常: {e}'})


# ============================================================
# 托管账号管理
# ============================================================

# ============================================================
# 扫码托管（新增托管账号的扫码方式）
# ============================================================

@bp.route('/wecom-scrm/account/scan-login', methods=['GET'])
@login_required
def account_scan_login():
    """生成扫码托管二维码页面

    流程:
      1. 检查配置（需要 corp_id + 扫码应用 agentid + 扫码应用 secret）
      2. 构造企微扫码URL（回调指向 account_callback）
      3. 渲染二维码，用户扫码后企微回跳回调地址
      4. 回调中用 code 换成员信息，自动创建 WecomAccount
    """
    cfg = WecomConfig.get_active_config()

    if not cfg.corp_id or not cfg.contact_secret:
        flash('请先在 SCRM 配置页填写 企业ID 和 客户联系Secret！', 'danger')
        return redirect(url_for('wecom_scrm.config_page'))

    # 构造回调地址
    # - 优先使用配置中的 qr_redirect_uri（与企微管理后台配置的"授权完成回调域名"必须完全一致）
    # - 未配置则回退到当前请求的外部地址（仅适用于本机调试）
    if cfg.qr_redirect_uri:
        redirect_uri = cfg.qr_redirect_uri.strip()
    else:
        redirect_uri = url_for('wecom_scrm.account_callback', _external=True)

    # 生成企微扫码URL
    svc = create_wecom_service(cfg.corp_id, cfg.contact_secret)
    qr_info = svc.get_qr_connect_url(
        redirect_uri=redirect_uri,
        agentid=cfg.agent_id or '',
        state=f'host_{current_user.id}',
    )

    return render_template(
        'wecom_scrm_qr_login.html',
        qr_url=qr_info['qr_url'],
        redirect_uri=qr_info['redirect_uri'],
        config=cfg,
        follow_users=[],
        unread_count=get_unread_count(current_user.id),
    )


@bp.route('/wecom-scrm/account/callback', methods=['GET'])
def account_callback():
    """企微扫码回调处理

    企微扫码成功后回跳: /wecom-scrm/account/callback?code=CODE&state=STATE
    流程:
      1. 解析 code 和 state
      2. 用 code 调 API 获取成员 userid
      3. 用 userid 调 API 获取成员详情（姓名、头像等）
      4. 检查该 wecom_id 是否已存在（存在则更新，不存在则创建）
      5. 跳回账号列表页
    """
    code = request.args.get('code', '')
    state = request.args.get('state', '')

    if not code:
        flash('扫码回调缺少 code 参数', 'danger')
        return redirect(url_for('wecom_scrm.accounts_list'))

    cfg = WecomConfig.get_active_config()
    if not cfg.corp_id or not cfg.contact_secret:
        flash('企微配置不完整，请先在SCRM配置页填写', 'danger')
        return redirect(url_for('wecom_scrm.config_page'))

    # 解析 state 中的归属用户ID
    owner_user_id = current_user.id
    try:
        if state.startswith('host_'):
            owner_user_id = int(state.split('_')[1])
    except (ValueError, IndexError):
        pass

    try:
        svc = create_wecom_service(cfg.corp_id, cfg.contact_secret)

        # 1. code 换成员 userid
        userinfo = svc.get_userinfo_by_code(code)
        wecom_userid = userinfo.get('UserId') or userinfo.get('userid')
        if not wecom_userid:
            flash(f'扫码回调未获取到成员ID（返回：{userinfo}）', 'danger')
            return redirect(url_for('wecom_scrm.accounts_list'))

        # 2. 拉取成员详情
        detail = svc.get_user_detail(wecom_userid)
        if detail.get('errcode') != 0:
            # 退而求其次，只存 userid
            name = wecom_userid
            avatar = ''
        else:
            name = detail.get('name', wecom_userid)
            avatar = detail.get('avatar', '')

        # 3. 检查是否已存在该企微ID账号
        exist = WecomAccount.query.filter_by(wecom_id=wecom_userid).first()
        if exist:
            exist.account_name = name
            exist.real_name = name
            exist.status = 'online'
            exist.last_login_time = _now_bj()
            db.session.commit()
            flash(f'账号"{name}"扫码登录成功，已更新', 'success')
        else:
            account = WecomAccount(
                user_id=owner_user_id,
                account_name=name,
                real_name=name,
                wecom_id=wecom_userid,
                wecom_alias=name,
                status='online',
                last_login_time=_now_bj(),
                customer_count=0,
            )
            db.session.add(account)
            db.session.commit()
            flash(f'托管账号"{name}"已添加成功，企微ID：{wecom_userid}', 'success')

    except Exception as e:
        flash(f'扫码回调失败: {e}', 'danger')

    return redirect(url_for('wecom_scrm.accounts_list'))


# ============================================================
# 托管账号列表
# ============================================================

@bp.route('/wecom-scrm/accounts', methods=['GET'])
@login_required
def accounts_list():
    """托管账号列表"""
    page = request.args.get('page', 1, type=int)
    keyword = request.args.get('keyword', '').strip()
    status = request.args.get('status', '')

    query = WecomAccount.query

    # 权限：admin 可见全部，其他角色只能看到自己的账号
    if not current_user.has_role('admin'):
        query = query.filter_by(user_id=current_user.id)

    if keyword:
        query = query.filter(
            (WecomAccount.account_name.contains(keyword)) |
            (WecomAccount.real_name.contains(keyword)) |
            (WecomAccount.wecom_alias.contains(keyword))
        )
    if status:
        query = query.filter_by(status=status)

    accounts = query.order_by(WecomAccount.create_time.desc()).paginate(
        page=page, per_page=10, error_out=False
    )

    # 生成扫码托管二维码 URL（用于弹窗展示）
    cfg = WecomConfig.get_active_config()
    qr_url = None
    qr_error = None
    if cfg.corp_id and cfg.contact_secret:
        try:
            if cfg.qr_redirect_uri:
                redirect_uri = cfg.qr_redirect_uri.strip()
            else:
                redirect_uri = url_for('wecom_scrm.account_callback', _external=True)
            svc = create_wecom_service(cfg.corp_id, cfg.contact_secret)
            qr_info = svc.get_qr_connect_url(
                redirect_uri=redirect_uri,
                agentid=cfg.agent_id or '',
                state=f'host_{current_user.id}',
            )
            qr_url = qr_info['qr_url']
        except Exception as e:
            qr_error = str(e)

    return render_template(
        'wecom_scrm_accounts.html',
        accounts=accounts,
        keyword=keyword,
        status=status,
        qr_url=qr_url,
        qr_error=qr_error,
        unread_count=get_unread_count(current_user.id),
    )


@bp.route('/wecom-scrm/account/add', methods=['POST'])
@login_required
def account_add():
    """新增托管账号"""
    account_name = request.form.get('account_name', '').strip()
    wecom_id = request.form.get('wecom_id', '').strip()
    wecom_alias = request.form.get('wecom_alias', '').strip()

    if not account_name:
        flash('账号名称不能为空！', 'danger')
        return redirect(url_for('wecom_scrm.accounts_list'))

    # admin 可以指定归属用户；普通用户只能给自己加账号
    user_id = current_user.id
    if current_user.has_role('admin'):
        user_id_val = request.form.get('user_id', '')
        if user_id_val:
            try:
                user_id = int(user_id_val)
            except (ValueError, TypeError):
                pass

    account = WecomAccount(
        user_id=user_id,
        account_name=account_name,
        wecom_id=wecom_id,
        wecom_alias=wecom_alias,
        status='offline',
    )
    try:
        db.session.add(account)
        db.session.commit()
        flash(f'账号"{account_name}"已添加，请扫码登录！', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'添加失败: {e}', 'danger')

    return redirect(url_for('wecom_scrm.accounts_list'))


@bp.route('/wecom-scrm/account/delete/<int:account_id>', methods=['POST'])
@login_required
def account_delete(account_id: int):
    """删除托管账号"""
    account = WecomAccount.query.get(account_id)
    if not account:
        flash('账号不存在', 'danger')
        return redirect(url_for('wecom_scrm.accounts_list'))

    # 权限检查：只有 admin 或账号所有者能删除
    if account.user_id != current_user.id and not current_user.has_role('admin'):
        flash('无权删除此账号', 'danger')
        return redirect(url_for('wecom_scrm.accounts_list'))

    try:
        # 先删客户数据
        WecomCustomer.query.filter_by(account_id=account_id).delete()
        db.session.delete(account)
        db.session.commit()
        flash('账号及关联客户数据已删除', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败: {e}', 'danger')

    return redirect(url_for('wecom_scrm.accounts_list'))


@bp.route('/wecom-scrm/account/update/<int:account_id>', methods=['POST'])
@login_required
def account_update(account_id: int):
    """更新账号信息"""
    account = WecomAccount.query.get(account_id)
    if not account:
        flash('账号不存在', 'danger')
        return redirect(url_for('wecom_scrm.accounts_list'))

    if account.user_id != current_user.id and not current_user.has_role('admin'):
        flash('无权操作此账号', 'danger')
        return redirect(url_for('wecom_scrm.accounts_list'))

    account.account_name = request.form.get('account_name', account.account_name)
    account.wecom_id = request.form.get('wecom_id', account.wecom_id) or ''
    account.wecom_alias = request.form.get('wecom_alias', account.wecom_alias) or ''
    account.real_name = request.form.get('real_name', account.real_name) or ''

    try:
        db.session.commit()
        flash('账号信息已更新', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'更新失败: {e}', 'danger')

    return redirect(url_for('wecom_scrm.accounts_list'))


@bp.route('/wecom-scrm/account/sync/<int:account_id>', methods=['POST', 'GET'])
@login_required
def account_sync(account_id: int):
    """同步账号的客户数据（调用企业微信API拉取外部联系人）"""
    account = WecomAccount.query.get(account_id)
    if not account:
        return jsonify({'success': False, 'message': '账号不存在'})

    if account.user_id != current_user.id and not current_user.has_role('admin'):
        return jsonify({'success': False, 'message': '无权操作此账号'})

    if not account.wecom_id:
        return jsonify({'success': False, 'message': '账号未配置企微用户ID（wecom_id）'})

    # 使用配置
    cfg = WecomConfig.get_active_config()
    if not cfg.corp_id or not cfg.contact_secret:
        return jsonify({'success': False, 'message': '请先在SCRM配置页填写企业ID和客户联系Secret'})

    try:
        svc = create_wecom_service(cfg.corp_id, cfg.contact_secret)

        # 1. 获取该成员的客户详情
        customers = svc.sync_all_customers_for_user(account.wecom_id)

        # 2. 写入数据库（覆盖式，先删后插）
        WecomCustomer.query.filter_by(account_id=account.id).delete()

        for c in customers:
            cust = WecomCustomer(
                account_id=account.id,
                external_user_id=c.get('external_userid', ''),
                name=c.get('name', ''),
                avatar=c.get('avatar', ''),
                gender=c.get('gender', ''),
                position=c.get('position', ''),
                corp_name=c.get('corp_name', ''),
                remark=c.get('remark', ''),
                tags=c.get('tags', ''),
                status='normal',
            )
            db.session.add(cust)

        account.customer_count = len(customers)
        account.last_sync_time = time.strftime('%Y-%m-%d %H:%M:%S')
        account.status = 'online'
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'同步成功，共 {len(customers)} 个客户',
            'count': len(customers),
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'同步异常: {e}'})


# ============================================================
# 客户管理
# ============================================================

@bp.route('/wecom-scrm/customers', methods=['GET'])
@login_required
def customers_list():
    """客户管理页面（选择账号 + 搜索 + 分页）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    keyword = request.args.get('keyword', '').strip()
    account_id = request.args.get('account_id', '', type=str)
    gender = request.args.get('gender', '')

    # 构建账号下拉列表（权限控制）
    if current_user.has_role('admin'):
        accounts = WecomAccount.query.all()
    else:
        accounts = WecomAccount.query.filter_by(user_id=current_user.id).all()

    # 客户查询
    if current_user.has_role('admin'):
        query = WecomCustomer.query
    else:
        # 非admin只能看自己账号下的客户
        my_account_ids = [a.id for a in accounts]
        query = WecomCustomer.query.filter(WecomCustomer.account_id.in_(my_account_ids))

    if account_id and account_id.isdigit():
        query = query.filter_by(account_id=int(account_id))
    if keyword:
        query = query.filter(
            (WecomCustomer.name.contains(keyword)) |
            (WecomCustomer.remark.contains(keyword)) |
            (WecomCustomer.corp_name.contains(keyword))
        )
    if gender:
        query = query.filter_by(gender=gender)

    customers = query.order_by(
        WecomCustomer.create_time.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    # 关联账号名称
    account_name_map = {a.id: a.account_name for a in accounts}

    return render_template(
        'wecom_scrm_customers.html',
        customers=customers,
        accounts=accounts,
        account_name_map=account_name_map,
        keyword=keyword,
        account_id=account_id,
        gender=gender,
        unread_count=get_unread_count(current_user.id),
    )


@bp.route('/wecom-scrm/customer/detail/<int:customer_id>', methods=['GET'])
@login_required
def customer_detail(customer_id: int):
    """客户详情"""
    customer = WecomCustomer.query.get(customer_id)
    if not customer:
        flash('客户不存在', 'danger')
        return redirect(url_for('wecom_scrm.customers_list'))

    # 权限检查
    account = WecomAccount.query.get(customer.account_id)
    if not account or (account.user_id != current_user.id and not current_user.has_role('admin')):
        flash('无权查看此客户', 'danger')
        return redirect(url_for('wecom_scrm.customers_list'))

    return jsonify({
        'success': True,
        'customer': {
            'id': customer.id,
            'external_user_id': customer.external_user_id,
            'name': customer.name,
            'avatar': customer.avatar,
            'gender': customer.gender,
            'position': customer.position,
            'corp_name': customer.corp_name,
            'remark': customer.remark,
            'tags': customer.tags,
            'status': customer.status,
            'first_contact_time': str(customer.first_contact_time) if customer.first_contact_time else '',
            'last_contact_time': str(customer.last_contact_time) if customer.last_contact_time else '',
            'account_name': account.account_name,
        }
    })


# ============================================================
# 扫码登录（管理后台扫码，用于验证企微配置）
# ============================================================

@bp.route('/wecom-scrm/admin/qr-login', methods=['GET'])
@role_required('admin')
def admin_qr_login():
    """企微管理后台扫码登录测试页面"""
    cfg = WecomConfig.get_active_config()
    if not cfg.corp_id or not cfg.contact_secret:
        flash('请先配置企业ID和客户联系Secret！', 'warning')
        return redirect(url_for('wecom_scrm.config_page'))

    # 测试连接
    try:
        ok, msg = test_connection(cfg.corp_id, cfg.contact_secret)
        if not ok:
            flash(f'企微连接失败: {msg}', 'danger')
            return redirect(url_for('wecom_scrm.config_page'))

        svc = create_wecom_service(cfg.corp_id, cfg.contact_secret)

        # 获取有客户联系权限的成员
        follow_users = svc.get_follow_user_list()

        return render_template(
            'wecom_scrm_qr_login.html',
            config=cfg,
            follow_users=follow_users,
            unread_count=get_unread_count(current_user.id),
        )
    except Exception as e:
        flash(f'企微API调用失败: {e}', 'danger')
        return redirect(url_for('wecom_scrm.config_page'))
