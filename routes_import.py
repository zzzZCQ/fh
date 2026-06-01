# -*- coding: utf-8 -*-
"""批量导入、导入模板管理、业绩报表模板管理路由"""
import os
import re
import json
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import db, User, Order, Category, ImportTemplate, PerformanceReportTemplate, _now_bj
from helpers import role_required, get_unread_count, notify_users

bp = Blueprint('import_routes', __name__)

# 引入模板管理中的共享变量
from routes_templates import UPLOAD_FOLDER, allowed_file


# ============ 批量导入快递信息 ============
@bp.route('/batch_import')
@role_required('shipper', 'admin')
def batch_import_page():
    """批量导入页面"""
    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order.asc()).all()
    import_templates = ImportTemplate.query.all()
    template_map = {t.category_id: t for t in import_templates}
    return render_template('batch_import.html', categories=categories,
                           import_templates=import_templates, template_map=template_map,
                           unread_count=get_unread_count(current_user.id))


@bp.route('/admin/import_template/upload', methods=['POST'])
@role_required('admin')
def upload_import_template():
    """上传导入模板（支持从现有模板复制）"""
    category_id = request.form.get('category_id', type=int)
    file = request.files.get('file')
    copy_from_template_id = request.form.get('copy_from_template_id', type=int)

    if not category_id:
        flash('请选择产品类别！', 'danger')
        return redirect(url_for('templates.admin_templates'))

    # 收集字段映射
    field_mapping = {}
    idx = 0
    while True:
        excel_col = request.form.get(f'excel_col_{idx}', '').strip()
        order_field = request.form.get(f'order_field_{idx}', '').strip()
        if not excel_col and not order_field:
            break
        if excel_col and order_field:
            field_mapping[excel_col] = order_field
        idx += 1

    # 获取默认快递种类
    default_express_type = request.form.get('default_express_type', '').strip()

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    filename = None
    filepath = None

    # 处理文件：优先使用复制的文件，否则上传新文件
    if copy_from_template_id:
        # 从现有模板复制
        source_template = ImportTemplate.query.get(copy_from_template_id)
        if source_template and os.path.exists(source_template.filepath):
            filename = source_template.filename
            # 创建新文件名（添加时间戳）
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            saved_name = f"import_{category_id}_{timestamp}_{filename}"
            filepath = os.path.join(UPLOAD_FOLDER, saved_name)
            # 复制文件
            import shutil
            shutil.copy2(source_template.filepath, filepath)
    elif file and file.filename:
        # 上传新文件
        if not allowed_file(file.filename):
            flash('只允许上传Excel文件（.xlsx, .xls）！', 'danger')
            return redirect(url_for('templates.admin_templates'))
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        saved_name = f"import_{category_id}_{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, saved_name)
        file.save(filepath)
    else:
        flash('请选择文件或从现有模板复制！', 'danger')
        return redirect(url_for('templates.admin_templates'))

    existing = ImportTemplate.query.filter_by(category_id=category_id).first()
    if existing:
        if os.path.exists(existing.filepath):
            os.remove(existing.filepath)
        existing.filename = filename
        existing.filepath = filepath
        existing.field_mapping = json.dumps(field_mapping, ensure_ascii=False)
        existing.default_express_type = default_express_type
        existing.create_time = _now_bj()
        flash('导入模板已更新！', 'success')
    else:
        template = ImportTemplate(category_id=category_id, filename=filename, filepath=filepath,
                                  field_mapping=json.dumps(field_mapping, ensure_ascii=False),
                                  default_express_type=default_express_type)
        db.session.add(template)
        flash('导入模板上传成功！', 'success')

    db.session.commit()
    return redirect(url_for('templates.admin_templates'))


@bp.route('/admin/import_template/delete/<int:template_id>', methods=['POST'])
@role_required('admin')
def delete_import_template(template_id):
    """删除导入模板"""
    template = ImportTemplate.query.get_or_404(template_id)
    if os.path.exists(template.filepath):
        os.remove(template.filepath)
    db.session.delete(template)
    db.session.commit()
    flash('导入模板删除成功！', 'success')
    return redirect(url_for('import_routes.batch_import_page'))


@bp.route('/admin/import_template/edit', methods=['POST'])
@role_required('admin')
def edit_import_template():
    """编辑导入模板（只更新字段映射，可选重新上传文件）"""
    template_id = request.form.get('template_id', type=int)
    template = ImportTemplate.query.get_or_404(template_id)

    # 收集字段映射
    field_mapping = {}
    idx = 0
    while True:
        excel_col = request.form.get(f'excel_col_{idx}', '').strip()
        order_field = request.form.get(f'order_field_{idx}', '').strip()
        if not excel_col and not order_field:
            break
        if excel_col and order_field:
            field_mapping[excel_col] = order_field
        idx += 1

    if not field_mapping:
        flash('至少需要配置一个字段映射！', 'danger')
        return redirect(url_for('templates.admin_templates'))

    # 处理可选的文件重新上传
    file = request.files.get('file')
    if file and file.filename:
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        new_filename = f"import_{template.category_id}_{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, new_filename)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file.save(filepath)
        # 删除旧文件
        if os.path.exists(template.filepath):
            os.remove(template.filepath)
        template.filepath = filepath
        template.filename = filename

    template.field_mapping = json.dumps(field_mapping, ensure_ascii=False)
    template.default_express_type = request.form.get('default_express_type', '').strip() or None
    db.session.commit()
    flash(f'导入模板 "{template.category.name}" 更新成功！', 'success')
    return redirect(url_for('templates.admin_templates'))


@bp.route('/api/import_template/mapping/<int:category_id>')
@login_required
def api_import_template_mapping(category_id):
    """获取某类别的导入模板映射配置"""
    template = ImportTemplate.query.filter_by(category_id=category_id).first()
    if template:
        return jsonify({
            'mapping': json.loads(template.field_mapping) if template.field_mapping else {},
            'default_express_type': template.default_express_type or ''
        })
    return jsonify({'mapping': {}, 'default_express_type': ''})


# ============ 业绩报表模板管理 ============
@bp.route('/admin/performance_templates')
@role_required('admin')
def admin_performance_templates():
    """业绩报表模板管理页面"""
    templates = PerformanceReportTemplate.query.filter_by(is_active=True).all()
    return render_template('admin_performance_templates.html',
                           templates=templates,
                           unread_count=get_unread_count(current_user.id))


@bp.route('/admin/performance_template/save', methods=['POST'])
@role_required('admin')
def save_performance_template():
    """保存业绩报表模板配置"""
    template_id = request.form.get('template_id', type=int)
    name = request.form.get('name', '').strip()
    template_file = request.files.get('template_file')

    # 字段映射
    field_mapping = {}
    excel_fields = request.form.getlist('excel_field[]')
    order_fields = request.form.getlist('order_field[]')
    for ef, of in zip(excel_fields, order_fields):
        if ef and of:
            field_mapping[ef] = of

    # 处理模板文件上传
    filepath = None
    if template_file and template_file.filename:
        filename = secure_filename(template_file.filename)
        filepath = os.path.join('uploads', 'performance_templates', filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        template_file.save(filepath)

    if template_id:
        template = PerformanceReportTemplate.query.get_or_404(template_id)
        template.name = name
        template.field_mapping = json.dumps(field_mapping, ensure_ascii=False)
        if filepath:
            template.filepath = filepath
    else:
        if not filepath:
            flash('请上传模板文件！', 'danger')
            return redirect(url_for('import_routes.admin_performance_templates'))
        template = PerformanceReportTemplate(
            name=name,
            field_mapping=json.dumps(field_mapping, ensure_ascii=False),
            filepath=filepath
        )
        db.session.add(template)

    db.session.commit()
    flash('业绩报表模板保存成功！', 'success')
    return redirect(url_for('import_routes.admin_performance_templates'))


@bp.route('/admin/performance_template/delete/<int:template_id>', methods=['POST'])
@role_required('admin')
def delete_performance_template(template_id):
    """删除业绩报表模板"""
    template = PerformanceReportTemplate.query.get_or_404(template_id)
    template.is_active = False
    db.session.commit()
    flash('业绩报表模板已删除！', 'success')
    return redirect(url_for('import_routes.admin_performance_templates'))


def extract_digits(s: str) -> str:
    """提取字符串中的所有数字，拼接成纯数字字符串"""
    if not s:
        return ""
    # 匹配所有数字字符并拼接

    ss = ''.join(re.findall(r'\d+', s))
    print(f"===========拼接后的字符串{ss}")
    return ss


def col_letter_to_index(col_str: str) -> int:
    """Excel列号字母转数字索引，如 A->1, B->2, Z->26, AA->27"""
    col_str = col_str.strip().upper()
    if not col_str or not col_str[0].isalpha():
        return 0
    result = 0
    for ch in col_str:
        result = result * 26 + (ord(ch) - ord('A') + 1)
    return result


def resolve_col_index(excel_col, header_map):
    """解析Excel列标识为列索引，支持列名或列号(A,B,C...)"""
    # 先尝试列名匹配
    if excel_col in header_map:
        return header_map[excel_col]
    # 检查是否是有效的列字母格式（只包含A-Z，不超过3个字符）
    excel_col_clean = str(excel_col).strip().upper()
    if len(excel_col_clean) > 3:
        return None
    if not all(c.isalpha() for c in excel_col_clean):
        return None
    # 再尝试列号匹配（A->1, B->2...）
    col_idx = col_letter_to_index(excel_col)
    # 检查是否在合理的列索引范围内（1-1000）
    if 0 < col_idx <= 1000:
        return col_idx
    return None


def is_col_letter_mapping(mapping):
    """判断映射是否全部使用列号（A,B,C...）"""
    for key in mapping.keys():
        key = key.strip().upper()
        if not key or not key[0].isalpha():
            return False
        # 如果是纯字母（列号），返回True
        if key.replace(' ', '').isalpha():
            continue
        else:
            return False
    return True


def _is_valid_tracking_number(s):
    """判断是否是有效的快递单号"""
    if not s:
        return False
    s = s.strip()
    # 顺丰：12位纯数字（或以SF开头）
    if re.match(r'^(SF\d{10,15}|\d{12,20})$', s):
        return True
    # 中通、圆通、韵达等：纯数字，通常10-20位
    if re.match(r'^\d{10,20}$', s):
        return True
    # 京东：以JD开头
    if re.match(r'^JD\d+', s):
        return True
    # 包含字母和数字混合（如YT、YZ开头等）
    if re.match(r'^[A-Za-z]{1,4}\d{10,20}$', s):
        return True
    return False


def _find_tracking_from_row(row_data):
    """从行数据所有字段中查找有效的快递单号"""
    for key, value in row_data.items():
        val = str(value).strip()
        if val and _is_valid_tracking_number(val):
            return val
    return ''


@bp.route('/batch_import/execute', methods=['POST'])
@role_required('shipper', 'admin')
def execute_batch_import():
    """执行批量导入"""
    category_id = request.form.get('category_id', type=int)
    file = request.files.get('file')

    if not category_id:
        flash('请选择产品类别！', 'danger')
        return redirect(url_for('import_routes.batch_import_page'))
    if not file or file.filename == '':
        flash('请选择文件！', 'danger')
        return redirect(url_for('import_routes.batch_import_page'))

    template = ImportTemplate.query.filter_by(category_id=category_id).first()
    if not template:
        flash('该类别未配置导入模板！', 'danger')
        return redirect(url_for('import_routes.batch_import_page'))

    mapping = json.loads(template.field_mapping) if template.field_mapping else {}
    if not mapping:
        flash('导入模板未配置字段映射！', 'danger')
        return redirect(url_for('import_routes.batch_import_page'))

    # 读取上传的Excel
    is_xls = file.filename.lower().endswith('.xls')

    try:
        # 判断是否全部使用列号映射（无表头模式）
        no_header = is_col_letter_mapping(mapping)

        if is_xls:
            import xlrd
            wb = xlrd.open_workbook(file_contents=file.read())
            ws = wb.sheet_by_index(0)

            # 建立列名->列号映射
            header_map = {}
            for col in range(ws.ncols):
                cell_value = ws.cell(0, col).value
                if cell_value:
                    header_map[str(cell_value).strip()] = col

            # 读取数据行（列号模式从第1行开始，列名模式从第2行开始）
            start_row = 0 if no_header else 1
            rows_data = []
            for row in range(start_row, ws.nrows):
                row_data = {}
                for excel_col, field in mapping.items():
                    col_idx = resolve_col_index(excel_col, header_map)
                    if col_idx is not None:
                        row_data[field] = ws.cell(row, col_idx).value
                rows_data.append(row_data)
        else:
            import openpyxl
            wb = openpyxl.load_workbook(file)
            ws = wb.active

            # 建立列名->列号映射
            header_map = {}
            for col in range(1, ws.max_column + 1):
                cell_value = ws.cell(row=1, column=col).value
                if cell_value:
                    header_map[str(cell_value).strip()] = col

            # 读取数据行（列号模式从第1行开始，列名模式从第2行开始）
            start_row = 1 if no_header else 2
            rows_data = []
            for row in range(start_row, ws.max_row + 1):
                row_data = {}
                for excel_col, field in mapping.items():
                    col_idx = resolve_col_index(excel_col, header_map)
                    if col_idx:
                        row_data[field] = ws.cell(row=row, column=col_idx).value
                rows_data.append(row_data)

        # 更新订单
        updated_count = 0
        not_found_count = 0
        skipped_count = 0
        category = Category.query.get(category_id)
        default_express = template.default_express_type or ''

        print(f"[DEBUG] 导入模板映射: {mapping}")
        print(f"[DEBUG] Excel表头: {header_map}")
        print(f"[DEBUG] 默认快递种类: {default_express}")
        print(f"[DEBUG] 类别: {category.name}")
        print(f"[DEBUG] 共读取 {len(rows_data)} 行数据")

        for idx, row_data in enumerate(rows_data):
            group_name = str(row_data.get('group_name', '')).strip()
            salesman_name = str(row_data.get('salesman_name', '')).strip()
            customer_name = str(row_data.get('customer_name', '')).strip()
            tracking_number = str(row_data.get('tracking_number', '')).strip()
            express_type = str(row_data.get('express_type', '')).strip()
            new_product_info = str(row_data.get('product_info', '')).strip()  # 托寄物内容

            # 校验快递单号：如果不是有效单号，从该行所有数据中查找
            if tracking_number and not _is_valid_tracking_number(tracking_number):
                found_number = _find_tracking_from_row(row_data)
                if found_number:
                    tracking_number = found_number
                else:
                    tracking_number = ''  # 找不到有效单号则置空

            # 如果Excel中没有快递种类，使用默认值
            if not express_type and default_express:
                express_type = default_express

            # 字段预处理：大写字母、去特殊字符、只保留字母数字汉字
            def normalize_field(s):
                s = s.upper()
                s = re.sub(r'[^\w\u4e00-\u9fff]', '', s)
                return s

            group_name_norm = normalize_field(group_name)
            customer_name_norm = normalize_field(customer_name)

            # 必填字段校验（只有映射中有组别时才要求）
            has_group_in_mapping = 'group_name' in mapping
            has_salesman_in_mapping = 'salesman_name' in mapping

            if has_group_in_mapping and not group_name:
                skipped_count += 1
                continue

            if not tracking_number or tracking_number == '0':
                skipped_count += 1
                continue

            if not customer_name:
                skipped_count += 1
                continue

            # 查找业务员（也做预处理匹配，支持多角色）
            salesman = None
            if salesman_name:
                all_salesmen = User.query.filter(User.roles.like('%salesman%')).all()
                salesman = next((s for s in all_salesmen if normalize_field(s.name) == normalize_field(salesman_name)), None)

            # 如果映射中有业务员字段但找不到，则跳过
            if has_salesman_in_mapping and not salesman:
                skipped_count += 1
                continue

            # 查找匹配的订单
            if has_salesman_in_mapping and salesman:
                # 有业务员字段：按业务员过滤
                all_orders = Order.query.filter_by(
                    category=category.name,
                    salesman_id=salesman.id
                ).all()
            else:
                # 无业务员字段：不用业务员过滤，只按类别匹配
                all_orders = Order.query.filter_by(
                    category=category.name
                ).all()

            # 筛选出客户名匹配的候选订单（组别可选）
            if has_group_in_mapping:
                # 有组别字段：组别+客户名双重匹配
                candidates = [o for o in all_orders
                             if normalize_field(o.group_name) == group_name_norm
                             and normalize_field(o.customer_name) == customer_name_norm]
            else:
                # 无组别字段：只用客户名匹配
                candidates = [o for o in all_orders
                             if normalize_field(o.customer_name) == customer_name_norm]

            if not candidates:
                print(f"[DEBUG]   未找到匹配订单（客户名={customer_name}不匹配）")
                not_found_count += 1
                continue

            # 如果有托寄物内容，用数字匹配筛选
            order = None
            if new_product_info:
                extract_digits = lambda s: ''.join(re.findall(r'\d+', s or ''))
                target_digits = extract_digits(new_product_info)
                if target_digits:
                    # 尝试找数字匹配的订单（包含匹配：订单数字包含Excel数字）
                    for c in candidates:
                        order_digits = extract_digits(c.product_info)
                        # 检查订单数字是否包含Excel数字，或Excel数字是否包含订单数字
                        if target_digits in order_digits or order_digits in target_digits:
                            order = c
                            break

            # 如果没有找到数字匹配的，取第一个候选订单
            if not order and candidates:
                order = candidates[0]
            if order:
                print(f"[DEBUG]   找到订单: id={order.id}, status={order.status}")
                if order.status == 'submitted':
                    order.tracking_number = tracking_number
                    order.express_type = express_type or order.express_type
                    order.status = 'shipped'

                    # 判断是否为主品，非主品发货即签收
                    if category.is_main_product:
                        # 主品：正常发货流程
                        if express_type == '顺丰':
                            order.logistics_status = '已发货'
                    else:
                        # 非主品：发货即签收
                        order.logistics_status = '已签收'
                        print(f"[DEBUG]   非主品类别，直接标记为已签收")

                    updated_count += 1

                    # 通知业务员
                    notify_users([order.salesman_id],
                                f'您的订单 {order.group_name} 已发货，{order.express_type}：{tracking_number}，请注意查收！',
                                order_id=order.id)
                else:
                    print(f"[DEBUG]   订单状态不是待发货，跳过")
                    not_found_count += 1
            else:
                print(f"[DEBUG]   未找到匹配订单")
                not_found_count += 1

        db.session.commit()
        msg = f'批量导入完成，共更新 {updated_count} 条订单！'
        if not_found_count > 0:
            msg += f'（{not_found_count} 条未匹配到订单）'
        if skipped_count > 0:
            msg += f'（{skipped_count} 条因数据不完整已跳过）'
        flash(msg, 'success')

    except Exception as e:
        flash(f'导入失败：{str(e)}', 'danger')

    return redirect(url_for('import_routes.batch_import_page'))


def merge_product_info(original_info, new_info):
    """
    合并托寄物内容：数量累加，产品名称不变
    原格式示例: "康欣胶囊*3+赠品*1" 或 "康欣胶囊3个"
    新格式示例: "康欣胶囊*2"
    结果: "康欣胶囊*5+赠品*1"
    """
    import re

    if not original_info:
        return new_info
    if not new_info:
        return original_info

    # 解析产品信息为字典 {产品名: 数量}
    def parse_product_info(info):
        products = {}
        # 支持多种格式: "产品*数量", "产品数量个", "产品数量盒" 等
        # 按 + 分割
        parts = re.split(r'[+、，,]', info)
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # 尝试匹配 "产品名*数量" 或 "产品名数量单位"
            match = re.match(r'^(.+?)[*×xX](\d+)', part)
            if match:
                name = match.group(1).strip()
                qty = int(match.group(2))
                products[name] = products.get(name, 0) + qty
                continue

            # 尝试匹配 "产品名数量" (如 "康欣胶囊3")
            match = re.match(r'^(.+?)(\d+)(?:个|盒|瓶|袋|件)?$', part)
            if match:
                name = match.group(1).strip()
                qty = int(match.group(2))
                products[name] = products.get(name, 0) + qty
                continue

            # 没有数量的情况，默认为1
            products[part] = products.get(part, 0) + 1

        return products

    # 解析原有和新的产品信息
    original_products = parse_product_info(original_info)
    new_products = parse_product_info(new_info)

    # 合并数量（产品名称不变，数量累加）
    for name, qty in new_products.items():
        if name in original_products:
            original_products[name] += qty
        else:
            original_products[name] = qty

    # 重新组装为字符串
    result_parts = []
    for name, qty in original_products.items():
        result_parts.append(f"{name}*{qty}")

    return '+'.join(result_parts)
