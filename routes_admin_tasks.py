# -*- coding: utf-8 -*-
"""定时任务管理路由（管理员可见）"""
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import current_user, login_required

from models import db, ScheduledTask, ScheduledTaskLog, _now_bj
from helpers import role_required, get_unread_count

bp = Blueprint('admin_tasks', __name__)

# 任务注册表：task_key -> {name, description, trigger_type, default_config, func}
# 新增定时任务时，只需在此注册，并在 services.py 中实现对应函数即可
_TASK_REGISTRY = {}


def register_task(task_key, name, description, trigger_type='interval',
                  default_interval_hours=6, default_cron_time='01:00'):
    """注册一个定时任务（供 app.py 启动时调用）"""
    _TASK_REGISTRY[task_key] = {
        'name': name,
        'description': description,
        'trigger_type': trigger_type,
        'default_interval_hours': default_interval_hours,
        'default_cron_time': default_cron_time,
    }


def get_task_registry():
    return _TASK_REGISTRY


def sync_task_config_to_db():
    """启动时同步任务注册表到数据库（不存在则创建）"""
    for task_key, cfg in _TASK_REGISTRY.items():
        existing = ScheduledTask.query.filter_by(task_key=task_key).first()
        if not existing:
            new_task = ScheduledTask(
                task_key=task_key,
                name=cfg['name'],
                description=cfg['description'],
                trigger_type=cfg['trigger_type'],
                interval_hours=cfg['default_interval_hours'],
                cron_time=cfg['default_cron_time'],
                is_enabled=True,
            )
            db.session.add(new_task)
            print(f'[定时任务] 新增任务配置: {task_key}')
    db.session.commit()


# ============ 任务列表页面 ============
@bp.route('/admin/tasks')
@role_required('admin')
def admin_tasks():
    page = request.args.get('page', 1, type=int)
    per_page = 20

    tasks = ScheduledTask.query.order_by(ScheduledTask.id.asc()).all()

    # 读取最近执行日志（每个任务最近3条）
    recent_logs = {}
    for task in tasks:
        logs = (ScheduledTaskLog.query
                .filter_by(task_id=task.id)
                .order_by(ScheduledTaskLog.run_time.desc())
                .limit(3)
                .all())
        recent_logs[task.id] = logs

    return render_template(
        'admin_scheduled_tasks.html',
        tasks=tasks,
        recent_logs=recent_logs,
        unread_count=get_unread_count(current_user.id),
        now_bj=_now_bj(),
    )


# ============ 更新任务配置 ============
@bp.route('/admin/tasks/<int:task_id>/config', methods=['POST'])
@role_required('admin')
def update_task_config(task_id):
    task = ScheduledTask.query.get_or_404(task_id)

    trigger_type = request.form.get('trigger_type', task.trigger_type)
    task.trigger_type = trigger_type

    if trigger_type == 'interval':
        interval_hours = request.form.get('interval_hours', type=int)
        if interval_hours is None or interval_hours < 1 or interval_hours > 168:
            flash('间隔小时数必须在 1-168 之间', 'danger')
            return redirect(url_for('admin_tasks.admin_tasks'))
        task.interval_hours = interval_hours
    elif trigger_type == 'cron':
        cron_time = request.form.get('cron_time', '').strip()
        # 校验 HH:MM 格式
        import re
        if not re.match(r'^\d{1,2}:\d{2}$', cron_time):
            flash('执行时间格式不正确，请使用 HH:MM（例如 01:00）', 'danger')
            return redirect(url_for('admin_tasks.admin_tasks'))
        h, m = cron_time.split(':')
        if int(h) > 23 or int(m) > 59:
            flash('执行时间超出范围', 'danger')
            return redirect(url_for('admin_tasks.admin_tasks'))
        task.cron_time = f'{int(h):02d}:{int(m):02d}'

    db.session.commit()

    # 通知调度器重新加载（通过修改记录的 update_time 让调度器下次 tick 时检测）
    flash(f'任务「{task.name}」配置已更新，将按新设置执行', 'success')
    return redirect(url_for('admin_tasks.admin_tasks'))


# ============ 启停任务 ============
@bp.route('/admin/tasks/<int:task_id>/toggle', methods=['POST'])
@role_required('admin')
def toggle_task(task_id):
    task = ScheduledTask.query.get_or_404(task_id)
    task.is_enabled = not task.is_enabled
    db.session.commit()
    status_txt = '已启用' if task.is_enabled else '已停用'
    flash(f'任务「{task.name}」{status_txt}', 'success')
    return redirect(url_for('admin_tasks.admin_tasks'))


# ============ 立即执行 ============
@bp.route('/admin/tasks/<int:task_id>/run', methods=['POST'])
@role_required('admin')
def run_task_now(task_id):
    task = ScheduledTask.query.get_or_404(task_id)

    # 通过统一入口执行（避免重复代码）
    from services import run_scheduled_task_by_key
    result = run_scheduled_task_by_key(task.task_key)

    # 记录一次手动执行日志
    log = ScheduledTaskLog(
        task_id=task.id,
        run_time=_now_bj(),
        duration_seconds=result.get('duration', 0),
        status=result.get('status', 'success'),
        message=f"[手动执行] {result.get('message', '')}",
    )
    db.session.add(log)
    task.last_run_time = log.run_time
    task.last_run_status = log.status
    task.last_run_message = result.get('message', '')
    db.session.commit()

    if result.get('status') == 'success':
        flash(f'任务「{task.name}」执行成功：{result.get("message", "")}', 'success')
    else:
        flash(f'任务「{task.name}」执行失败：{result.get("message", "")}', 'danger')

    return redirect(url_for('admin_tasks.admin_tasks'))


# ============ 执行日志（只读） ============
@bp.route('/admin/tasks/<int:task_id>/logs')
@role_required('admin')
def task_logs(task_id):
    task = ScheduledTask.query.get_or_404(task_id)
    page = request.args.get('page', 1, type=int)
    logs_query = (ScheduledTaskLog.query
                  .filter_by(task_id=task.id)
                  .order_by(ScheduledTaskLog.run_time.desc()))
    pagination = logs_query.paginate(page=page, per_page=20, error_out=False)
    return render_template(
        'admin_scheduled_task_logs.html',
        task=task,
        logs=pagination.items,
        pagination=pagination,
        unread_count=get_unread_count(current_user.id),
    )
