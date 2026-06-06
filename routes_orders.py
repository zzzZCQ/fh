# -*- coding: utf-8 -*-
"""订单管理路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
import re

from models import db, User, Order, Group, Category, OrderReminder
from helpers import role_required, get_unread_count, get_active_categories, get_all_categories, get_active_gifts, notify_users, notify_user_upward_admin

bp = Blueprint('orders', __name__)


def extract_quantity_from_product_info(product_info):
    """从产品信息中提取数量"""
    if not product_info:
        return 1
    # 尝试匹配常见的数量格式：数量:x、数量：x、x件、x个、产品*3等
    patterns = [
        r'\*(\d+)',  # *3 格式（产品*3）
        r'数量[：:]\s*(\d+)',  # 数量:1 或 数量：1
        r'(\d+)\s*[件个台盒]',  # 1件、2个等
        r'数量\s*[=＝]\s*(\d+)',  # 数量=1
        r'共\s*(\d+)\s*[份盒]',  # 共3份、共3盒
        r'×(\d+)',  # ×3 格式
    ]
    for pattern in patterns:
        match = re.search(pattern, product_info)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                continue
    # 如果没找到，默认返回1
    return 1


def validate_order_amount(category_name, product_info, paid_amount_str, collect_amount_str):
    """验证订单金额是否与单价×数量匹配"""
    # 获取类别信息
    category = Category.query.filter_by(name=category_name, is_active=True).first()
    if not category or not category.unit_price or category.unit_price <= 0:
        # 如果没有设置单价，不验证
        return True, None
    
    # 提取数量
    quantity = extract_quantity_from_product_info(product_info)
    
    # 计算总金额
    expected_total = category.unit_price * quantity
    
    # 解析已付金额（只取数字部分）
    paid = 0
    if paid_amount_str:
        num_match = re.match(r'^(\d+(?:\.\d+)?)', str(paid_amount_str))
        if num_match:
            paid = float(num_match.group(1))
    
    # 解析代收金额
    collect = 0
    if collect_amount_str:
        try:
            collect = float(collect_amount_str)
        except (ValueError, TypeError):
            collect = 0
    
    actual_total = paid + collect
    
    # 允许一定的误差（±1元）
    if abs(actual_total - expected_total) > 1:
        return False, (f'金额不匹配！{category_name}单价为{category.unit_price}元，数量为{quantity}，'
                      f'预期总金额为{expected_total}元，实际填写为{actual_total}元（已付{paid}元+代收{collect}元）')
    
    return True, None


# ============ 统一订单管理路由 ============
@bp.route('/')
@bp.route('/dashboard')
@login_required
def dashboard():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if per_page not in [20, 50, 100, 500]:
        per_page = 20
    customer_keyword = request.args.get('customer_keyword', '').strip()
    tracking_keyword = request.args.get('tracking_keyword', '').strip()
    category_filter = request.args.get('category', '').strip()
    salesman_filter = request.args.get('salesman_id', '').strip()
    status_filters = request.args.getlist('status')
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
    if status_filters:
        # 支持多个状态筛选
        from sqlalchemy import or_
        status_conditions = []
        logistics_status_conditions = []
        
        for s in status_filters:
            if s:
                if s in ['draft', 'submitted', 'shipped']:
                    status_conditions.append(Order.status == s)
                else:
                    logistics_status_conditions.append(Order.logistics_status == s)
        
        if status_conditions or logistics_status_conditions:
            conditions = []
            if status_conditions:
                conditions.append(or_(*status_conditions))
            if logistics_status_conditions:
                conditions.append(or_(*logistics_status_conditions))
            if conditions:
                query = query.filter(or_(*conditions))
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
    from sqlalchemy import case
    from models import Category
    
    # 使用简单直接的SQL CASE排序（SQLAlchemy 2.0正确语法）
    # 统一优先级规则：
    # 0: 待发货 主品（无论物流状态如何）
    # 1: 待发货 非主品 + 未导出（无论物流状态如何）
    # 2: 派送中
    # 3: 待派送
    # 4: 已揽收/已揽件（非待发货状态）
    # 5: 运送中
    # 6: 已发货（非待发货状态）
    # 7: 待发货 非主品 + 已导出（无论物流状态如何）
    # 8: 已签收 主品
    # 9: 已签收 非主品
    # 10: 退回已签收
    # 11: 其他
    orders = query.outerjoin(Category, Category.name == Order.category).order_by(
        case(
            # 0: 待发货 主品（无论物流状态如何）
            ((Order.status == 'submitted') & (Category.is_main_product == True), 0),
            # 1: 待发货 非主品 + 未导出（无论物流状态如何）
            ((Order.status == 'submitted') & ((Category.is_main_product == False) | (Category.is_main_product == None)) & (Order.export_marked == False), 1),
            # 2: 派送中
            (Order.logistics_status == '派送中', 2),
            # 3: 待派送
            (Order.logistics_status == '待派送', 3),
            # 4: 已揽收/已揽件（非待发货状态）
            ((Order.logistics_status == '已揽收') & (Order.status != 'submitted'), 4),
            ((Order.logistics_status == '已揽件') & (Order.status != 'submitted'), 4),
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
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    # 业务员筛选：可见范围是本级及下级
    salesman_query = User.query.filter(User.roles.like('%salesman%'))
    if is_admin and current_user.username == 'admin':
        pass
    elif current_user.group_id:
        visible_group_ids = current_user.get_managed_group_ids()
        salesman_query = salesman_query.filter(User.group_id.in_(visible_group_ids))
    salesmen = salesman_query.all()
    
    # 简化汇总统计：只统计当前页，避免大数据量时的性能问题
    page_count = orders.total
    import re
    page_paid = 0
    page_collect = 0
    signed_amount = 0
    
    # 获取所有活跃的主品类别
    main_product_categories = set(c.name for c in Category.query.filter_by(is_main_product=True, is_active=True).all())
    
    for o in orders.items:
        # 只统计主品的金额（包含退回已签收）
        if o.category not in main_product_categories:
            continue
        
        # 判断订单归属月份：以签收时间为主，没有签收时间时用创建时间（与团队业绩一致）
        order_month = None
        order_year = None
        if o.sign_time:
            order_month = o.sign_time.month
            order_year = o.sign_time.year
        elif o.create_time:
            order_month = o.create_time.month
            order_year = o.create_time.year
        
        # 如果有月份筛选，只统计归属月份在筛选范围内的订单
        should_count = True
        if month_filter and order_month and order_year:
            try:
                filter_year, filter_month = month_filter.split('-')
                if order_year != int(filter_year) or order_month != int(filter_month):
                    should_count = False
            except:
                pass
        
        if should_count:
            # 计算订单总金额（与团队业绩一致，只统计金额>0的订单）
            order_total = 0
            if o.paid_amount:
                num_match = re.match(r'^(\d+(?:\.\d+)?)', str(o.paid_amount))
                if num_match:
                    order_total += float(num_match.group(1))
            if o.collect_amount:
                order_total += float(o.collect_amount)
            
            # 只统计金额>0的订单（与团队业绩一致）
            if order_total > 0:
                # 已付定金
                if o.paid_amount:
                    num_match = re.match(r'^(\d+(?:\.\d+)?)', str(o.paid_amount))
                    if num_match:
                        page_paid += float(num_match.group(1))
                # 代收金额
                if o.collect_amount:
                    page_collect += float(o.collect_amount)
        # 已签收金额：只统计签收时间在筛选月份内且金额>0的订单（与团队业绩一致）
        if o.logistics_status == '已签收':
            # 判断订单归属月份：以签收时间为准
            if o.sign_time:
                order_month = o.sign_time.month
                order_year = o.sign_time.year
                
                # 判断是否在筛选月份内
                in_month = False
                if month_filter:
                    try:
                        filter_year, filter_month = month_filter.split('-')
                        if order_year == int(filter_year) and order_month == int(filter_month):
                            in_month = True
                    except:
                        in_month = True  # 解析失败时统计所有
                else:
                    in_month = True  # 没有筛选时统计所有
                
                # 只统计金额>0的订单
                if in_month:
                    order_total = 0
                    paid_val = 0
                    if o.paid_amount:
                        num_match = re.match(r'^(\d+(?:\.\d+)?)', str(o.paid_amount))
                        if num_match:
                            paid_val = float(num_match.group(1))
                            order_total += paid_val
                    if o.collect_amount:
                        order_total += float(o.collect_amount)
                    
                    if order_total > 0:
                        signed_amount += order_total
    
    # 总览统计：使用当前页的汇总数据
    total_paid = page_paid
    total_collect = page_collect
    total_performance = page_paid + page_collect
    
    # 组别筛选列表：管理员本级及以下
    filter_groups = []
    if is_admin:
        if current_user.username == 'admin':
            filter_groups = Group.query.filter_by(is_active=True).order_by(Group.level.asc(), Group.create_time.asc()).all()
        elif current_user.group_id:
            managed_group_ids = current_user.get_managed_group_ids()
            filter_groups = Group.query.filter(Group.id.in_(managed_group_ids), Group.is_active==True).order_by(Group.level.asc(), Group.create_time.asc()).all()
    
    # 权限变量
    # 获取主产品类别列表
    main_product_categories = set(c.name for c in Category.query.filter_by(is_main_product=True, is_active=True).all())
    
    return render_template('dashboard.html', orders=orders, salesmen=salesmen,
                           page_title='订单管理',
                           can_see_draft=not is_shipper,
                           can_filter_salesman=not is_salesman,
                           can_export=is_admin or is_shipper,
                           can_see_export_mark=True,  # 所有人都能看到导出标记
                           can_create_order=is_salesman,
                           can_ship=is_admin or is_shipper,
                           can_edit_order=is_salesman or is_admin,
                           can_edit_order_detail=is_admin or is_salesman,
                           can_reissue_gift=is_admin or current_user.has_role('admin') or current_user.has_role('salesman'),
                           can_approve_delete=is_admin,
                           auto_refresh=is_salesman,
                           unread_count=get_unread_count(current_user.id),
                           categories=get_all_categories(),
                           filter_groups=filter_groups if is_admin else [],
                           month_filter=month_filter,
                           total_paid=total_paid,
                           total_collect=total_collect,
                           signed_amount=signed_amount,
                           total_performance=total_performance,
                           page_paid=page_paid,
                           page_collect=page_collect,
                           page_count=page_count,
                           main_product_categories=main_product_categories)


@bp.route('/order/create', methods=['GET'])
@role_required('salesman')
def create_order_page():
    return render_template('create_order.html',
                           unread_count=get_unread_count(current_user.id),
                           categories=get_active_categories(),
                           gifts=get_active_gifts())


@bp.route('/order/batch_create', methods=['GET'])
@role_required('salesman')
def batch_create_order_page():
    """批量创建订单页面 - 重定向到新建订单页面"""
    return redirect(url_for('orders.create_order_page'))


@bp.route('/order/batch_create', methods=['POST'])
@role_required('salesman')
def batch_create_order():
    """批量创建订单"""
    import json
    
    customers_json = request.form.get('customers_json')
    category = request.form.get('category')
    paid_amount = request.form.get('paid_amount')
    collect_amount = request.form.get('collect_amount')
    product_info = request.form.get('product_info')
    
    if not customers_json or not category or not product_info:
        return render_template('create_order.html',
                               unread_count=get_unread_count(current_user.id),
                               categories=get_active_categories(),
                               error='请填写所有必填字段！')
    
    try:
        customers = json.loads(customers_json)
    except json.JSONDecodeError:
        return render_template('create_order.html',
                               unread_count=get_unread_count(current_user.id),
                               categories=get_active_categories(),
                               error='客户数据格式错误！')
    
    success_count = 0
    failed_count = 0
    
    for customer in customers:
        phone = customer.get('phone', '').strip()
        address = customer.get('address', '').strip()
        
        if not phone or not address or len(address) < 10:
            failed_count += 1
            continue
        
        try:
            order = Order(
                group_name=current_user.group.name if current_user.group else '',
                salesman_id=current_user.id,
                product_info=product_info,
                category=category,
                phone=phone,
                address=address,
                remark='',
                customer_name=customer.get('name', '').strip(),
                customer_wechat='',
                paid_amount=paid_amount.strip() if paid_amount else None,
                pay_date=None,
                collect_amount=float(collect_amount) if collect_amount else 0,
                gender='',
                has_gift=False,
                gift_info='',
                group_id=current_user.group_id,
                status='submitted'
            )
            db.session.add(order)
            success_count += 1
        except Exception as e:
            print(f"创建订单失败: {e}")
            failed_count += 1
    
    if success_count > 0:
        db.session.commit()
        
        # 通知发货员
        shipper_ids = [s.id for s in User.query.filter(User.roles.like('%shipper%'), User.is_active==True).all()]
        if shipper_ids:
            notify_users(shipper_ids,
                         f'业务员 {current_user.name} 批量创建了 {success_count} 个订单，请及时处理！',
                         order_id=None)
    
    return render_template('create_order.html',
                           unread_count=get_unread_count(current_user.id),
                           categories=get_active_categories(),
                           success_count=success_count,
                           failed_count=failed_count)


@bp.route('/order/create', methods=['POST'])
@role_required('salesman')
def create_order():
    group_name = request.form.get('group_name')
    customer_name = request.form.get('customer_name')
    customer_wechat = request.form.get('customer_wechat')
    paid_amount = request.form.get('paid_amount')
    pay_date = request.form.get('pay_date')
    collect_amount = request.form.get('collect_amount')
    product_info = request.form.get('product_info')
    category = request.form.get('category')
    phone = request.form.get('phone')
    address = request.form.get('address')
    remark = request.form.get('remark', '')
    action = request.form.get('action')
    expected_shipping_time_str = request.form.get('expected_shipping_time')
    confirm_duplicate = request.form.get('confirm_duplicate', '')
    # 赠品字段
    has_gift = request.form.get('has_gift') == 'on'
    gift_list = request.form.getlist('gift_info') if has_gift else []
    gift_info = '、'.join([g.strip() for g in gift_list if g.strip()])
    
    # 性别字段
    gender = request.form.get('gender')

    # 判断是否是AJAX请求
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
              request.is_json or \
              request.form.get('_ajax') == '1'
    
    # 添加隐藏字段用于识别AJAX请求
    if request.form.get('_ajax') == '1':
        is_ajax = True
    
    if not all([group_name, product_info, category, phone, address]):
        error_msg = '请填写所有必填字段！'
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg})
        # 保留用户填写的数据并返回表单
        return render_template('create_order.html',
                             unread_count=get_unread_count(current_user.id),
                             categories=get_active_categories(),
                             gifts=get_active_gifts(),
                             form_data={
                                 'group_name': group_name,
                                 'customer_name': customer_name or '',
                                 'customer_wechat': customer_wechat or '',
                                 'paid_amount': paid_amount or '',
                                 'pay_date': pay_date or '',
                                 'collect_amount': collect_amount or '',
                                 'product_info': product_info,
                                 'category': category,
                                 'phone': phone,
                                 'address': address,
                                 'remark': remark or '',
                                 'has_gift': has_gift,
                                 'gift_info': gift_list,
                                 'gender': gender if 'gender' in locals() else ''
                             },
                             error=error_msg)
    
    # 验证金额（只在提交订单时验证，保存草稿不验证）
    if action == 'submit':
        is_valid, error_msg = validate_order_amount(category, product_info, paid_amount, collect_amount)
        if not is_valid:
            if is_ajax:
                return jsonify({'success': False, 'error': error_msg})
            # 保留用户填写的数据并返回表单
            return render_template('create_order.html',
                                 unread_count=get_unread_count(current_user.id),
                                 categories=get_active_categories(),
                                 gifts=get_active_gifts(),
                                 form_data={
                                     'group_name': group_name,
                                     'customer_name': customer_name or '',
                                     'customer_wechat': customer_wechat or '',
                                     'paid_amount': paid_amount or '',
                                     'pay_date': pay_date or '',
                                     'collect_amount': collect_amount or '',
                                     'product_info': product_info,
                                     'category': category,
                                     'phone': phone,
                                     'address': address,
                                     'remark': remark or '',
                                     'has_gift': has_gift,
                                     'gift_info': gift_list,
                                     'gender': gender if 'gender' in dir() else ''
                                 },
                                 error=error_msg)
    
    # 检查重复订单（只在提交订单时检查，保存草稿不检查）
    if action == 'submit' and confirm_duplicate != '1':
        existing_orders = Order.query.filter(
            Order.customer_name == customer_name,
            Order.phone == phone,
            Order.category == category
        ).order_by(Order.create_time.desc()).limit(5).all()
        
        if existing_orders:
            # 构建错误信息，显示现有订单
            error_msg = "发现以下相似订单：\n\n"
            for i, order in enumerate(existing_orders):
                status_text = {
                    'draft': '草稿',
                    'submitted': '待发货',
                    'shipped': order.logistics_status or '已发货'
                }.get(order.status, order.status)
                
                create_time = order.create_time.strftime('%Y-%m-%d %H:%M') if order.create_time else ''
                product_short = order.product_info[:50] + '...' if len(order.product_info) > 50 else order.product_info
                
                error_msg += f"{i+1}. [{status_text}] {create_time}\n   {product_short}\n\n"
            
            # 生成提示信息的HTML
            if is_ajax:
                return jsonify({
                    'success': False, 
                    'error': error_msg,
                    'has_duplicate': True
                })
            
            # 渲染页面，保留表单数据并显示重复订单警告
            return render_template('create_order.html',
                                 unread_count=get_unread_count(current_user.id),
                                 categories=get_active_categories(),
                                 gifts=get_active_gifts(),
                                 form_data={
                                     'group_name': group_name,
                                     'customer_name': customer_name or '',
                                     'customer_wechat': customer_wechat or '',
                                     'paid_amount': paid_amount or '',
                                     'pay_date': pay_date or '',
                                     'collect_amount': collect_amount or '',
                                     'product_info': product_info,
                                     'category': category,
                                     'phone': phone,
                                     'address': address,
                                     'remark': remark or '',
                                     'has_gift': has_gift,
                                     'gift_info': gift_list,
                                     'gender': gender if 'gender' in locals() else ''
                                 },
                                 duplicate_orders=existing_orders)

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
        customer_wechat=customer_wechat,
        paid_amount=paid,
        pay_date=pay_d,
        collect_amount=collect,
        gender=gender,
        has_gift=has_gift,
        gift_info=gift_info,
        group_id=current_user.group_id
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
    db.session.flush()  # 先获取order.id

    # 如果是保存草稿（AJAX请求），返回JSON
    if action == 'save_draft':
        db.session.commit()
        return jsonify({
            'success': True,
            'order_id': order.id,
            'message': '草稿已保存'
        })
    
    # 如果有设置预计发货时间，保存提醒
    if expected_shipping_time_str:
        try:
            expected_shipping_time = datetime.strptime(expected_shipping_time_str, '%Y-%m-%dT%H:%M')
            reminder = OrderReminder(
                order_id=order.id,
                user_id=current_user.id,
                expected_shipping_time=expected_shipping_time,
                is_sent=False
            )
            db.session.add(reminder)
        except ValueError:
            pass  # 时间格式错误，忽略提醒

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
        customer_wechat = request.form.get('customer_wechat')
        paid_amount = request.form.get('paid_amount')
        pay_date = request.form.get('pay_date')
        collect_amount = request.form.get('collect_amount')
        product_info = request.form.get('product_info')
        category = request.form.get('category')
        phone = request.form.get('phone')
        address = request.form.get('address')
        remark = request.form.get('remark', '')
        express_type = request.form.get('express_type')
        tracking_number = request.form.get('tracking_number')
        action = request.form.get('action')
        has_gift = request.form.get('has_gift') == 'on'
        gift_list = request.form.getlist('gift_info') if has_gift else []
        gift_info = '、'.join([g.strip() for g in gift_list if g.strip()])
        gender = request.form.get('gender')

        if not all([group_name, product_info, category, phone, address]):
            error_msg = '请填写所有必填字段！'
            # 保留数据返回表单
            return render_template('edit_order.html',
                                 order=order,
                                 unread_count=get_unread_count(current_user.id),
                                 categories=get_active_categories(),
                                 gifts=get_active_gifts(),
                                 form_data={
                                     'group_name': group_name,
                                     'customer_name': customer_name or '',
                                     'customer_wechat': customer_wechat or '',
                                     'paid_amount': paid_amount or '',
                                     'pay_date': pay_date or '',
                                     'collect_amount': collect_amount or '',
                                     'product_info': product_info,
                                     'category': category,
                                     'phone': phone,
                                     'address': address,
                                     'remark': remark or '',
                                     'has_gift': has_gift,
                                     'gift_info': gift_list,
                                     'gender': gender,
                                     'express_type': express_type or '',
                                     'tracking_number': tracking_number or ''
                                 },
                                 error=error_msg)
        
        # 验证金额（只在提交订单时验证，保存草稿不验证）
        if action == 'submit':
            is_valid, error_msg = validate_order_amount(category, product_info, paid_amount, collect_amount)
            if not is_valid:
                # 保留数据返回表单
                return render_template('edit_order.html',
                                     order=order,
                                     unread_count=get_unread_count(current_user.id),
                                     categories=get_active_categories(),
                                     gifts=get_active_gifts(),
                                     form_data={
                                         'group_name': group_name,
                                         'customer_name': customer_name or '',
                                         'customer_wechat': customer_wechat or '',
                                         'paid_amount': paid_amount or '',
                                         'pay_date': pay_date or '',
                                         'collect_amount': collect_amount or '',
                                         'product_info': product_info,
                                         'category': category,
                                         'phone': phone,
                                         'address': address,
                                         'remark': remark or '',
                                         'has_gift': has_gift,
                                         'gift_info': gift_list,
                                         'gender': gender,
                                         'express_type': express_type or '',
                                         'tracking_number': tracking_number or ''
                                     },
                                     error=error_msg)

        order.group_name = group_name
        order.customer_name = customer_name
        order.customer_wechat = customer_wechat
        order.paid_amount = paid_amount.strip() if paid_amount else None
        order.pay_date = datetime.strptime(pay_date, '%Y-%m-%d').date() if pay_date else None
        order.collect_amount = float(collect_amount) if collect_amount else 0
        order.product_info = product_info
        order.category = category
        order.phone = phone
        order.address = address
        order.remark = remark
        order.express_type = express_type
        order.tracking_number = tracking_number
        order.has_gift = has_gift
        order.gift_info = gift_info
        order.gender = gender

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


@bp.route('/order/edit_submitted/<int:order_id>', methods=['GET', 'POST'])
@role_required('salesman')
def edit_submitted_order(order_id):
    """编辑待发货订单"""
    order = Order.query.get_or_404(order_id)
    if order.salesman_id != current_user.id or order.status != 'submitted':
        flash('您只能编辑自己的待发货订单！', 'danger')
        return redirect(url_for('orders.dashboard'))

    if request.method == 'POST':
        customer_name = request.form.get('customer_name')
        phone = request.form.get('phone')
        address = request.form.get('address')
        remark = request.form.get('remark', '')
        gender = request.form.get('gender')

        if not all([phone, address]):
            error_msg = '请填写必填字段！'
            return render_template('edit_submitted_order.html',
                                 order=order,
                                 unread_count=get_unread_count(current_user.id),
                                 form_data={
                                     'customer_name': customer_name or '',
                                     'phone': phone,
                                     'address': address,
                                     'remark': remark or '',
                                     'gender': gender
                                 },
                                 error=error_msg)

        order.customer_name = customer_name
        order.phone = phone
        order.address = address
        order.remark = remark
        order.gender = gender
        
        from models import _now_bj
        order.update_time = _now_bj()
        
        flash('订单已更新！', 'success')
        db.session.commit()
        return redirect(url_for('orders.dashboard'))

    return render_template('edit_submitted_order.html',
                           order=order,
                           unread_count=get_unread_count(current_user.id))


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
        'customer_wechat': order.customer_wechat or '',
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
        'is_main_product': is_main_product,
        'gender': order.gender or ''
    })


@bp.route('/api/categories')
@login_required
def api_categories():
    """获取赠品类别（用于补发赠品），可根据订单ID筛选相关赠品"""
    order_id = request.args.get('order_id', type=int)
    
    if order_id:
        # 如果有订单ID，根据订单的主品筛选赠品
        order = Order.query.get_or_404(order_id)
        # 查找订单类别对应的主品ID
        main_product = Category.query.filter_by(name=order.category, is_active=True, is_main_product=True).first()
        
        if main_product:
            # 查询：通用赠品 + 关联该主品的赠品
            categories = Category.query.filter_by(is_active=True, is_gift=True).filter(
                (Category.related_main_product_id.is_(None)) | 
                (Category.related_main_product_id == main_product.id)
            ).order_by(Category.sort_order.asc(), Category.id.asc()).all()
        else:
            # 找不到对应的主品，返回所有赠品
            categories = Category.query.filter_by(is_active=True, is_gift=True).order_by(Category.sort_order.asc(), Category.id.asc()).all()
    else:
        # 没有订单ID，返回所有赠品
        categories = Category.query.filter_by(is_active=True, is_gift=True).order_by(Category.sort_order.asc(), Category.id.asc()).all()
    
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

    # 未发货或无单号，返回空
    if order.status != 'shipped' or not order.tracking_number:
        return jsonify({'routes': [], 'tracking_number': order.tracking_number or '', 'express_type': order.express_type or ''})
    
    # 检查是否为主品
    cat = Category.query.filter_by(name=order.category, is_active=True).first()
    is_main_product = cat and cat.is_main_product
    
    if is_main_product and order.express_type == '顺丰':
        # 主品顺丰：使用顺丰API
        from services import get_logistics_with_cache
        result = get_logistics_with_cache(order, force_refresh=False)
        return jsonify({
            'routes': result['routes'],
            'tracking_number': order.tracking_number,
            'express_type': order.express_type,
            'logistics_status': order.logistics_status or '',
            'from_cache': result['from_cache']
        })
    else:
        # 非主品或非顺丰：使用 uapis.cn API (带缓存，不更新数据库)
        from services import get_logistics_uapis_with_cache
        result = get_logistics_uapis_with_cache(order, force_refresh=False, update_db=False)
        
        # 无论成功与否都返回结果，这样前端能显示刷新按钮
        return jsonify({
            'routes': result['routes'],
            'tracking_number': order.tracking_number,
            'express_type': order.express_type or '',
            'logistics_status': result.get('status', order.logistics_status or ''),
            'from_cache': result.get('from_cache', False)
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

    # 未发货或无单号
    if order.status != 'shipped' or not order.tracking_number:
        return jsonify({'error': '未发货或无快递单号'}), 400
    
    # 检查是否为主品
    cat = Category.query.filter_by(name=order.category, is_active=True).first()
    is_main_product = cat and cat.is_main_product
    
    if is_main_product and order.express_type == '顺丰':
        # 主品顺丰：使用顺丰API
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
    else:
        # 非主品或非顺丰：使用 uapis.cn API (带缓存，强制刷新，不更新数据库)
        from services import get_logistics_uapis_with_cache
        result = get_logistics_uapis_with_cache(order, force_refresh=True, update_db=False)
        
        if 'error' in result:
            return jsonify({
                'error': result.get('error', '查询失败')
            }), 400
        
        return jsonify({
            'success': True,
            'routes': result['routes'],
            'tracking_number': order.tracking_number,
            'express_type': order.express_type or '',
            'logistics_status': result.get('status', order.logistics_status or ''),
            'from_cache': False
        })


@bp.route('/api/order/<int:order_id>/edit', methods=['POST'])
@login_required
def api_order_edit(order_id):
    """编辑订单API（管理员可编辑所有，业务员只能编辑自己的）"""
    order = Order.query.get_or_404(order_id)
    
    # 权限检查：admin账号可编辑所有，其他管理员按组别，业务员只能编辑自己的
    if current_user.username == 'admin':
        pass  # admin账号可编辑所有
    elif current_user.has_role('admin') and current_user.group_id:
        # 其他管理员：按组别过滤
        managed_group_ids = current_user.get_managed_group_ids()
        if order.group_id not in managed_group_ids:
            return jsonify({'error': '无权编辑此订单'}), 403
    elif current_user.has_role('salesman'):
        # 业务员：只能编辑自己的订单
        if order.salesman_id != current_user.id:
            return jsonify({'error': '无权编辑此订单'}), 403
    else:
        # 其他角色（如发货员）无权编辑
        return jsonify({'error': '无权编辑此订单'}), 403

    # 保存旧值用于比较
    old_values = {
        'customer_name': order.customer_name,
        'customer_wechat': order.customer_wechat,
        'phone': order.phone,
        'address': order.address,
        'product_info': order.product_info,
        'paid_amount': order.paid_amount,
        'collect_amount': order.collect_amount,
        'remark': order.remark,
        'tracking_number': order.tracking_number,
        'express_type': order.express_type,
        'gender': order.gender
    }

    # 获取新值
    new_customer_name = request.form.get('customer_name', '').strip()
    new_customer_wechat = request.form.get('customer_wechat', '').strip()
    new_phone = request.form.get('phone', '').strip()
    new_address = request.form.get('address', '').strip()
    new_product_info = request.form.get('product_info', '').strip()
    new_paid_amount = request.form.get('paid_amount', '').strip()
    new_collect_amount = request.form.get('collect_amount', '').strip()
    new_remark = request.form.get('remark', '').strip()
    new_tracking_number = request.form.get('tracking_number', '').strip()
    new_express_type = request.form.get('express_type', '').strip()
    new_gender = request.form.get('gender', '').strip()

    # 更新字段
    order.customer_name = new_customer_name
    order.customer_wechat = new_customer_wechat if new_customer_wechat else None
    order.phone = new_phone
    order.address = new_address
    order.product_info = new_product_info
    order.paid_amount = new_paid_amount if new_paid_amount else None
    order.collect_amount = float(new_collect_amount) if new_collect_amount else 0
    order.remark = new_remark
    
    # 更新运单号和状态
    order.tracking_number = new_tracking_number if new_tracking_number else None
    order.express_type = new_express_type if new_express_type else None
    
    # 如果有运单号且当前是待发货状态，自动改为已发货状态
    if new_tracking_number and order.status == 'submitted':
        order.status = 'shipped'
        
        # 判断是否为主品，非主品发货即签收
        category = Category.query.filter_by(name=order.category).first()
        if category and not category.is_main_product:
            # 非主品：发货即签收
            order.logistics_status = '已签收'
        elif new_express_type == '顺丰':
            # 主品且顺丰：标记为已发货
            order.logistics_status = '已发货'
    
    order.gender = new_gender if new_gender else None
    from models import _now_bj
    order.update_time = _now_bj()

    db.session.commit()

    # 生成修改通知
    changes = []
    field_labels = {
        'customer_name': '客户姓名',
        'customer_wechat': '客户微信名',
        'phone': '电话',
        'address': '地址',
        'product_info': '产品信息',
        'paid_amount': '已付定金',
        'collect_amount': '代收金额',
        'remark': '备注',
        'tracking_number': '快递单号',
        'express_type': '快递类型',
        'gender': '性别'
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


@bp.route('/order/submit/<int:order_id>', methods=['POST'])
@role_required('salesman')
def submit_order(order_id):
    """提交草稿订单"""
    order = Order.query.get_or_404(order_id)
    if order.salesman_id != current_user.id:
        flash('您只能提交自己的订单！', 'danger')
        return redirect(url_for('orders.dashboard'))
    
    if order.status != 'draft':
        flash('只有草稿状态的订单才能提交！', 'warning')
        return redirect(url_for('orders.dashboard'))
    
    order.status = 'submitted'
    from models import _now_bj
    order.update_time = _now_bj()
    
    shipper_ids = [s.id for s in User.query.filter(User.roles.like('%shipper%'), User.is_active==True).all()]
    customer_info = f"{order.customer_name or '未知'}-{order.phone}" if order.customer_name else order.phone
    notify_users(shipper_ids,
                 f'新的待发货订单：{order.group_name}，客户：{customer_info}，业务员：{current_user.name}，请及时处理！',
                 order_id=order.id)
    
    db.session.commit()
    flash('订单已提交，已通知发货员！', 'success')
    return redirect(url_for('orders.dashboard'))


@bp.route('/order/delete/<int:order_id>', methods=['POST'])
@role_required('salesman')
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.salesman_id != current_user.id:
        flash('您只能删除自己的订单！', 'danger')
        return redirect(url_for('orders.dashboard'))

    if order.status == 'draft':
        # 先删除关联的提醒记录
        OrderReminder.query.filter_by(order_id=order.id).delete()
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
        # 先删除关联的提醒记录
        OrderReminder.query.filter_by(order_id=order.id).delete()
        db.session.delete(order)
        db.session.commit()
        flash('订单已删除！（金额为0，无需审批）', 'success')
        return redirect(url_for('orders.dashboard'))

    from models import _now_bj
    order.delete_requested = True
    order.delete_request_time = _now_bj()
    db.session.commit()
    customer_info = f"{order.customer_name or '未知'}-{order.phone}" if order.customer_name else order.phone
    notify_user_upward_admin(current_user,
                 f'业务员 {current_user.name} 提交了删除订单 {order.group_name}（客户：{customer_info}）的申请，请处理！',
                 order_id=order.id)
    flash('删除申请已提交，等待管理员审批！', 'success')
    return redirect(url_for('orders.dashboard'))


# ============ 订单提醒API ============
@bp.route('/api/order/<int:order_id>/reminder', methods=['POST'])
@login_required
def update_order_reminder(order_id):
    """更新订单的预计发货时间和提醒"""
    order = Order.query.get_or_404(order_id)
    
    # 检查权限：只有订单的业务员才能设置提醒
    if order.salesman_id != current_user.id:
        return jsonify({'success': False, 'error': '没有权限操作此订单'})
    
    data = request.get_json()
    if not data or 'expected_shipping_time' not in data:
        return jsonify({'success': False, 'error': '缺少预计发货日期'})
    
    expected_shipping_date_str = data['expected_shipping_time']
    
    try:
        # 解析日期（格式为 YYYY-MM-DD）
        expected_shipping_date = datetime.strptime(expected_shipping_date_str, '%Y-%m-%d')
        # 设置时间为当天凌晨1点
        expected_shipping_time = expected_shipping_date.replace(hour=1, minute=0, second=0, microsecond=0)
    except ValueError:
        return jsonify({'success': False, 'error': '日期格式错误'})
    
    # 删除该订单之前的所有未发送提醒
    OrderReminder.query.filter_by(order_id=order_id, is_sent=False).delete()
    
    # 创建新的提醒
    reminder = OrderReminder(
        order_id=order_id,
        user_id=current_user.id,
        expected_shipping_time=expected_shipping_time,
        is_sent=False
    )
    db.session.add(reminder)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '提醒已设置，将在预计发货时间前通知您'
    })
