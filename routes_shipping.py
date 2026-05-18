# -*- coding: utf-8 -*-
"""发货操作路由"""
import time
from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import db, User, Order, Category
from helpers import role_required, notify_users
from services import update_single_order_logistics

bp = Blueprint('shipping', __name__)

# 更新物流按钮点击时间缓存 {user_id: last_click_timestamp}
_update_logistics_click_cache = {}


# ============ 发货操作路由 ============
@bp.route('/order/ship/<int:order_id>', methods=['POST'])
@role_required('shipper', 'admin')
def ship_order(order_id):
    order = Order.query.get_or_404(order_id)
    tracking_number = request.form.get('tracking_number')
    express_type = request.form.get('express_type')
    if not tracking_number or not express_type:
        flash('请填写快递单号和选择快递类型！', 'danger')
        return redirect(url_for('orders.dashboard'))

    order.status = 'shipped'
    order.tracking_number = tracking_number
    order.express_type = express_type

    # 判断是否为主品，非主品发货即签收
    category = Category.query.filter_by(name=order.category).first()
    if category and not category.is_main_product:
        # 非主品：发货即签收
        order.logistics_status = '已签收'
    elif express_type == '顺丰':
        # 主品且顺丰：标记为已发货
        order.logistics_status = '已发货'

    customer_info = f"{order.customer_name or '未知'}-{order.phone}" if order.customer_name else order.phone
    notify_users([order.salesman_id],
                 f'您的订单 {order.group_name}（客户：{customer_info}）已发货，{express_type}：{tracking_number}，请注意查收！',
                 order_id=order.id)
    flash('订单已处理，已通知业务员！', 'success')
    return redirect(url_for('orders.dashboard'))


@bp.route('/update_logistics', methods=['POST'])
@login_required
def update_logistics():
    # 检查点击频率限制（1小时 = 3600秒）
    user_id = current_user.id
    now = time.time()
    last_click = _update_logistics_click_cache.get(user_id, 0)
    
    if now - last_click < 3600:  # 1小时内已点击过
        remaining_seconds = int(3600 - (now - last_click))
        remaining_minutes = remaining_seconds // 60
        flash(f'更新物流按钮每小时只能点击一次，请 {remaining_minutes} 分钟后再试！', 'warning')
        return redirect(url_for('orders.dashboard',
            page=request.form.get('page', 1),
            customer_keyword=request.form.get('customer_keyword', ''),
            tracking_keyword=request.form.get('tracking_keyword', ''),
            status=request.form.get('status', ''),
            category=request.form.get('category', ''),
            salesman_id=request.form.get('salesman_id', '')))
    
    # 记录本次点击时间
    _update_logistics_click_cache[user_id] = now
    
    print(f"[update_logistics] 收到请求, page={request.form.get('page')}")
    page = request.form.get('page', 1, type=int)
    customer_keyword = request.form.get('customer_keyword', '').strip()
    tracking_keyword = request.form.get('tracking_keyword', '').strip()
    category_filter = request.form.get('category', '').strip()
    salesman_filter = request.form.get('salesman_id', '').strip()

    if current_user.has_role('admin'):
        query = Order.query
    elif current_user.has_role('salesman') and not current_user.has_role('admin'):
        query = Order.query.filter_by(salesman_id=current_user.id)
    elif current_user.has_role('shipper') and not current_user.has_role('admin'):
        query = Order.query.filter(Order.status != 'draft')
    else:
        query = Order.query

    if customer_keyword:
        query = query.filter(Order.customer_name.contains(customer_keyword))
    if tracking_keyword:
        query = query.filter(Order.tracking_number.contains(tracking_keyword))
    if category_filter:
        query = query.filter(Order.category == category_filter)
    if salesman_filter:
        query = query.filter(Order.salesman_id == salesman_filter)

    # 分页查询，只更新当前页
    orders = query.filter(
        Order.express_type == '顺丰',
        Order.status == 'shipped',
        Order.logistics_status.notin_(['已签收', '拒签'])
    ).order_by(Order.create_time.desc()).paginate(page=page, per_page=10, error_out=False).items
    print("====================================================")
    print(f"[update_logistics] 当前页有 {len(orders)} 个订单需要更新")
    for i, order in enumerate(orders):
        print(f"[update_logistics] 正在更新第 {i+1}/{len(orders)} 个订单: id={order.id}, customer={order.customer_name}, tracking={order.tracking_number}, status={order.logistics_status}")
        update_single_order_logistics(order)
    flash('当前页的物流信息已更新！', 'success')
    return redirect(url_for('orders.dashboard',
        page=request.form.get('page', 1),
        customer_keyword=request.form.get('customer_keyword', ''),
        tracking_keyword=request.form.get('tracking_keyword', ''),
        status=request.form.get('status', ''),
        category=request.form.get('category', ''),
        salesman_id=request.form.get('salesman_id', '')))


# ============ 删除审批路由 ============
@bp.route('/admin/delete/approve/<int:order_id>', methods=['POST'])
@role_required('admin')
def approve_delete(order_id):
    order = Order.query.get_or_404(order_id)
    if not order.delete_requested:
        flash('没有找到删除申请！', 'danger')
        return redirect(url_for('orders.dashboard'))
    customer_info = f"{order.customer_name or '未知'}-{order.phone}" if order.customer_name else order.phone
    group_name = order.group_name
    salesman_id = order.salesman_id
    db.session.delete(order)
    db.session.commit()
    notify_users([salesman_id], f'您的删除订单 {group_name}（客户：{customer_info}）的申请，管理员已通过！')
    flash('删除申请已通过，订单已删除！', 'success')
    return redirect(url_for('orders.dashboard'))


@bp.route('/admin/delete/reject/<int:order_id>', methods=['POST'])
@role_required('admin')
def reject_delete(order_id):
    order = Order.query.get_or_404(order_id)
    if not order.delete_requested:
        flash('没有找到删除申请！', 'danger')
        return redirect(url_for('orders.dashboard'))
    order.delete_requested = False
    db.session.commit()
    customer_info = f"{order.customer_name or '未知'}-{order.phone}" if order.customer_name else order.phone
    notify_users([order.salesman_id], f'您的删除订单 {order.group_name}（客户：{customer_info}）的申请，管理员已拒绝！')
    flash('删除申请已拒绝！', 'success')
    return redirect(url_for('orders.dashboard'))
