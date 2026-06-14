# -*- coding: utf-8 -*-
"""黑名单管理路由（支持手机号 + 地址）"""
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import login_required, current_user
import openpyxl
import re

from models import db, BlacklistedPhone
from helpers import role_required, get_unread_count

bp = Blueprint('blacklist', __name__)


# ---------- 工具 ----------
def _clean_phone(raw):
    return re.sub(r'[-\s]', '', raw or '')


def _validate_phone(phone):
    return bool(re.match(r'^1[3-9]\d{9}$', phone or ''))


# ---------- 列表页 ----------
@bp.route('/admin/blacklist')
@role_required('admin')
def admin_blacklist():
    """黑名单管理页面（支持手机/地址切换）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    keyword = request.args.get('keyword', '').strip()
    entry_type = request.args.get('type', '').strip()  # phone | address | 空=全部

    valid_per_page = [20, 100, 1000]
    if per_page not in valid_per_page:
        per_page = 20

    query = BlacklistedPhone.query

    if entry_type in ('phone', 'address'):
        query = query.filter_by(entry_type=entry_type)

    if keyword:
        # 关键词同时匹配手机号 / 地址 / 原因
        like = f'%{keyword}%'
        query = query.filter(
            db.or_(
                BlacklistedPhone.phone.like(like),
                BlacklistedPhone.address.like(like),
                BlacklistedPhone.reason.like(like),
            )
        )

    items = query.order_by(BlacklistedPhone.create_time.desc()).paginate(page=page, per_page=per_page)

    return render_template('admin_blacklist.html',
                           phones=items,
                           keyword=keyword,
                           per_page=per_page,
                           entry_type=entry_type,
                           unread_count=get_unread_count(current_user.id))


# ---------- 新增 ----------
@bp.route('/admin/blacklist/add', methods=['POST'])
@role_required('admin')
def add_blacklisted_phone():
    """添加黑名单（手机号或地址二选一）"""
    entry_type = request.form.get('entry_type', 'phone').strip() or 'phone'
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    reason = request.form.get('reason', '').strip()

    if entry_type == 'phone':
        if not phone:
            flash('请输入手机号！', 'danger')
            return redirect(url_for('blacklist.admin_blacklist'))
        phone = _clean_phone(phone)
        if not _validate_phone(phone):
            flash('请输入正确的11位手机号！', 'danger')
            return redirect(url_for('blacklist.admin_blacklist'))
        # 手机号唯一检查
        if BlacklistedPhone.query.filter_by(phone=phone, entry_type='phone').first():
            flash(f'手机号 {phone} 已在黑名单中！', 'warning')
            return redirect(url_for('blacklist.admin_blacklist'))
        entry = BlacklistedPhone(entry_type='phone', phone=phone, reason=reason, created_by=current_user.id)
        db.session.add(entry)
        db.session.commit()
        flash(f'手机号 {phone} 已添加到黑名单！', 'success')
    else:
        if not address or len(address.strip()) < 10:
            flash('地址长度不足10个字符！', 'danger')
            return redirect(url_for('blacklist.admin_blacklist'))
        # 地址去重：归一化后写入 normalized_address，依赖数据库唯一约束去重
        norm = BlacklistedPhone.normalize_address(address)
        if not norm:
            flash('地址格式无效！', 'danger')
            return redirect(url_for('blacklist.admin_blacklist'))
        entry = BlacklistedPhone(
            entry_type='address',
            address=address,
            normalized_address=norm,
            reason=reason,
            created_by=current_user.id
        )
        db.session.add(entry)
        try:
            db.session.commit()
            flash('该地址已添加到黑名单！', 'success')
        except Exception as e:
            db.session.rollback()
            if 'Duplicate entry' in str(e):
                flash('该地址已在黑名单中！', 'warning')
            else:
                flash(f'添加失败：{str(e)}', 'danger')

    return redirect(url_for('blacklist.admin_blacklist'))


# ---------- 修改 ----------
@bp.route('/admin/blacklist/update/<int:id>', methods=['POST'])
@role_required('admin')
def update_blacklisted_phone(id):
    """更新黑名单记录"""
    entry = BlacklistedPhone.query.get_or_404(id)
    reason = request.form.get('reason', '').strip()
    # 支持修改地址内容（手机号保持唯一，不允许改）
    if entry.entry_type == 'address':
        new_address = request.form.get('address', '').strip()
        if new_address:
            entry.address = new_address
    entry.reason = reason
    db.session.commit()
    flash('黑名单记录已更新！', 'success')
    return redirect(url_for('blacklist.admin_blacklist'))


# ---------- 删除 ----------
@bp.route('/admin/blacklist/delete/<int:id>', methods=['POST'])
@role_required('admin')
def delete_blacklisted_phone(id):
    """删除黑名单记录"""
    entry = BlacklistedPhone.query.get_or_404(id)
    label = entry.phone if entry.entry_type == 'phone' else (entry.address or '')[:30]
    db.session.delete(entry)
    db.session.commit()
    flash(f'记录【{label}】已从黑名单中移除！', 'success')
    return redirect(url_for('blacklist.admin_blacklist'))


# ---------- 批量导入 ----------
@bp.route('/admin/blacklist/import', methods=['POST'])
@role_required('admin')
def import_blacklisted_phones():
    """批量导入黑名单
    Excel 列结构（从第二行开始读取）：
        列1：类型（phone/address，留空默认phone）
        列2：手机号 或 地址
        列3：原因
    若只有一列手机号也能识别，保持向后兼容。
    """
    if 'file' not in request.files:
        flash('请选择要导入的文件！', 'danger')
        return redirect(url_for('blacklist.admin_blacklist'))

    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        flash('只支持Excel文件（.xlsx/.xls）！', 'danger')
        return redirect(url_for('blacklist.admin_blacklist'))

    try:
        wb = openpyxl.load_workbook(file)
        ws = wb.active

        phone_reason_map = {}   # phone -> reason
        address_reason_map = {}  # normalized_address -> (original_address, reason)
        failed_count = 0

        for row in ws.iter_rows(min_row=2):
            cells = [c.value for c in row]
            while len(cells) < 3:
                cells.append(None)

            col1_raw = str(cells[0]).strip() if cells[0] is not None else ''
            col2_raw = str(cells[1]).strip() if cells[1] is not None else ''
            col3_raw = str(cells[2]).strip() if cells[2] is not None else ''

            # 判断是老格式（只有手机号）还是新格式
            if col1_raw and col1_raw.lower() in ('phone', '手机号', '电话', '手机'):
                entry_type = 'phone'
                value = col2_raw
                reason = col3_raw
            elif col1_raw and col1_raw.lower() in ('address', 'addr', '地址'):
                entry_type = 'address'
                value = col2_raw
                reason = col3_raw
            elif _validate_phone(_clean_phone(col1_raw)):
                # 老格式：第一列就是手机号
                entry_type = 'phone'
                value = col1_raw
                reason = col2_raw
            else:
                entry_type = 'address'
                value = col1_raw
                reason = col2_raw or col3_raw

            if not value:
                continue

            if entry_type == 'phone':
                phone = _clean_phone(value)
                if not _validate_phone(phone):
                    failed_count += 1
                    continue
                phone_reason_map[phone] = reason or ''
            else:
                if not value or len(value.strip()) < 10:
                    failed_count += 1
                    continue
                norm = BlacklistedPhone.normalize_address(value)
                if not norm:
                    failed_count += 1
                    continue
                # 用归一化地址作为 key 去重
                address_reason_map[norm] = (value, reason or '')

        # === 批量查重 ===
        existed_phone_set = set()
        if phone_reason_map:
            existed = BlacklistedPhone.query.filter(
                BlacklistedPhone.phone.in_(list(phone_reason_map.keys())),
                BlacklistedPhone.entry_type == 'phone'
            ).with_entities(BlacklistedPhone.phone).all()
            existed_phone_set = {r.phone for r in existed}

        # 地址去重：用 normalized_address 查询
        existed_address_norm_set = set()
        if address_reason_map:
            existed = BlacklistedPhone.query.filter(
                BlacklistedPhone.normalized_address.in_(list(address_reason_map.keys())),
                BlacklistedPhone.entry_type == 'address'
            ).with_entities(BlacklistedPhone.normalized_address).all()
            existed_address_norm_set = {r.normalized_address for r in existed}

        # === 批量构建新增对象 ===
        new_records = []
        for phone, reason in phone_reason_map.items():
            if phone in existed_phone_set:
                continue
            new_records.append(BlacklistedPhone(
                entry_type='phone',
                phone=phone,
                reason=reason,
                created_by=current_user.id
            ))
        for norm, (original, reason) in address_reason_map.items():
            if norm in existed_address_norm_set:
                continue
            new_records.append(BlacklistedPhone(
                entry_type='address',
                address=original,
                normalized_address=norm,
                reason=reason,
                created_by=current_user.id
            ))

        success_count = 0
        if new_records:
            db.session.bulk_save_objects(new_records)
            db.session.commit()
            success_count = len(new_records)

        existed_count = len(existed_phone_set) + len(existed_address_norm_set)

        message = f'导入完成！成功添加 {success_count} 条记录'
        if existed_count > 0:
            message += f'，{existed_count} 条已存在跳过'
        if failed_count > 0:
            message += f'，{failed_count} 条格式错误跳过'
        flash(message, 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'导入失败：{str(e)}', 'danger')

    return redirect(url_for('blacklist.admin_blacklist'))


# ---------- 综合检测 API ----------
@bp.route('/api/check_blacklist', methods=['GET', 'POST'])
@login_required
def api_check_blacklist():
    """综合检测：同时检查手机号和地址（地址做相似度匹配）
    支持 GET: ?phone=xxx&address=xxx
    支持 POST JSON: {"phone":"xxx","address":"xxx"}
    """
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        phone = (data.get('phone') or '').strip()
        address = (data.get('address') or '').strip()
    else:
        phone = request.args.get('phone', '').strip()
        address = request.args.get('address', '').strip()

    phone_clean = _clean_phone(phone)

    result = BlacklistedPhone.check_blacklist(
        phone=phone_clean or None,
        address=address or None,
        address_threshold=0.75
    )

    phone_hit = result['phone_hit']
    address_hits = result['address_hits']

    response = {
        'phone_hit': None,
        'address_hits': [],
        'has_hit': False,
        'address_warn': None,  # 部分匹配警告（<100%）
    }

    if phone_hit:
        response['phone_hit'] = {
            'phone': phone_hit.phone,
            'reason': phone_hit.reason or '未说明原因',
            'create_time': phone_hit.create_time.strftime('%Y-%m-%d %H:%M') if phone_hit.create_time else ''
        }
        response['has_hit'] = True

    if address_hits:
        entry, sim = address_hits[0]
        if sim >= 1.0:
            # 100%匹配，算命中
            response['address_hits'] = [
                {
                    'address': entry.address,
                    'reason': entry.reason or '未说明原因',
                    'similarity': round(sim, 3),
                    'create_time': entry.create_time.strftime('%Y-%m-%d %H:%M') if entry.create_time else ''
                }
            ]
            response['has_hit'] = True
        else:
            # 部分匹配，算警告
            response['address_warn'] = {
                'address': entry.address,
                'reason': entry.reason or '未说明原因',
                'similarity': round(sim, 3),
                'create_time': entry.create_time.strftime('%Y-%m-%d %H:%M') if entry.create_time else ''
            }

    return jsonify(response)


# ---------- 批量删除 ----------
@bp.route('/admin/blacklist/batch_delete', methods=['POST'])
@role_required('admin')
def batch_delete_blacklisted_phones():
    """批量删除黑名单记录"""
    ids = request.form.getlist('ids[]')

    if not ids:
        flash('请选择要删除的记录！', 'danger')
        return redirect(url_for('blacklist.admin_blacklist'))

    for id_str in ids:
        try:
            entry = BlacklistedPhone.query.get(int(id_str))
            if entry:
                db.session.delete(entry)
        except Exception:
            pass

    db.session.commit()
    flash(f'已删除 {len(ids)} 条记录！', 'success')
    return redirect(url_for('blacklist.admin_blacklist'))
