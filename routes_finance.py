# -*- coding: utf-8 -*-
"""财务模块路由（角色：finance 或 admin）"""
import re
import json
from datetime import datetime
from calendar import monthrange

from flask import (
    Blueprint, request, redirect, url_for, flash, render_template,
    send_file, jsonify, abort
)
from flask_login import login_required, current_user

from models import (
    db, Group, User, Order, Category, _now_bj,
    CommissionRule, AttendanceConfig, DingTalkAttendance, SalaryRecord
)
from helpers import role_required, get_unread_count

bp = Blueprint('finance', __name__)


# ============ 工具函数 ============
def _require_finance_access():
    """财务/超级管理员权限校验（返回布尔值）"""
    roles = current_user.get_roles()
    return 'finance' in roles or current_user.username == 'admin'


def _get_accessible_users():
    """获取当前财务人员可管理的用户：
    - admin 可看所有人
    - finance 可看所有业务员
    """
    if 'admin' in current_user.get_roles():
        return User.query.filter_by(is_active=True).all()
    # 财务角色 -> 所有业务员
    users = User.query.filter_by(is_active=True).all()
    return [u for u in users if 'salesman' in u.get_roles()]


def _get_accessible_groups():
    """获取财务可见的组别列表"""
    return Group.query.filter_by(is_active=True).order_by(Group.level.asc(), Group.create_time.asc()).all()


def _calculate_month_performance(user_id, year, month):
    """计算指定用户指定月份的业绩：
    返回 (total_amount, signed_amount, order_count, signed_count)
    """
    # 获取主产品类别
    main_categories = Category.query.filter_by(is_main_product=True, is_active=True).all()
    main_cat_names = {c.name for c in main_categories}

    all_orders = Order.query.filter(
        Order.salesman_id == user_id,
        Order.status.in_(['submitted', 'shipped'])
    ).all()
    signed_orders = Order.query.filter(
        Order.salesman_id == user_id,
        Order.status == 'shipped',
        Order.logistics_status == '已签收'
    ).all()

    def _order_amount(o):
        paid_str = str(o.paid_amount or '')
        paid_num = float(re.match(r'[\d.]+', paid_str).group()) if re.match(r'[\d.]+', paid_str) else 0
        collect_num = float(o.collect_amount or 0)
        return paid_num + collect_num

    def _in_month(o):
        # 按签收时间归属月份；无签收时间按创建时间
        ref = o.sign_time or o.create_time
        if not ref:
            return False
        return ref.year == year and ref.month == month

    total_amount = 0.0
    signed_amount = 0.0
    order_count = 0
    signed_count = 0
    for o in all_orders:
        if (o.category or '未分类') not in main_cat_names:
            continue
        if not _in_month(o):
            continue
        amt = _order_amount(o)
        if amt <= 0:
            continue
        total_amount += amt
        order_count += 1

    for o in signed_orders:
        if (o.category or '未分类') not in main_cat_names:
            continue
        if not _in_month(o):
            continue
        amt = _order_amount(o)
        if amt <= 0:
            continue
        signed_amount += amt
        signed_count += 1

    return round(total_amount, 2), round(signed_amount, 2), order_count, signed_count


# ============ 仪表盘 ============
@bp.route('/finance/dashboard')
@login_required
def finance_dashboard():
    if not _require_finance_access():
        flash('您没有权限访问财务模块！', 'danger')
        return redirect(url_for('auth.index'))

    now = _now_bj()
    year = request.args.get('year', type=int, default=now.year)
    month = request.args.get('month', type=int, default=now.month)

    # 获取可见用户及其组别汇总
    groups = _get_accessible_groups()
    users = _get_accessible_users()

    # 简单汇总
    total_users = len(users)
    total_salary_records = SalaryRecord.query.filter_by(year=year, month=month).count()

    # 全局财务配置（提成+考勤）
    global_cfg = AttendanceConfig.get_global()
    finance_config_saved = global_cfg.id is not None
    applicable_group_ids = set(global_cfg.get_applicable_group_ids()) if finance_config_saved else set()
    # 如果未选择任何组别（空列表），表示适用于所有组
    if finance_config_saved and not applicable_group_ids:
        applicable_group_count = len(groups)
    else:
        applicable_group_count = sum(1 for g in groups if g.id in applicable_group_ids)

    # 考勤数据状态（是否已有本月考勤数据）
    attendance_records = DingTalkAttendance.query.filter(
        db.func.extract('year', DingTalkAttendance.attendance_date) == year,
        db.func.extract('month', DingTalkAttendance.attendance_date) == month
    ).count()

    return render_template(
        'finance_dashboard.html',
        year=year, month=month,
        total_users=total_users,
        total_salary_records=total_salary_records,
        finance_config_saved=finance_config_saved,
        applicable_group_count=applicable_group_count,
        attendance_record_count=attendance_records,
        groups=groups,
        unread_count=get_unread_count(current_user.id)
    )


# ============ 提成规则配置 ============
@bp.route('/finance/commission')
@login_required
def commission_config():
    if not _require_finance_access():
        flash('您没有权限访问财务模块！', 'danger')
        return redirect(url_for('auth.index'))

    groups = _get_accessible_groups()
    # 每个组读取/创建默认规则
    group_rules = []
    for g in groups:
        rule = CommissionRule.get_by_group(g.id)
        if not rule:
            # 创建一个默认规则对象（不入库，便于前端显示配置表单）
            rule = CommissionRule()
            rule.group_id = g.id
            rule.rule_type = 'fixed'
            rule.fixed_rate = 5.0
            rule.tiered_config = None
            rule.id = None
        group_rules.append((g, rule))

    return render_template(
        'finance_commission.html',
        groups=groups,
        group_rules=group_rules,
        unread_count=get_unread_count(current_user.id)
    )


@bp.route('/finance/commission/save', methods=['POST'])
@login_required
def commission_save():
    if not _require_finance_access():
        return jsonify({'success': False, 'error': '没有权限'}), 403

    group_id = request.form.get('group_id', type=int)
    rule_type = request.form.get('rule_type', 'fixed')
    fixed_rate = request.form.get('fixed_rate', type=float, default=5.0)
    remark = request.form.get('remark', '') or ''

    if not group_id:
        flash('请选择组别', 'warning')
        return redirect(url_for('finance.commission_config'))

    # 处理阶梯配置
    tiered_config = None
    if rule_type == 'tiered':
        mins = request.form.getlist('tier_min[]')
        maxs = request.form.getlist('tier_max[]')
        rates = request.form.getlist('tier_rate[]')
        tiers = []
        for i in range(len(mins)):
            try:
                min_a = float(mins[i]) if mins[i] != '' else 0
                max_a = maxs[i] if maxs[i] != '' and maxs[i] is not None else None
                if max_a is not None:
                    max_a = float(max_a)
                rate = float(rates[i]) if rates[i] != '' else 0
                tiers.append({
                    'min_amount': min_a,
                    'max_amount': max_a,
                    'rate': rate
                })
            except (ValueError, TypeError):
                continue
        if not tiers:
            flash('阶梯配置不能为空，请至少配置一档', 'warning')
            return redirect(url_for('finance.commission_config'))
        tiered_config = json.dumps(tiers, ensure_ascii=False)

    # 更新或创建规则
    rule = CommissionRule.get_by_group(group_id)
    is_new = False
    if not rule:
        rule = CommissionRule()
        rule.group_id = group_id
        is_new = True
    rule.rule_type = rule_type
    rule.fixed_rate = fixed_rate
    rule.tiered_config = tiered_config
    rule.remark = remark
    rule.created_by = current_user.id if is_new else rule.created_by

    try:
        if is_new:
            db.session.add(rule)
        db.session.commit()
        flash(f'提成规则已保存', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'保存失败：{str(e)}', 'danger')

    return redirect(url_for('finance.commission_config'))


# ============ 财务配置（考勤 + 提成统一配置）============
@bp.route('/finance/attendance/config')
@login_required
def attendance_config():
    if not _require_finance_access():
        flash('您没有权限访问财务模块！', 'danger')
        return redirect(url_for('auth.index'))

    groups = _get_accessible_groups()
    # 读取全局唯一配置（不存在则返回默认值对象）
    global_cfg = AttendanceConfig.get_global()

    return render_template(
        'finance_attendance.html',
        groups=groups,
        global_cfg=global_cfg,
        unread_count=get_unread_count(current_user.id)
    )


@bp.route('/finance/attendance/config/save', methods=['POST'])
@login_required
def attendance_config_save():
    """保存全局财务配置：基础薪资 + 全勤奖 + 扣款规则 + 提成规则 + 适用组别"""
    if not _require_finance_access():
        flash('您没有权限访问财务模块！', 'danger')
        return redirect(url_for('auth.index'))

    # -------- 适用范围 --------
    applicable_ids_raw = request.form.getlist('applicable_groups[]') or []
    applicable_ids = []
    for x in applicable_ids_raw:
        try:
            applicable_ids.append(int(x))
        except (ValueError, TypeError):
            pass
    applicable_group_ids = json.dumps(applicable_ids, ensure_ascii=False) if applicable_ids else '[]'

    # -------- 基础薪资 & 全勤奖 --------
    base_salary = request.form.get('base_salary', type=float, default=0)
    full_attendance_bonus = request.form.get('full_attendance_bonus', type=float, default=0)

    # -------- 扣款规则 --------
    absence_deduction = request.form.get('absence_deduction', type=float, default=0)
    sick_leave_deduction = request.form.get('sick_leave_deduction', type=float, default=0)
    personal_leave_deduction = request.form.get('personal_leave_deduction', type=float, default=0)
    standard_work_days = request.form.get('standard_work_days', type=int, default=22)
    remark = request.form.get('remark', '') or ''

    # 迟到扣钱档位
    late_mins = request.form.getlist('late_minutes[]')
    late_amounts = request.form.getlist('late_amount[]')
    late_rules = []
    for i in range(len(late_mins)):
        try:
            m = float(late_mins[i]) if late_mins[i] != '' else 0
            a = float(late_amounts[i]) if late_amounts[i] != '' else 0
            if m > 0:
                late_rules.append({'minutes': m, 'amount': a})
        except (ValueError, TypeError):
            continue
    late_rules.sort(key=lambda x: x['minutes'])
    late_deduction_rules = json.dumps(late_rules, ensure_ascii=False) if late_rules else None

    # -------- 提成规则 --------
    commission_rule_type = request.form.get('commission_rule_type', 'fixed') or 'fixed'
    commission_fixed_rate = request.form.get('commission_fixed_rate', type=float, default=5.0)

    # 阶梯
    tier_mins = request.form.getlist('commission_tier_min[]')
    tier_maxs = request.form.getlist('commission_tier_max[]')
    tier_rates = request.form.getlist('commission_tier_rate[]')
    commission_tiers = []
    for i in range(len(tier_mins)):
        try:
            min_a = float(tier_mins[i]) if tier_mins[i] != '' else 0
            max_a = tier_maxs[i] if i < len(tier_maxs) else None
            if max_a == '' or max_a is None:
                max_a_val = None
            else:
                try:
                    max_a_val = float(max_a)
                except (ValueError, TypeError):
                    max_a_val = None
            rate = float(tier_rates[i]) if i < len(tier_rates) and tier_rates[i] != '' else 0
            commission_tiers.append({
                'min_amount': min_a,
                'max_amount': max_a_val,
                'rate': rate
            })
        except (ValueError, TypeError):
            continue
    commission_tiered_config = json.dumps(commission_tiers, ensure_ascii=False) if commission_tiers else None

    # -------- 更新或创建唯一的配置记录 --------
    cfg = AttendanceConfig.query.first()
    is_new = False
    if not cfg:
        cfg = AttendanceConfig()
        is_new = True

    cfg.applicable_group_ids = applicable_group_ids
    cfg.base_salary = base_salary
    cfg.full_attendance_bonus = full_attendance_bonus
    cfg.absence_deduction = absence_deduction
    cfg.sick_leave_deduction = sick_leave_deduction
    cfg.personal_leave_deduction = personal_leave_deduction
    cfg.standard_work_days = standard_work_days
    cfg.remark = remark
    cfg.late_deduction_rules = late_deduction_rules
    cfg.commission_rule_type = commission_rule_type
    cfg.commission_fixed_rate = commission_fixed_rate
    cfg.commission_tiered_config = commission_tiered_config
    cfg.created_by = current_user.id if is_new else cfg.created_by

    try:
        if is_new:
            db.session.add(cfg)
        db.session.commit()
        flash('财务配置已保存', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'保存失败：{str(e)}', 'danger')

    return redirect(url_for('finance.attendance_config'))


# ============ 考勤数据录入/同步 ============
@bp.route('/finance/attendance/data')
@login_required
def attendance_data():
    if not _require_finance_access():
        flash('您没有权限访问财务模块！', 'danger')
        return redirect(url_for('auth.index'))

    now = _now_bj()
    year = request.args.get('year', type=int, default=now.year)
    month = request.args.get('month', type=int, default=now.month)

    users = _get_accessible_users()

    # 每个用户的考勤摘要
    user_stats = []
    for u in users:
        stats = DingTalkAttendance.get_month_stats(u.id, year, month)
        user_stats.append((u, stats))

    return render_template(
        'finance_attendance_data.html',
        year=year, month=month,
        users=users,
        user_stats=user_stats,
        unread_count=get_unread_count(current_user.id)
    )


@bp.route('/finance/attendance/data/add', methods=['POST'])
@login_required
def attendance_data_add():
    if not _require_finance_access():
        flash('您没有权限访问财务模块！', 'danger')
        return redirect(url_for('auth.index'))

    user_id = request.form.get('user_id', type=int)
    date_str = request.form.get('date', '')
    check_type = request.form.get('check_type', 'normal')
    late_minutes = request.form.get('late_minutes', type=int, default=0)
    early_minutes = request.form.get('early_minutes', type=int, default=0)
    leave_days = request.form.get('leave_days', type=float, default=0)
    leave_type = request.form.get('leave_type', '') or ''

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        flash('日期格式无效', 'warning')
        return redirect(url_for('finance.attendance_data'))

    # 已存在则更新
    record = DingTalkAttendance.query.filter_by(user_id=user_id, attendance_date=date_obj).first()
    if not record:
        record = DingTalkAttendance(user_id=user_id, attendance_date=date_obj)
        db.session.add(record)
    record.check_type = check_type
    record.late_minutes = late_minutes
    record.early_minutes = early_minutes
    record.leave_days = leave_days
    record.leave_type = leave_type
    record.source = 'manual'

    db.session.commit()
    flash('考勤记录已保存', 'success')
    return redirect(url_for('finance.attendance_data'))


@bp.route('/finance/attendance/data/delete/<int:rec_id>', methods=['POST'])
@login_required
def attendance_data_delete(rec_id):
    if not _require_finance_access():
        return jsonify({'success': False, 'error': '没有权限'}), 403
    record = DingTalkAttendance.query.get(rec_id)
    if record:
        db.session.delete(record)
        db.session.commit()
        flash('考勤记录已删除', 'success')
    return redirect(url_for('finance.attendance_data'))


@bp.route('/finance/attendance/sync', methods=['POST'])
@login_required
def attendance_sync():
    """从钉钉同步考勤数据（按日期或月份）"""
    if not _require_finance_access():
        flash('您没有权限访问财务模块！', 'danger')
        return redirect(url_for('auth.index'))

    date_str = request.form.get('date', '').strip()
    start_date = request.form.get('start_date', '').strip()
    end_date = request.form.get('end_date', '').strip()

    from services import fetch_dingtalk_attendance_by_date, fetch_dingtalk_attendance_by_range

    try:
        if start_date and end_date:
            res = fetch_dingtalk_attendance_by_range(start_date, end_date)
            if res.get('success'):
                flash(
                    f'批量同步完成：共保存 {res.get("total_saved_records", 0)} 条考勤记录',
                    'success'
                )
            else:
                flash('同步失败：' + res.get('error', '未知错误'), 'danger')
        elif date_str:
            res = fetch_dingtalk_attendance_by_date(date_str)
            if res.get('success'):
                flash(
                    f'已同步 {date_str} 考勤数据：保存 {res.get("saved_records", 0)} 条，覆盖 {res.get("processed_users", 0)} 个用户',
                    'success'
                )
            else:
                flash('同步失败：' + res.get('error', '未知错误'), 'danger')
        else:
            flash('请指定日期或日期范围', 'warning')
    except Exception as e:
        flash('同步过程出错：' + str(e), 'danger')

    return redirect(url_for('finance.attendance_data'))


# ============ 薪资核算 ============
@bp.route('/finance/salary')
@login_required
def salary_calculation():
    if not _require_finance_access():
        flash('您没有权限访问财务模块！', 'danger')
        return redirect(url_for('auth.index'))

    now = _now_bj()
    year = request.args.get('year', type=int, default=now.year)
    month = request.args.get('month', type=int, default=now.month)

    users = _get_accessible_users()

    # 读取所有已核算/未核算的薪资记录
    existing_records = {sr.user_id: sr for sr in SalaryRecord.query.filter_by(year=year, month=month).all()}

    salary_rows = []
    for u in users:
        rec = existing_records.get(u.id)
        if not rec:
            # 未核算 -> 做一个预估（但不入库），仅用于显示
            total_amt, signed_amt, cnt, scnt = _calculate_month_performance(u.id, year, month)
            # 从统一财务配置读取提成规则和考勤配置
            fin_cfg = AttendanceConfig.get_effective(u.group_id)
            not_configured = getattr(fin_cfg, '_not_configured', False)
            commission = 0.0
            summary = '未配置财务规则' if not_configured else (
                f'固定 {fin_cfg.commission_fixed_rate}%' if (fin_cfg.commission_rule_type or '').lower() == 'fixed' else '阶梯比例'
            )
            if not not_configured:
                commission = fin_cfg.calculate_commission(signed_amt)
            # 考勤
            att_stats = DingTalkAttendance.get_month_stats(u.id, year, month)
            base = float(fin_cfg.base_salary or 0)
            full_bonus = float(fin_cfg.full_attendance_bonus or 0) if fin_cfg.is_full_attendance(
                att_stats['absence_days'], att_stats['sick_leave_days'],
                att_stats['personal_leave_days'], att_stats['total_late_minutes']
            ) else 0
            late_ded = fin_cfg.get_late_deduction(att_stats['total_late_minutes'])
            absence_ded = float(fin_cfg.absence_deduction or 0) * float(att_stats['absence_days'] or 0)
            sick_ded = float(fin_cfg.sick_leave_deduction or 0) * float(att_stats['sick_leave_days'] or 0)
            personal_ded = float(fin_cfg.personal_leave_deduction or 0) * float(att_stats['personal_leave_days'] or 0)
            net = round(
                base + full_bonus + commission
                - late_ded - absence_ded - sick_ded - personal_ded, 2
            )

            salary_rows.append({
                'user_id': u.id,
                'user_name': u.name,
                'group_name': u.group.name if u.group else '未分组',
                'base_salary': base,
                'full_attendance_bonus': full_bonus,
                'performance_amount': total_amt,
                'signed_performance_amount': signed_amt,
                'order_count': cnt,
                'commission_amount': commission,
                'commission_rule_summary': summary,
                'attendance_normal_days': att_stats['normal_days'],
                'attendance_late_days': att_stats['late_days'],
                'attendance_absence_days': att_stats['absence_days'],
                'attendance_sick_leave_days': att_stats['sick_leave_days'],
                'attendance_personal_leave_days': att_stats['personal_leave_days'],
                'attendance_total_late_minutes': att_stats['total_late_minutes'],
                'late_deduction': round(late_ded, 2),
                'absence_deduction': round(absence_ded, 2),
                'sick_leave_deduction': round(sick_ded, 2),
                'personal_leave_deduction': round(personal_ded, 2),
                'manual_adjustment': 0,
                'manual_remark': '',
                'net_salary': net,
                'status': 'preview',
                'record_id': None
            })
        else:
            salary_rows.append({
                'user_id': rec.user_id,
                'user_name': rec.user.name,
                'group_name': rec.group.name if rec.group else '未分组',
                'base_salary': float(rec.base_salary or 0),
                'full_attendance_bonus': float(rec.full_attendance_bonus or 0),
                'performance_amount': float(rec.performance_amount or 0),
                'signed_performance_amount': float(rec.signed_performance_amount or 0),
                'order_count': rec.order_count or 0,
                'commission_amount': float(rec.commission_amount or 0),
                'commission_rule_summary': rec.commission_rule_summary or '',
                'attendance_normal_days': rec.attendance_normal_days or 0,
                'attendance_late_days': rec.attendance_late_days or 0,
                'attendance_absence_days': rec.attendance_absence_days or 0,
                'attendance_sick_leave_days': rec.attendance_sick_leave_days or 0,
                'attendance_personal_leave_days': rec.attendance_personal_leave_days or 0,
                'attendance_total_late_minutes': rec.attendance_total_late_minutes or 0,
                'late_deduction': float(rec.late_deduction or 0),
                'absence_deduction': float(rec.absence_deduction or 0),
                'sick_leave_deduction': float(rec.sick_leave_deduction or 0),
                'personal_leave_deduction': float(rec.personal_leave_deduction or 0),
                'manual_adjustment': float(rec.manual_adjustment or 0),
                'manual_remark': rec.manual_remark or '',
                'net_salary': float(rec.net_salary or 0),
                'status': rec.status,
                'record_id': rec.id
            })

    # 汇总
    grand_total = sum(r['net_salary'] for r in salary_rows)
    total_commission = sum(r['commission_amount'] for r in salary_rows)
    total_performance = sum(r['performance_amount'] for r in salary_rows)

    return render_template(
        'finance_salary.html',
        year=year, month=month,
        salary_rows=salary_rows,
        grand_total=round(grand_total, 2),
        total_commission=round(total_commission, 2),
        total_performance=round(total_performance, 2),
        unread_count=get_unread_count(current_user.id)
    )


@bp.route('/finance/salary/calculate_all', methods=['POST'])
@login_required
def salary_calculate_all():
    if not _require_finance_access():
        flash('您没有权限访问财务模块！', 'danger')
        return redirect(url_for('auth.index'))

    year = request.form.get('year', type=int)
    month = request.form.get('month', type=int)
    if not year or not month:
        flash('请指定月份', 'warning')
        return redirect(url_for('finance.salary_calculation'))

    users = _get_accessible_users()
    created_count = 0
    updated_count = 0

    for u in users:
        total_amt, signed_amt, cnt, scnt = _calculate_month_performance(u.id, year, month)
        # 从统一财务配置读取
        fin_cfg = AttendanceConfig.get_effective(u.group_id)
        not_configured = getattr(fin_cfg, '_not_configured', False)
        commission = 0.0
        summary = '未配置财务规则' if not_configured else (
            f'固定 {fin_cfg.commission_fixed_rate}%' if (fin_cfg.commission_rule_type or '').lower() == 'fixed' else '阶梯比例'
        )
        if not not_configured:
            commission = fin_cfg.calculate_commission(signed_amt)

        # 考勤
        att_stats = DingTalkAttendance.get_month_stats(u.id, year, month)
        base = float(fin_cfg.base_salary or 0)
        full_bonus = float(fin_cfg.full_attendance_bonus or 0) if fin_cfg.is_full_attendance(
            att_stats['absence_days'], att_stats['sick_leave_days'],
            att_stats['personal_leave_days'], att_stats['total_late_minutes']
        ) else 0
        late_ded = fin_cfg.get_late_deduction(att_stats['total_late_minutes'])
        absence_ded = float(fin_cfg.absence_deduction or 0) * float(att_stats['absence_days'] or 0)
        sick_ded = float(fin_cfg.sick_leave_deduction or 0) * float(att_stats['sick_leave_days'] or 0)
        personal_ded = float(fin_cfg.personal_leave_deduction or 0) * float(att_stats['personal_leave_days'] or 0)

        # 更新或创建薪资记录
        rec = SalaryRecord.query.filter_by(user_id=u.id, year=year, month=month).first()
        if not rec:
            rec = SalaryRecord(user_id=u.id, year=year, month=month)
            rec.group_id = u.group_id
            db.session.add(rec)
            created_count += 1
        else:
            updated_count += 1
            rec.group_id = u.group_id

        rec.base_salary = base
        rec.full_attendance_bonus = full_bonus
        rec.performance_amount = total_amt
        rec.signed_performance_amount = signed_amt
        rec.order_count = cnt
        rec.commission_amount = commission
        rec.commission_rule_summary = summary
        rec.attendance_normal_days = att_stats['normal_days']
        rec.attendance_late_days = att_stats['late_days']
        rec.attendance_absence_days = att_stats['absence_days']
        rec.attendance_sick_leave_days = att_stats['sick_leave_days']
        rec.attendance_personal_leave_days = att_stats['personal_leave_days']
        rec.attendance_total_late_minutes = att_stats['total_late_minutes']
        rec.late_deduction = round(late_ded, 2)
        rec.absence_deduction = round(absence_ded, 2)
        rec.sick_leave_deduction = round(sick_ded, 2)
        rec.personal_leave_deduction = round(personal_ded, 2)
        rec.status = 'draft'
        rec.calculated_by = current_user.id
        rec.recalculate_net()

    db.session.commit()
    flash(f'薪资核算完成：新增 {created_count} 条，更新 {updated_count} 条', 'success')
    return redirect(url_for('finance.salary_calculation', year=year, month=month))


@bp.route('/finance/salary/update/<int:record_id>', methods=['POST'])
@login_required
def salary_update(record_id):
    if not _require_finance_access():
        flash('您没有权限访问财务模块！', 'danger')
        return redirect(url_for('auth.index'))

    rec = SalaryRecord.query.get(record_id)
    if not rec:
        flash('记录不存在', 'warning')
        return redirect(url_for('finance.salary_calculation'))

    # 只允许手动调整和状态更新
    manual_adj = request.form.get('manual_adjustment', type=float, default=0)
    manual_remark = request.form.get('manual_remark', '') or ''
    status = request.form.get('status', rec.status)

    rec.manual_adjustment = manual_adj
    rec.manual_remark = manual_remark
    rec.status = status
    rec.calculated_by = current_user.id
    rec.recalculate_net()
    db.session.commit()

    flash('薪资记录已更新', 'success')
    return redirect(url_for('finance.salary_calculation', year=rec.year, month=rec.month))


@bp.route('/finance/salary/export')
@login_required
def salary_export():
    if not _require_finance_access():
        flash('您没有权限访问财务模块！', 'danger')
        return redirect(url_for('auth.index'))

    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    if not year or not month:
        flash('请指定月份', 'warning')
        return redirect(url_for('finance.salary_calculation'))

    records = SalaryRecord.query.filter_by(year=year, month=month).all()
    if not records:
        flash('没有可导出的薪资记录，请先核算', 'warning')
        return redirect(url_for('finance.salary_calculation', year=year, month=month))

    import io
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = f'{year}年{month}月薪资'

    headers = [
        '姓名', '组别', '基础薪资', '全勤奖',
        '总业绩', '已签收业绩', '订单数', '提成金额', '提成规则',
        '正常出勤', '迟到天数', '累计迟到分钟', '缺旷天数', '病假天数', '事假天数',
        '迟到扣款', '缺旷扣款', '病假扣款', '事假扣款',
        '手动调整', '调整备注', '实发合计', '状态'
    ]
    ws.append(headers)

    for r in records:
        ws.append([
            r.user.name if r.user else '',
            r.group.name if r.group else '未分组',
            float(r.base_salary or 0),
            float(r.full_attendance_bonus or 0),
            float(r.performance_amount or 0),
            float(r.signed_performance_amount or 0),
            r.order_count or 0,
            float(r.commission_amount or 0),
            r.commission_rule_summary or '',
            r.attendance_normal_days or 0,
            r.attendance_late_days or 0,
            r.attendance_total_late_minutes or 0,
            r.attendance_absence_days or 0,
            r.attendance_sick_leave_days or 0,
            r.attendance_personal_leave_days or 0,
            float(r.late_deduction or 0),
            float(r.absence_deduction or 0),
            float(r.sick_leave_deduction or 0),
            float(r.personal_leave_deduction or 0),
            float(r.manual_adjustment or 0),
            r.manual_remark or '',
            float(r.net_salary or 0),
            r.status or ''
        ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(
        output, as_attachment=True,
        download_name=f'薪资表_{year}年{month}月.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
