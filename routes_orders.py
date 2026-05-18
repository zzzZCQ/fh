# -*- coding: utf-8 -*-
"""订单管理路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime

from models import db, User, Order, Group, Category
from helpers import role_required, get_unread_count, get_active_categories, get_active_gifts, notify_users

bp = Blueprint('orders', __name__)


# ============ 统一订单管理路由 ============
@bp.route('/')
@bp.route('/dashboard')
@login_required
def dashboard():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    if per_page not in [10, 50, 100]:
        per_page = 10
    customer_keyword = request.args.get('customer_keyword', '').strip()
    tracking_keyword = request.args.get('tracking_keyword', '').strip()
    category_filter = request.args.get('category', '').strip()
    salesman_filter = request.args.get('salesman_id', '').strip()
    status_filter = request.args.get('status', '').strip()
    group_filter = request.args.get('group_id', '').strip()
    month_filter = request.args.get('month', '').strip()

    is_admin = current_user.has_role('admin')
    is_salesman = current_user.has_role('salesman') and not is_admin
    is_shipper = current_user.has_role('shipper') and not is_admin

    # 构建查询
    if is_salesman:
        query = Order.query.filter_by(salesman_id=current_user.id)
    elif is_shipper:
        query = Order.query.filter(Order.status != 'draft')
        if current_user.group_id:
            managed_group_ids = current_user.get_managed_group_ids()
            query = query.filter(Order.group_id.in_(managed_group_ids))
    else:
        # 管理员
        query = Order.query
        if current_user.username != 'admin' and current_user.group_id:
            managed_group_ids = current_user.get_managed_group_ids()
            query = query.filter(Order.group_id.in_(managed_group_ids))

    if customer_keyword:
        query = query.filter(Order.customer_name.contains(customer_keyword))
    if tracking_keyword:
        query = query.filter(Order.tracking_number.contains(tracking_keyword))
    if category_filter:
        query = query.filter(Order.category == category_filter)
    if salesman_filter and not is_salesman:
        query = query.filter(Order.salesman_id == salesman_filter)
    if status_filter:
        query = query.filter(Order.status == status_filter)
    if group_filter and is_admin:
        query = query.filter(Order.group_id == group_filter)
    if month_filter:
        try:
            year, month = month_filter.split('-')
            from calendar import monthrange
            start_date = datetime(int(year), int(month), 1)
            end_date = datetime(int(year), int(month), monthrange(int(year), int(month))[1], 23, 59, 59)
            query = query.filter(Order.create_time >= start_date, Order.create_time <= end_date)
        except (ValueError, IndexError):
            pass
    orders = query.order_by(Order.create_time.desc()).paginate(page=page, per_page=per_page)
    
    # 业务员筛选：可见范围是本级及下级
    salesman_query = User.query.filter(User.roles.like('%salesman%'))
    if is_admin and current_user.username == 'admin':
        # admin 管理员可以看到所有业务员
        pass
    elif current_user.group_id:
        # 其他用户只能看到自己组别及下级组别的业务员
        visible_group_ids = current_user.get_managed_group_ids()
        salesman_query = salesman_query.filter(User.group_id.in_(visible_group_ids))
    salesmen = salesman_query.all()

    # 汇总统计（基于当前筛选条件的全部数据，不分页）
    import re
    summary_query = query  # 复用当前筛选条件
    all_orders = summary_query.all()

    total_paid = 0  # 已付定金汇总（只取数字部分）
    total_collect = 0  # 代收金额汇总
    signed_amount = 0  # 已签收金额
    for o in all_orders:
        if o.paid_amount:
            num_match = re.match(r'^(\d+(?:\.\d+)?)', str(o.paid_amount))
            if num_match:
                total_paid += float(num_match.group(1))
        if o.collect_amount:
            total_collect += float(o.collect_amount)
        # 已签收金额
        if o.logistics_status == '已签收':
            if o.paid_amount:
                num_match = re.match(r'^(\d+(?:\.\d+)?)', str(o.paid_amount))
                if num_match:
                    signed_amount += float(num_match.group(1))
            if o.collect_amount:
                signed_amount += float(o.collect_amount)
    total_performance = total_paid + total_collect  # 总业绩

    # 组别筛选列表：管理员本级及以下
    filter_groups = []
    if is_admin:
        if current_user.username == 'admin':
            filter_groups = Group.query.filter_by(is_active=True).order_by(Group.level.asc(), Group.create_time.asc()).all()
        elif current_user.group_id:
            managed_group_ids = current_user.get_managed_group_ids()
            filter_groups = Group.query.filter(Group.id.in_(managed_group_ids), Group.is_active==True).order_by(Group.level.asc(), Group.create_time.asc()).all()

    # 权限变量
    return render_template('dashboard.html', orders=orders, salesmen=salesmen,
                           page_title='订单管理',
                           can_see_draft=not is_shipper,
                           can_filter_salesman=not is_salesman,
                           can_export=is_admin or is_shipper,
                           can_create_order=is_salesman,
                           can_ship=is_admin or is_shipper,
                           can_edit_order=is_salesman or is_admin,
                           can_edit_order_detail=is_admin,
                           can_reissue_gift=is_admin or current_user.has_role('admin') or current_user.has_role('salesman'),
                           can_approve_delete=is_admin,
                           auto_refresh=is_salesman,
                           unread_count=get_unread_count(current_user.id),
                           categories=get_active_categories(),
                           filter_groups=filter_groups if is_admin else [],
                           month_filter=month_filter,
                           total_paid=total_paid,
                           total_collect=total_collect,
                           signed_amount=signed_amount,
                           total_performance=total_performance)


@bp.route('/order/create', methods=['GET'])
@role_required('salesman')
def create_order_page():
    return render_template('create_order.html',
                           unread_count=get_unread_count(current_user.id),
                           categories=get_active_categories(),
                           gifts=get_active_gifts())


@bp.route('/order/create', methods=['POST'])
@role_required('salesman')
def create_order():
    group_name = request.form.get('group_name')
    customer_name = request.form.get('customer_name')
    paid_amount = request.form.get('paid_amount')
    pay_date = request.form.get('pay_date')
    collect_amount = request.form.get('collect_amount')
    product_info = request.form.get('product_info')
    category = request.form.get('category')
    phone = request.form.get('phone')
    address = request.form.get('address')
    remark = request.form.get('remark', '')
    action = request.form.get('action')
    # 赠品字段
    has_gift = request.form.get('has_gift') == 'on'
    gift_list = request.form.getlist('gift_info') if has_gift else []
    gift_info = '、'.join([g.strip() for g in gift_list if g.strip()])

    if not all([group_name, product_info, category, phone, address]):
        flash('请填写所有必填字段！', 'danger')
        return redirect(url_for('orders.create_order_page'))

    paid = paid_amount.strip() if paid_amount else None
    pay_d = datetime.strptime(pay_date, '%Y-%m-%d').date() if pay_date else None
    collect = float(collect_amount) if collect_amount else 0

    order = Order(
        group_name=group_name,
        salesman_id=current_user.id,
        product_info=product_info,
        category=category,
        phone=phone,
        address=address,
        remark=remark,
        customer_name=customer_name,
        paid_amount=paid,
        pay_date=pay_d,
        collect_amount=collect,
        has_gift=has_gift,
        gift_info=gift_info,
        group_id=current_user.group_id  # 自动带入当前用户的组别
    )

    if action == 'submit':
        order.status = 'submitted'
        shipper_ids = [s.id for s in User.query.filter(User.roles.like('%shipper%'), User.is_active==True).all()]
        customer_info = f"{customer_name or '未知'}-{phone}" if customer_name else phone
        notify_users(shipper_ids,
                     f'新的待发货订单：{group_name}，客户：{customer_info}，业务员：{current_user.name}，请及时处理！',
                     order_id=order.id)
        flash('订单已提交，已通知发货员！', 'success')
    else:
        order.status = 'draft'
        flash('草稿已保存！', 'success')

    db.session.add(order)
    db.session.commit()
    return redirect(url_for('orders.dashboard'))


@bp.route('/order/edit/<int:order_id>', methods=['GET', 'POST'])
@role_required('salesman')
def edit_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.salesman_id != current_user.id or order.status != 'draft':
        flash('您只能编辑自己的草稿订单！', 'danger')
        return redirect(url_for('orders.dashboard'))

    if request.method == 'POST':
        group_name = request.form.get('group_name')
        customer_name = request.form.get('customer_name')
        paid_amount = request.form.get('paid_amount')
        pay_date = request.form.get('pay_date')
        collect_amount = request.form.get('collect_amount')
        product_info = request.form.get('product_info')
        category = request.form.get('category')
        phone = request.form.get('phone')
        address = request.form.get('address')
        remark = request.form.get('remark', '')
        action = request.form.get('action')
        has_gift = request.form.get('has_gift') == 'on'
        gift_list = request.form.getlist('gift_info') if has_gift else []
        gift_info = '、'.join([g.strip() for g in gift_list if g.strip()])

        if not all([group_name, product_info, category, phone, address]):
            flash('请填写所有必填字段！', 'danger')
            return redirect(url_for('orders.edit_order', order_id=order_id))

        order.group_name = group_name
        order.customer_name = customer_name
        order.paid_amount = paid_amount.strip() if paid_amount else None
        order.pay_date = datetime.strptime(pay_date, '%Y-%m-%d').date() if pay_date else None
        order.collect_amount = float(collect_amount) if collect_amount else 0
        order.product_info = product_info
        order.category = category
        order.phone = phone
        order.address = address
        order.remark = remark
        order.has_gift = has_gift
        order.gift_info = gift_info

        if action == 'submit':
            order.status = 'submitted'
            shipper_ids = [s.id for s in User.query.filter(User.roles.like('%shipper%'), User.is_active==True).all()]
            customer_info = f"{customer_name or '未知'}-{phone}" if customer_name else phone
            notify_users(shipper_ids,
                         f'新的待发货订单：{group_name}，客户：{customer_info}，业务员：{current_user.name}，请及时处理！',
                         order_id=order.id)
            flash('订单已提交，已通知发货员！', 'success')
        else:
            order.status = 'draft'
            flash('草稿已保存！', 'success')
        db.session.commit()
        return redirect(url_for('orders.dashboard'))

    return render_template('edit_order.html',
                           order=order,
                           unread_count=get_unread_count(current_user.id),
                           categories=get_active_categories(),
                           gifts=get_active_gifts())


@bp.route('/api/order/<int:order_id>')
@login_required
def api_order_detail(order_id):
    """获取订单详情API"""
    order = Order.query.get_or_404(order_id)

    # 权限检查：admin账号可看所有，其他管理员按组别，业务员看自己
    if current_user.username == 'admin':
        pass  # admin账号可看所有
    elif current_user.has_role('admin') and current_user.group_id:
        # 其他管理员：按组别过滤
        managed_group_ids = current_user.get_managed_group_ids()
        if order.group_id not in managed_group_ids:
            return jsonify({'error': '无权查看此订单'}), 403
    elif order.salesman_id != current_user.id:
        return jsonify({'error': '无权查看此订单'}), 403

    is_main_product = False
    if order.category:
        cat = Category.query.filter_by(name=order.category, is_active=True).first()
        if cat:
            is_main_product = cat.is_main_product
    
    return jsonify({
        'id': order.id,
        'group_name': order.group_name,
        'salesman_name': order.salesman.name if order.salesman else '',
        'salesman_id': order.salesman_id,
        'customer_name': order.customer_name or '',
        'phone': order.phone,
        'address': order.address,
        'product_info': order.product_info,
        'category': order.category,
        'paid_amount': order.paid_amount or '',
        'collect_amount': order.collect_amount or 0,
        'has_gift': order.has_gift,
        'gift_info': order.gift_info or '',
        'remark': order.remark or '',
        'status': order.status,
        'tracking_number': order.tracking_number or '',
        'express_type': order.express_type or '',
        'logistics_status': order.logistics_status or '',
        'create_time': order.create_time.strftime('%Y-%m-%d %H:%M:%S') if order.create_time else '',
        'update_time': order.update_time.strftime('%Y-%m-%d %H:%M:%S') if order.update_time else '',
        'is_main_product': is_main_product
    })


@bp.route('/api/categories')
@login_required
def api_categories():
    """获取所有非主品产品类别（用于补发赠品）"""
    categories = Category.query.filter_by(is_active=True, is_main_product=False).order_by(Category.sort_order.asc(), Category.id.asc()).all()
    return jsonify([{'id': c.id, 'name': c.name, 'example': c.example or ''} for c in categories])

@bp.route('/api/category/<int:category_id>/gifts')
@login_required
def api_category_gifts(category_id):
    """获取类别对应的赠品列表"""
    gifts = get_active_gifts(category_id)
    return jsonify([{'id': g.id, 'name': g.name} for g in gifts])


@bp.route('/api/order/<int:order_id>/reissue-gift', methods=['POST'])
@login_required
def api_order_reissue_gift(order_id):
    """补发赠品：创建一条新的草稿订单"""
    original_order = Order.query.get_or_404(order_id)
    
    data = request.get_json() or {}
    category_id = data.get('category_id')
    
    if not category_id:
        return jsonify({'error': '请选择产品类别'}), 400
    
    category = Category.query.get(category_id)
    if not category:
        return jsonify({'error': '产品类别不存在'}), 400
    
    product_info = category.example or '补发赠品'
    
    new_order = Order(
        group_name=original_order.group_name,
        salesman_id=original_order.salesman_id,
        product_info=product_info,
        category=category.name,
        paid_amount='0',
        collect_amount='0',
        phone=original_order.phone,
        address=original_order.address,
        customer_name=original_order.customer_name,
        remark=f'补发赠品，源订单ID: {original_order.id}',
        status='draft',
        group_id=original_order.group_id
    )
    
    db.session.add(new_order)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'order_id': new_order.id
    })


@bp.route('/api/order/<int:order_id>/logistics')
@login_required
def api_order_logistics(order_id):
    """获取订单物流路由详情（带缓存）"""
    order = Order.query.get_or_404(order_id)

    # 权限检查
    if current_user.username == 'admin':
        pass
    elif current_user.has_role('admin') and current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        if order.group_id not in managed_group_ids:
            return jsonify({'error': '无权查看'}), 403
    elif order.salesman_id != current_user.id:
        return jsonify({'error': '无权查看'}), 403

    # 非顺丰或未发货，返回空
    if order.express_type != '顺丰' or order.status != 'shipped' or not order.tracking_number:
        return jsonify({'routes': [], 'tracking_number': order.tracking_number or '', 'express_type': order.express_type or ''})

    # 使用缓存获取物流信息
    from services import get_logistics_with_cache
    result = get_logistics_with_cache(order, force_refresh=False)

    return jsonify({
        'routes': result['routes'],
        'tracking_number': order.tracking_number,
        'express_type': order.express_type,
        'logistics_status': order.logistics_status or '',
        'from_cache': result['from_cache']
    })


@bp.route('/api/order/<int:order_id>/logistics/refresh', methods=['POST'])
@login_required
def api_order_logistics_refresh(order_id):
    """手动刷新订单物流信息"""
    order = Order.query.get_or_404(order_id)

    # 权限检查
    if current_user.username == 'admin':
        pass
    elif current_user.has_role('admin') and current_user.group_id:
        managed_group_ids = current_user.get_managed_group_ids()
        if order.group_id not in managed_group_ids:
            return jsonify({'error': '无权操作'}), 403
    elif order.salesman_id != current_user.id:
        return jsonify({'error': '无权操作'}), 403

    # 非顺丰或未发货
    if order.express_type != '顺丰' or order.status != 'shipped' or not order.tracking_number:
        return jsonify({'error': '非顺丰订单或未发货'}), 400

    # 强制刷新物流信息
    from services import get_logistics_with_cache
    result = get_logistics_with_cache(order, force_refresh=True)

    return jsonify({
        'success': True,
        'routes': result['routes'],
        'tracking_number': order.tracking_number,
        'express_type': order.express_type,
        'logistics_status': order.logistics_status or '',
        'from_cache': False
    })


@bp.route('/api/order/<int:order_id>/edit', methods=['POST'])
@role_required('admin')
def api_order_edit(order_id):
    """管理员编辑订单API"""
    order = Order.query.get_or_404(order_id)

    # 保存旧值用于比较
    old_values = {
        'customer_name': order.customer_name,
        'phone': order.phone,
        'address': order.address,
        'product_info': order.product_info,
        'paid_amount': order.paid_amount,
        'collect_amount': order.collect_amount,
        'remark': order.remark,
        'tracking_number': order.tracking_number,
        'express_type': order.express_type
    }

    # 获取新值
    new_customer_name = request.form.get('customer_name', '').strip()
    new_phone = request.form.get('phone', '').strip()
    new_address = request.form.get('address', '').strip()
    new_product_info = request.form.get('product_info', '').strip()
    new_paid_amount = request.form.get('paid_amount', '').strip()
    new_collect_amount = request.form.get('collect_amount', '').strip()
    new_remark = request.form.get('remark', '').strip()
    new_tracking_number = request.form.get('tracking_number', '').strip()
    new_express_type = request.form.get('express_type', '').strip()

    # 更新字段
    order.customer_name = new_customer_name
    order.phone = new_phone
    order.address = new_address
    order.product_info = new_product_info
    order.paid_amount = new_paid_amount if new_paid_amount else None
    order.collect_amount = float(new_collect_amount) if new_collect_amount else 0
    order.remark = new_remark
    order.tracking_number = new_tracking_number if new_tracking_number else None
    order.express_type = new_express_type if new_express_type else None
    from models import _now_bj
    order.update_time = _now_bj()

    db.session.commit()

    # 生成修改通知
    changes = []
    field_labels = {
        'customer_name': '客户姓名',
        'phone': '电话',
        'address': '地址',
        'product_info': '产品信息',
        'paid_amount': '已付定金',
        'collect_amount': '代收金额',
        'remark': '备注',
        'tracking_number': '快递单号',
        'express_type': '快递类型'
    }

    for field, label in field_labels.items():
        old_val = old_values[field] or ''
        new_val = locals().get(f'new_{field}') or ''
        if str(old_val) != str(new_val):
            changes.append(f'{label}：{old_val} → {new_val}')

    # 通知业务员
    if changes:
        change_text = '；'.join(changes)
        notify_users([order.salesman_id],
                    f'管理员 {current_user.name} 修改了您的订单（ID:{order.id}）：{change_text}',
                    order_id=order.id)

    return jsonify({
        'success': True,
        'message': '订单已更新' + ('，已通知业务员' if changes else ''),
        'changes': changes
    })


@bp.route('/order/delete/<int:order_id>', methods=['POST'])
@role_required('salesman')
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.salesman_id != current_user.id:
        flash('您只能删除自己的订单！', 'danger')
        return redirect(url_for('orders.dashboard'))

    if order.status == 'draft':
        db.session.delete(order)
        db.session.commit()
        flash('草稿已删除！', 'success')
        return redirect(url_for('orders.dashboard'))

    if order.delete_requested:
        flash('已经提交过删除申请了，请等待管理员审批！', 'warning')
        return redirect(url_for('orders.dashboard'))

    # 已付金额和代收金额都为0时，直接删除不需要审批
    import re
    paid = 0
    if order.paid_amount:
        num_match = re.match(r'^(\d+(?:\.\d+)?)', str(order.paid_amount))
        if num_match:
            paid = float(num_match.group(1))
    collect = float(order.collect_amount or 0)
    if paid == 0 and collect == 0:
        db.session.delete(order)
        db.session.commit()
        flash('订单已删除！（金额为0，无需审批）', 'success')
        return redirect(url_for('orders.dashboard'))

    from models import _now_bj
    order.delete_requested = True
    order.delete_request_time = _now_bj()
    db.session.commit()
    admin_ids = [a.id for a in User.query.filter(User.roles.like('%admin%')).all()]
    customer_info = f"{order.customer_name or '未知'}-{order.phone}" if order.customer_name else order.phone
    notify_users(admin_ids,
                 f'业务员 {current_user.name} 提交了删除订单 {order.group_name}（客户：{customer_info}）的申请，请处理！',
                 order_id=order.id)
    flash('删除申请已提交，等待管理员审批！', 'success')
    return redirect(url_for('orders.dashboard'))
