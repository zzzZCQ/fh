# -*- coding: utf-8 -*-
"""管理配置路由（类别、赠品、数据库查看）"""
import os
from flask import Blueprint, request, redirect, url_for, flash, render_template
from flask_login import current_user, login_required

from models import db, Order, Category, Gift
from helpers import role_required, get_unread_count, broadcast_notification

bp = Blueprint('admin_config', __name__)


# ============ 类别配置 ============
@bp.route('/admin/categories')
@role_required('admin')
def admin_categories():
    page = request.args.get('page', 1, type=int)
    name_keyword = request.args.get('name_keyword', '').strip()
    is_main_product = request.args.get('is_main_product', '')
    is_gift = request.args.get('is_gift', '')

    query = Category.query

    # 筛选条件
    if name_keyword:
        query = query.filter(Category.name.contains(name_keyword))
    if is_main_product == '1':
        query = query.filter(Category.is_main_product == True)
    elif is_main_product == '0':
        query = query.filter(Category.is_main_product == False)
    if is_gift == '1':
        query = query.filter(Category.is_gift == True)
    elif is_gift == '0':
        query = query.filter(Category.is_gift == False)

    categories = query.order_by(Category.sort_order.asc(), Category.id.asc()).paginate(
        page=page, per_page=10, error_out=False)

    from models import _now_bj
    # 获取所有启用的主品
    main_products = Category.query.filter_by(is_active=True, is_main_product=True).order_by(Category.sort_order.asc(), Category.id.asc()).all()
    return render_template('admin_categories.html', categories=categories,
                           main_products=main_products,
                           unread_count=get_unread_count(current_user.id),
                           now_bj=_now_bj())


@bp.route('/admin/category/add', methods=['POST'])
@role_required('admin')
def add_category():
    name = request.form.get('name', '').strip()
    sort_order = request.form.get('sort_order', 0, type=int)
    is_main_product = request.form.get('is_main_product') == 'on'
    is_gift = request.form.get('is_gift') == 'on'
    related_main_product_id = request.form.get('related_main_product_id', '', type=int) or None
    unit_price = request.form.get('unit_price', 0.0, type=float)
    expire_time_str = request.form.get('expire_time', '').strip()
    
    from models import _now_bj
    expire_time = None
    if expire_time_str:
        try:
            from datetime import datetime
            expire_time = datetime.strptime(expire_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass
    
    if not name:
        flash('类别名称不能为空！', 'danger')
        return redirect(url_for('admin_config.admin_categories'))
    if Category.query.filter_by(name=name).first():
        flash('类别名称已存在！', 'danger')
        return redirect(url_for('admin_config.admin_categories'))
    
    # 如果不是赠品，清空关联主品
    if not is_gift:
        related_main_product_id = None
    
    db.session.add(Category(
        name=name, 
        sort_order=sort_order, 
        is_main_product=is_main_product,
        is_gift=is_gift,
        related_main_product_id=related_main_product_id,
        example=request.form.get('example', '').strip(),
        unit_price=unit_price,
        expire_time=expire_time
    ))
    db.session.commit()
    flash(f'类别 "{name}" 添加成功！', 'success')
    return redirect(url_for('admin_config.admin_categories'))


@bp.route('/admin/category/edit/<int:category_id>', methods=['POST'])
@role_required('admin')
def edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    name = request.form.get('name', '').strip()
    sort_order = request.form.get('sort_order', 0, type=int)
    is_active = request.form.get('is_active') == 'on'
    is_main_product = request.form.get('is_main_product') == 'on'
    is_gift = request.form.get('is_gift') == 'on'
    related_main_product_id = request.form.get('related_main_product_id', '', type=int) or None
    unit_price = request.form.get('unit_price', 0.0, type=float)
    expire_time_str = request.form.get('expire_time', '').strip()
    
    expire_time = None
    if expire_time_str:
        try:
            from datetime import datetime
            expire_time = datetime.strptime(expire_time_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass
    
    if not name:
        flash('类别名称不能为空！', 'danger')
        return redirect(url_for('admin_config.admin_categories'))
    existing = Category.query.filter_by(name=name).first()
    if existing and existing.id != category_id:
        flash('类别名称已存在！', 'danger')
        return redirect(url_for('admin_config.admin_categories'))
    
    category.name = name
    category.sort_order = sort_order
    category.is_main_product = is_main_product
    category.is_gift = is_gift
    
    # 如果不是赠品，清空关联主品
    if not is_gift:
        category.related_main_product_id = None
    else:
        category.related_main_product_id = related_main_product_id
    
    category.example = request.form.get('example', '').strip()
    category.is_active = is_active
    category.unit_price = unit_price
    category.expire_time = expire_time
    db.session.commit()
    flash(f'类别 "{name}" 更新成功！', 'success')
    return redirect(url_for('admin_config.admin_categories'))


@bp.route('/admin/category/delete/<int:category_id>', methods=['POST'])
@role_required('admin')
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    order_count = Order.query.filter_by(category=category.name).count()
    if order_count > 0:
        flash(f'无法删除，有 {order_count} 个订单正在使用此类别！', 'danger')
        return redirect(url_for('admin_config.admin_categories'))
    db.session.delete(category)
    db.session.commit()
    flash(f'类别 "{category.name}" 删除成功！', 'success')
    return redirect(url_for('admin_config.admin_categories'))


# ============ 赠品配置 ============
@bp.route('/admin/gifts')
@role_required('admin')
def admin_gifts():
    gifts = Gift.query.order_by(Gift.sort_order.asc(), Gift.id.asc()).all()
    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order.asc()).all()
    return render_template('admin_gifts.html', gifts=gifts, categories=categories,
                           unread_count=get_unread_count(current_user.id))


@bp.route('/admin/gift/add', methods=['POST'])
@role_required('admin')
def add_gift():
    name = request.form.get('name', '').strip()
    category_id = request.form.get('category_id', '', type=int) or None
    sort_order = request.form.get('sort_order', 0, type=int)
    if not name:
        flash('赠品名称不能为空！', 'danger')
        return redirect(url_for('admin_config.admin_gifts'))
    # 同一类别下赠品名称不能重复
    if Gift.query.filter_by(name=name, category_id=category_id).first():
        flash('该类别下已存在同名赠品！', 'danger')
        return redirect(url_for('admin_config.admin_gifts'))
    db.session.add(Gift(name=name, category_id=category_id, sort_order=sort_order))
    db.session.commit()
    flash(f'赠品 "{name}" 添加成功！', 'success')
    return redirect(url_for('admin_config.admin_gifts'))


@bp.route('/admin/gift/edit/<int:gift_id>', methods=['POST'])
@role_required('admin')
def edit_gift(gift_id):
    gift = Gift.query.get_or_404(gift_id)
    name = request.form.get('name', '').strip()
    category_id = request.form.get('category_id', '', type=int) or None
    sort_order = request.form.get('sort_order', 0, type=int)
    is_active = request.form.get('is_active') == 'on'
    if not name:
        flash('赠品名称不能为空！', 'danger')
        return redirect(url_for('admin_config.admin_gifts'))
    existing = Gift.query.filter_by(name=name, category_id=category_id).first()
    if existing and existing.id != gift_id:
        flash('该类别下已存在同名赠品！', 'danger')
        return redirect(url_for('admin_config.admin_gifts'))
    gift.name = name
    gift.category_id = category_id
    gift.sort_order = sort_order
    gift.is_active = is_active
    db.session.commit()
    flash(f'赠品 "{name}" 更新成功！', 'success')
    return redirect(url_for('admin_config.admin_gifts'))


@bp.route('/admin/gift/delete/<int:gift_id>', methods=['POST'])
@role_required('admin')
def delete_gift(gift_id):
    gift = Gift.query.get_or_404(gift_id)
    db.session.delete(gift)
    db.session.commit()
    flash(f'赠品 "{gift.name}" 删除成功！', 'success')
    return redirect(url_for('admin_config.admin_gifts'))





# ============ 广播消息 ============
@bp.route('/broadcast')
@login_required
def admin_broadcast():
    """广播消息页面"""
    from models import User
    
    if not (current_user.has_role('admin') and current_user.can_broadcast):
        flash('您没有发送广播通知的权限！', 'danger')
        return redirect(url_for('orders.dashboard'))
    
    if current_user.username == 'admin':
        users = User.query.filter(User.is_active == True, User.id != current_user.id).order_by(User.username).all()
    else:
        target_group_ids = current_user.get_managed_group_ids()
        users = User.query.filter(
            User.is_active == True,
            User.group_id.in_(target_group_ids),
            User.id != current_user.id
        ).order_by(User.username).all()
    
    return render_template('admin_broadcast.html', users=users, unread_count=get_unread_count(current_user.id))


@bp.route('/broadcast/send', methods=['POST'])
@login_required
def send_broadcast():
    """发送广播消息"""
    from models import User
    
    if not (current_user.has_role('admin') and current_user.can_broadcast):
        flash('您没有发送广播通知的权限！', 'danger')
        return redirect(url_for('orders.dashboard'))
    
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('消息内容不能为空！', 'danger')
        return redirect(url_for('admin_config.admin_broadcast'))
    
    importance = request.form.get('importance', 'normal')
    if importance not in ['normal', 'important', 'urgent']:
        importance = 'normal'
    
    image_url = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            filename = file.filename
            upload_dir = os.path.join('static', 'uploads', 'broadcast')
            os.makedirs(upload_dir, exist_ok=True)
            filepath = os.path.join(upload_dir, filename)
            file.save(filepath)
            image_url = '/' + filepath.replace('\\', '/')
    
    user_ids = request.form.getlist('user_ids')
    user_ids = [int(uid) for uid in user_ids if uid.isdigit()] if user_ids else None
    
    if user_ids:
        count = len(user_ids)
    elif current_user.username == 'admin':
        count = User.query.filter(User.is_active == True, User.id != current_user.id).count()
    else:
        target_group_ids = current_user.get_managed_group_ids()
        count = User.query.filter(
            User.is_active == True,
            User.group_id.in_(target_group_ids),
            User.id != current_user.id
        ).count()
    
    broadcast_notification(current_user, content, image_url, user_ids, importance)
    
    importance_text = {'normal': '一般', 'important': '重要', 'urgent': '紧急'}.get(importance, '一般')
    flash(f'消息已发送（{importance_text}），共发送给 {count} 位用户！', 'success')
    return redirect(url_for('admin_config.admin_broadcast'))


# ============ 版本配置 ============
@bp.route('/admin/version')
@role_required('admin')
def admin_version():
    """版本配置页面"""
    if current_user.username != 'admin':
        flash('只有超级管理员可以访问版本配置！', 'danger')
        return redirect(url_for('orders.dashboard'))
    
    from config import APP_VERSION, MIN_SUPPORTED_VERSION, VERSION_RELEASE_DATE
    return render_template('admin_version.html',
                           app_version=APP_VERSION,
                           min_supported_version=MIN_SUPPORTED_VERSION,
                           version_release_date=VERSION_RELEASE_DATE,
                           unread_count=get_unread_count(current_user.id))


@bp.route('/admin/version/update', methods=['POST'])
@role_required('admin')
def update_version():
    """更新版本配置"""
    if current_user.username != 'admin':
        flash('只有超级管理员可以修改版本配置！', 'danger')
        return redirect(url_for('orders.dashboard'))
    
    app_version = request.form.get('app_version', '').strip()
    min_supported_version = request.form.get('min_supported_version', '').strip()
    version_release_date = request.form.get('version_release_date', '').strip()
    
    # 更新 config.py 文件
    config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换版本配置
    import re
    content = re.sub(r'APP_VERSION\s*=\s*".*?"', f'APP_VERSION = "{app_version}"', content)
    content = re.sub(r'MIN_SUPPORTED_VERSION\s*=\s*".*?"', f'MIN_SUPPORTED_VERSION = "{min_supported_version}"', content)
    content = re.sub(r'VERSION_RELEASE_DATE\s*=\s*".*?"', f'VERSION_RELEASE_DATE = "{version_release_date}"', content)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    flash('版本配置更新成功！重启应用后生效。', 'success')
    return redirect(url_for('admin_config.admin_version'))
