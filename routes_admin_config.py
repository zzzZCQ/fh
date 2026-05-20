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

    query = Category.query

    # 筛选条件
    if name_keyword:
        query = query.filter(Category.name.contains(name_keyword))
    if is_main_product == '1':
        query = query.filter(Category.is_main_product == True)
    elif is_main_product == '0':
        query = query.filter(Category.is_main_product == False)

    categories = query.order_by(Category.sort_order.asc(), Category.id.asc()).paginate(
        page=page, per_page=10, error_out=False)

    return render_template('admin_categories.html', categories=categories,
                           unread_count=get_unread_count(current_user.id))


@bp.route('/admin/category/add', methods=['POST'])
@role_required('admin')
def add_category():
    name = request.form.get('name', '').strip()
    sort_order = request.form.get('sort_order', 0, type=int)
    is_main_product = request.form.get('is_main_product') == 'on'
    if not name:
        flash('类别名称不能为空！', 'danger')
        return redirect(url_for('admin_config.admin_categories'))
    if Category.query.filter_by(name=name).first():
        flash('类别名称已存在！', 'danger')
        return redirect(url_for('admin_config.admin_categories'))
    db.session.add(Category(name=name, sort_order=sort_order, is_main_product=is_main_product, example=request.form.get('example', '').strip()))
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
    category.example = request.form.get('example', '').strip()
    category.is_active = is_active
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


# ============ 数据库管理 ============
@bp.route('/admin/db')
@role_required('admin')
def admin_db_viewer():
    """数据库查看/编辑界面"""
    import sqlite3
    from math import ceil

    # 获取所有表名
    conn = sqlite3.connect('instance/delivery.db')
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in c.fetchall()]

    current_table = request.args.get('table', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    # 限制每页条数在合理范围内
    if per_page not in [10, 20, 50, 100, 200]:
        per_page = 10

    rows = []
    columns = []
    column_info = []  # 列详细信息：包含类型、是否主键、是否非空等
    total_count = 0
    total_pages = 0

    if current_table and current_table in tables:
        # 获取列信息（表名加引号防止关键字冲突）
        # PRAGMA table_info 返回: (cid, name, type, notnull, dflt_value, pk)
        c.execute(f'PRAGMA table_info("{current_table}")')
        col_data = c.fetchall()
        columns = [col[1] for col in col_data]
        column_info = [{
            'name': col[1],
            'type': col[2],
            'notnull': bool(col[3]),
            'default': col[4],
            'pk': bool(col[5])
        } for col in col_data]

        # 获取总数（表名加引号）
        c.execute(f'SELECT COUNT(*) FROM "{current_table}"')
        total_count = c.fetchone()[0]
        total_pages = ceil(total_count / per_page)

        # 获取分页数据（表名加引号）
        offset = (page - 1) * per_page
        c.execute(f'SELECT * FROM "{current_table}" ORDER BY id DESC LIMIT ? OFFSET ?', (per_page, offset))
        rows = c.fetchall()

    conn.close()

    return render_template('admin_db_viewer.html',
                           tables=tables,
                           current_table=current_table,
                           columns=columns,
                           column_info=column_info,
                           rows=rows,
                           page=page,
                           per_page=per_page,
                           total_pages=total_pages,
                           total_count=total_count,
                           unread_count=get_unread_count(current_user.id))


@bp.route('/admin/db/update/<table>/<int:id>', methods=['POST'])
@role_required('admin')
def admin_db_update(table, id):
    """更新数据库记录"""
    import sqlite3

    # 获取表单数据
    data = {k: v for k, v in request.form.items()}

    if not data:
        flash('没有要更新的数据', 'warning')
        return redirect(url_for('admin_config.admin_db_viewer', table=table))

    conn = sqlite3.connect('instance/delivery.db')
    c = conn.cursor()

    # 获取列信息进行类型验证
    c.execute(f'PRAGMA table_info("{table}")')
    col_info = {col[1]: {'type': col[2], 'pk': bool(col[5]), 'notnull': bool(col[3])} 
                for col in c.fetchall()}

    # 类型验证
    errors = []
    validated_data = {}
    for col_name, value in data.items():
        if col_name not in col_info:
            errors.append(f"字段 '{col_name}' 不存在")
            continue
        
        col_type = col_info[col_name]['type'].upper()
        is_pk = col_info[col_name]['pk']
        
        # 主键字段不允许修改
        if is_pk:
            continue
        
        # 根据类型验证
        try:
            if col_type in ('INTEGER', 'INT', 'TINYINT', 'SMALLINT', 'MEDIUMINT', 'BIGINT'):
                if value.strip():
                    validated_data[col_name] = int(value)
                else:
                    validated_data[col_name] = None
            elif col_type in ('REAL', 'DOUBLE', 'FLOAT', 'NUMERIC', 'DECIMAL'):
                if value.strip():
                    validated_data[col_name] = float(value)
                else:
                    validated_data[col_name] = None
            elif col_type == 'BOOLEAN':
                if value.strip().lower() in ('true', '1', 'yes'):
                    validated_data[col_name] = 1
                elif value.strip().lower() in ('false', '0', 'no'):
                    validated_data[col_name] = 0
                elif not value.strip():
                    validated_data[col_name] = None
                else:
                    raise ValueError(f"'{value}' 不是有效的布尔值")
            else:
                validated_data[col_name] = value if value.strip() else None
        except ValueError as e:
            errors.append(f"字段 '{col_name}' 类型错误: {col_info[col_name]['type']} - {str(e)}")

    if errors:
        conn.close()
        for err in errors:
            flash(err, 'danger')
        return redirect(url_for('admin_config.admin_db_viewer', table=table))

    if not validated_data:
        flash('没有有效的数据需要更新', 'warning')
        conn.close()
        return redirect(url_for('admin_config.admin_db_viewer', table=table))

    # 构建UPDATE语句
    set_clause = ', '.join([f"{k}=?" for k in validated_data.keys()])
    values = list(validated_data.values()) + [id]

    try:
        c.execute(f'UPDATE "{table}" SET {set_clause} WHERE id=?', values)
        conn.commit()
        flash(f'记录 #{id} 更新成功', 'success')
    except Exception as e:
        flash(f'更新失败: {e}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('admin_config.admin_db_viewer', table=table))


@bp.route('/admin/db/update-field/<table>/<int:id>', methods=['POST'])
@role_required('admin')
def admin_db_update_field(table, id):
    """更新单个字段（AJAX）"""
    import sqlite3
    from flask import jsonify

    field = request.form.get('field', '')
    value = request.form.get('value', '')

    if not field:
        return jsonify({'success': False, 'message': '字段名不能为空'})

    conn = sqlite3.connect('instance/delivery.db')
    c = conn.cursor()

    # 获取列信息进行类型验证
    c.execute(f'PRAGMA table_info("{table}")')
    col_info = {col[1]: {'type': col[2], 'pk': bool(col[5]), 'notnull': bool(col[3])} 
                for col in c.fetchall()}

    if field not in col_info:
        conn.close()
        return jsonify({'success': False, 'message': f"字段 '{field}' 不存在"})

    col_type = col_info[field]['type'].upper()
    is_pk = col_info[field]['pk']

    # 主键字段不允许修改
    if is_pk:
        conn.close()
        return jsonify({'success': False, 'message': '主键字段不可修改'})

    # 类型验证
    try:
        if col_type in ('INTEGER', 'INT', 'TINYINT', 'SMALLINT', 'MEDIUMINT', 'BIGINT'):
            validated_value = int(value) if value.strip() else None
        elif col_type in ('REAL', 'DOUBLE', 'FLOAT', 'NUMERIC', 'DECIMAL'):
            validated_value = float(value) if value.strip() else None
        elif col_type == 'BOOLEAN':
            if value.strip().lower() in ('true', '1', 'yes'):
                validated_value = 1
            elif value.strip().lower() in ('false', '0', 'no'):
                validated_value = 0
            elif not value.strip():
                validated_value = None
            else:
                raise ValueError(f"'{value}' 不是有效的布尔值")
        else:
            validated_value = value if value.strip() else None
    except ValueError as e:
        conn.close()
        return jsonify({'success': False, 'message': f"类型错误: {col_info[field]['type']} - {str(e)}"})

    # 执行更新
    try:
        c.execute(f'UPDATE "{table}" SET {field}=? WHERE id=?', (validated_value, id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '更新成功'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'})


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
