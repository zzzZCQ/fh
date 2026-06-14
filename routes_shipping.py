# -*- coding: utf-8 -*-
"""发货操作路由"""
import time
from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import db, User, Order, Category
from helpers import role_required, notify_users
from services import update_single_order_logistics, get_sf_routes_batch, _update_order_status_from_routes, save_logistics_cache

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
    # 检查点击频率限制（1小时 = 3600秒），超级管理员不受限制
    user_id = current_user.id
    now = time.time()
    
    # 超级管理员（用户名=admin）不受时间限制
    if current_user.username != 'admin':
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
    
    # 先回滚之前可能失败的事务，避免挂起
    try:
        db.session.rollback()
    except:
        pass
    
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

    # 获取 per_page 参数，与 dashboard 保持一致
    per_page = request.form.get('per_page', 20, type=int)
    if per_page not in [20, 50, 100, 500]:
        per_page = 20

    # 先完全按照 dashboard 的查询逻辑获取用户看到的当前页的所有订单（包括排序）
    from sqlalchemy import case
    from models import Category
    
    # 排序逻辑与dashboard保持一致
    page_orders = query.outerjoin(Category, Category.name == Order.category).order_by(
        case(
            # 0: 待发货 主品（无论物流状态如何）
            ((Order.status == 'submitted') & (Category.is_main_product == True), 0),
            # 1: 待发货 非主品 + 未导出（无论物流状态如何）
            ((Order.status == 'submitted') & ((Category.is_main_product == False) | (Category.is_main_product == None)) & (Order.export_marked == False), 1),
            # 2: 派送中
            (Order.logistics_status == '派送中', 2),
            # 3: 待派送
            (Order.logistics_status == '待派送', 3),
            # 4: 已揽收/已揽件/待取件（非待发货状态）
            ((Order.logistics_status == '已揽收') & (Order.status != 'submitted'), 4),
            ((Order.logistics_status == '已揽件') & (Order.status != 'submitted'), 4),
            ((Order.logistics_status == '待取件') & (Order.status != 'submitted'), 4),
            # 5: 运送中
            (Order.logistics_status == '运送中', 5),
            # 6: 已发货（非待发货状态）
            ((Order.logistics_status == '已发货') & (Order.status != 'submitted'), 6),
            # 7: 待发货 非主品 + 已导出（无论物流状态如何）
            ((Order.status == 'submitted') & ((Category.is_main_product == False) | (Category.is_main_product == None)) & (Order.export_marked == True), 7),
            # 8: 已签收 主品
            ((Order.logistics_status == '已签收') & (Category.is_main_product == True), 8),
            # 9: 已签收 非主品
            ((Order.logistics_status == '已签收') & ((Category.is_main_product == False) | (Category.is_main_product == None)), 9),
            # 10: 退回已签收
            (Order.logistics_status == '退回已签收', 10),
            # 11: 其他
            else_=11
        ),
        # 创建时间降序
        Order.create_time.desc()
    ).paginate(page=page, per_page=per_page, error_out=False).items
    
    print("====================================================")
    print(f"[update_logistics] 当前页共有 {len(page_orders)} 个订单")
    
    # 再在当前页的订单中筛选出需要更新物流的订单（非主品跳过）
    orders_to_update = []
    for order in page_orders:
        # 检查是否是主品，非主品不调用API更新
        category = Category.query.filter_by(name=order.category).first()
        is_main_product = category.is_main_product if category else False
        
        print(f"[update_logistics] 订单ID={order.id}: status={order.status}, express={order.express_type}, tracking={order.tracking_number}, log_status={order.logistics_status}, is_main={is_main_product}")
        
        if (is_main_product and  # 只更新主品的物流
            order.express_type == '顺丰' and 
            order.status == 'shipped' and 
            order.logistics_status not in ['已签收', '退回已签收', '拒签']):
            orders_to_update.append(order)
    
    print(f"[update_logistics] 其中有 {len(orders_to_update)} 个订单需要更新")

    updated_count = 0

    # 分批处理，每批最多10条
    BATCH_SIZE = 10
    for batch_start in range(0, len(orders_to_update), BATCH_SIZE):
        batch_orders = orders_to_update[batch_start:batch_start + BATCH_SIZE]

        # 收集本批次的单号和手机号后4位
        tracking_numbers = []
        phone_last4_list = []
        for order in batch_orders:
            phone_last4 = order.phone[-4:] if order.phone and len(order.phone) >= 4 else ''
            tracking_numbers.append(order.tracking_number)
            phone_last4_list.append(phone_last4)

        print(f"[update_logistics] 批量查询第 {batch_start//BATCH_SIZE + 1} 批: {len(batch_orders)} 个订单")

        # 一次性查询本批次的所有路由
        routes_dict = get_sf_routes_batch(tracking_numbers, phone_last4_list)
        print(f"[update_logistics] 本批次routes_dict内容: {routes_dict.keys()}")
        for tn, r in routes_dict.items():
            print(f"[update_logistics] 单号{tn}有{len(r)}条路由")

        # 逐个更新订单状态
        for order in batch_orders:
            routes = routes_dict.get(order.tracking_number, [])
            print(f"[update_logistics] 更新订单 {order.id}: tracking={order.tracking_number}, routes数量={len(routes)}")
            # 使用路由更新订单状态（内部不再调用API，直接用已查询的routes）
            result = _update_order_status_from_routes(order, routes)
            if result:
                updated_count += 1
            
            # 保存缓存
            final_statuses = ['已签收', '退回已签收']
            is_final = order.logistics_status in final_statuses
            print(f"[update_logistics] 保存缓存: 单号={order.tracking_number}, is_final={is_final}, routes数量={len(routes)}")
            save_logistics_cache(order.tracking_number, routes, is_final, order.sign_time if is_final else None)

    flash(f'物流信息已更新！共更新了 {updated_count} 条。', 'success')
    
    # 构建重定向参数
    redirect_args = {
        'page': request.form.get('page', 1),
        'per_page': per_page,
        'customer_keyword': request.form.get('customer_keyword', ''),
        'tracking_keyword': request.form.get('tracking_keyword', ''),
        'category': request.form.get('category', ''),
        'salesman_id': request.form.get('salesman_id', ''),
        'month': request.form.get('month', ''),
        'group_id': request.form.get('group_id', '')
    }
    
    # 处理多选的 status
    status_list = request.form.getlist('status')
    if status_list:
        redirect_args['status'] = status_list
    
    return redirect(url_for('orders.dashboard', **redirect_args))


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
    # 先删除关联的提醒记录
    from models import OrderReminder
    OrderReminder.query.filter_by(order_id=order.id).delete()
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
