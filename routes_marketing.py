# -*- coding: utf-8 -*-
"""营销模块路由"""
import base64
import re
import uuid
from io import BytesIO
from PIL import Image
from datetime import datetime, timedelta, date

from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import current_user, login_required

from models import (
    db, Group, User, MarketingPeriod, MarketingSchedule,
    MarketingExecution, _now_bj, _date_bj
)
from helpers import role_required, get_unread_count


bp = Blueprint('marketing', __name__)

UPLOAD_FOLDER = 'static/marketing_images'
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}


def _wants_json():
    """客户端是否期待 JSON 响应（AJAX）"""
    accept = request.headers.get('Accept', '')
    return ('application/json' in accept) or request.is_json or \
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'


# ============================================================
# 辅助函数
# ============================================================

def can_manage_marketing(group_id):
    """判断当前用户是否有权管理/编辑指定组的营销

    规则（管理员才能编辑）：
      - 全局 admin 可管理所有组
      - 其他组普通成员（业务员）不可编辑，只能执行
    """
    if not current_user.is_authenticated:
        return False
    if current_user.has_role('admin'):
        return True
    return False


def can_access_group(group_id):
    """判断当前用户是否有权访问指定组的营销内容（可读+执行）

    规则：
      - 全局 admin 可访问所有组
      - 组内成员（业务员）可访问本组
    """
    if not current_user.is_authenticated:
        return False
    if current_user.has_role('admin'):
        return True
    if current_user.group_id and current_user.group_id == group_id:
        return True
    return False


def get_managed_groups():
    """获取当前用户可访问的组列表（admin=全部，业务员=自己所在组）"""
    if current_user.has_role('admin'):
        return Group.query.filter_by(is_active=True).order_by(Group.level, Group.name).all()
    if current_user.group_id:
        grp = Group.query.get(current_user.group_id)
        return [grp] if grp and grp.is_active else []
    return []


def parse_date(s, default=None):
    """解析 YYYY-MM-DD"""
    if not s:
        return default
    try:
        return datetime.strptime(s.strip(), '%Y-%m-%d').date()
    except ValueError:
        return default


def save_upload_image(file_storage):
    """保存上传的图片，返回 URL；未上传返回 None"""
    if not file_storage or not file_storage.filename:
        return None
    fname = file_storage.filename
    ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
    if ext not in ALLOWED_EXT:
        return None
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    # 用时间戳+随机避免重名
    token = int(_now_bj().timestamp() * 1000)
    new_name = f'{token}_{abs(hash(fname)) % 100000}.{ext}'
    full_path = os.path.join(UPLOAD_FOLDER, new_name)
    file_storage.save(full_path)
    return f'/{UPLOAD_FOLDER}/{new_name}'


def process_html_images(html_content):
    """将 HTML 中的 base64 图片转换为静态文件，返回清理后的 HTML"""
    if not html_content or '<img' not in html_content:
        return html_content

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    def replace_base64_img(match):
        img_tag = match.group(0)
        # 提取 src 属性中的 base64 数据
        src_match = re.search(r'src=["\'](data:image/([^;]+);base64,([^"\'>]+))["\']', img_tag)
        if not src_match:
            return img_tag
        mime_type = src_match.group(2)  # 如 "png", "jpeg"
        b64_data = src_match.group(3)
        try:
            img_bytes = base64.b64decode(b64_data)
            # 生成文件名
            token = int(_now_bj().timestamp() * 1000)
            ext = 'png' if mime_type == 'png' else 'jpg'
            new_name = f'rich_{token}_{uuid.uuid4().hex[:8]}.{ext}'
            full_path = os.path.join(UPLOAD_FOLDER, new_name)
            with open(full_path, 'wb') as f:
                f.write(img_bytes)
            static_url = f'/{UPLOAD_FOLDER}/{new_name}'
            # 替换 src
            return img_tag.replace(src_match.group(1), static_url)
        except Exception:
            return img_tag  # 解析失败保留原样

    # 替换所有 <img src="data:image/...;base64,..."> 为静态 URL
    cleaned = re.sub(r'<img[^>]+>', replace_base64_img, html_content)
    return cleaned


# ============================================================
# 1. 营销总览（含日历视图）
# ============================================================

@bp.route('/marketing', methods=['GET'])
@login_required
def index():
    """营销总览 - 周日历视图 + 当前进行中的栏目"""
    groups = get_managed_groups()
    today = _date_bj()
    view_year = today.year
    view_month = today.month

    # 生成1周日历：往前3天 + 今天 + 往后3天
    calendar_days = []
    for offset in range(-3, 4):
        day = today + timedelta(days=offset)
        day_periods = []
        for g in groups:
            for p in g.marketing_periods:
                if p.start_date <= day <= p.end_date:
                    day_periods.append(p)
        calendar_days.append({
            'date': day,
            'is_today': (day == today),
            'is_current_month': (day.month == today.month),
            'periods': day_periods,
        })

    # 每个组的进行中栏目
    group_active = []
    for g in groups:
        active = next(
            (p for p in g.marketing_periods
             if p.status == 'active' and p.start_date <= today <= (p.end_date or today)),
            None
        )
        # 获取进行中栏目的当天话术（按时间点排序）
        today_schedules = []
        if active:
            today_schedules = MarketingSchedule.query.filter_by(
                period_id=active.id, schedule_date=today
            ).order_by(MarketingSchedule.time_point).all()

        # 今日执行统计
        exec_count = 0
        if active:
            exec_count = MarketingExecution.query.filter_by(
                period_id=active.id
            ).filter(
                db.func.date(MarketingExecution.executed_at) == today
            ).count()

        group_active.append({
            'group': g,
            'active': active,
            'today_schedules': today_schedules,
            'today_exec_count': exec_count,
        })

    return render_template(
        'marketing_index.html',
        groups=groups,
        group_active=group_active,
        calendar_days=calendar_days,
        view_year=view_year,
        view_month=view_month,
        today=today,
        is_admin=current_user.has_role('admin'),
        unread_count=get_unread_count(current_user.id),
    )


# ============================================================
# 2. 组的营销栏目列表
# ============================================================

@bp.route('/marketing/group/<int:group_id>', methods=['GET'])
@login_required
def group_periods(group_id):
    """某个组的栏目列表（管理员可管理，业务员可读）"""
    if not can_access_group(group_id):
        flash('没有权限访问该组的营销内容', 'danger')
        return redirect(url_for('marketing.index'))

    group = Group.query.get_or_404(group_id)
    today = _date_bj()

    periods = MarketingPeriod.query.filter_by(group_id=group_id).order_by(
        MarketingPeriod.start_date.desc(), MarketingPeriod.id.desc()
    ).all()

    # 标注每个栏目的状态
    for p in periods:
        if p.status == 'ended':
            p._ui_status = 'ended'
        elif p.start_date <= today <= (p.end_date or today):
            p._ui_status = 'active'
        elif today < p.start_date:
            p._ui_status = 'upcoming'
        else:
            p._ui_status = 'ended'

    return render_template(
        'marketing_group_periods.html',
        group=group,
        periods=periods,
        today=today,
        can_manage=can_manage_marketing(group_id),
        unread_count=get_unread_count(current_user.id),
    )


# ============================================================
# 3. 新增/编辑栏目
# ============================================================

@bp.route('/marketing/group/<int:group_id>/period/add', methods=['GET', 'POST'])
@login_required
def period_add(group_id):
    """新增栏目"""
    if not can_manage_marketing(group_id):
        flash('没有权限', 'danger')
        return redirect(url_for('marketing.index'))

    group = Group.query.get_or_404(group_id)

    if request.method == 'POST':
        name = request.form.get('period_name', '').strip()
        desc = request.form.get('description', '').strip()
        start = parse_date(request.form.get('start_date'))
        end = parse_date(request.form.get('end_date'))
        status = request.form.get('status', 'active')

        if not name or not start or not end:
            flash('请填写完整的栏目名称和起止日期', 'danger')
        elif end < start:
            flash('结束日期不能早于开始日期', 'danger')
        else:
            period = MarketingPeriod(
                group_id=group_id,
                period_name=name,
                description=desc,
                start_date=start,
                end_date=end,
                status=status,
                created_by=current_user.id,
            )
            db.session.add(period)
            db.session.commit()
            flash(f'栏目"{name}"创建成功，请继续添加话术', 'success')
            return redirect(url_for('marketing.period_schedules', period_id=period.id))

    today = _date_bj()
    default_start = today
    default_end = today + timedelta(days=7)

    return render_template(
        'marketing_period_form.html',
        group=group,
        period=None,
        default_start=default_start,
        default_end=default_end,
        unread_count=get_unread_count(current_user.id),
    )


@bp.route('/marketing/period/<int:period_id>/edit', methods=['GET', 'POST'])
@login_required
def period_edit(period_id):
    """编辑栏目"""
    period = MarketingPeriod.query.get_or_404(period_id)
    if not can_manage_marketing(period.group_id):
        flash('没有权限', 'danger')
        return redirect(url_for('marketing.index'))

    if request.method == 'POST':
        period.period_name = request.form.get('period_name', '').strip() or period.period_name
        period.description = request.form.get('description', '').strip()
        start = parse_date(request.form.get('start_date'))
        end = parse_date(request.form.get('end_date'))
        if start:
            period.start_date = start
        if end:
            period.end_date = end
        period.status = request.form.get('status', period.status)
        db.session.commit()
        flash('栏目信息已更新', 'success')
        return redirect(url_for('marketing.period_schedules', period_id=period.id))

    return render_template(
        'marketing_period_form.html',
        group=period.group,
        period=period,
        default_start=period.start_date,
        default_end=period.end_date,
        unread_count=get_unread_count(current_user.id),
    )


@bp.route('/marketing/period/<int:period_id>/delete', methods=['POST'])
@login_required
def period_delete(period_id):
    """删除栏目（连带话术和执行记录）"""
    period = MarketingPeriod.query.get_or_404(period_id)
    if not can_manage_marketing(period.group_id):
        flash('没有权限', 'danger')
        return redirect(url_for('marketing.index'))

    gid = period.group_id
    name = period.period_name
    db.session.delete(period)
    db.session.commit()
    flash(f'栏目"{name}"已删除', 'info')
    return redirect(url_for('marketing.group_periods', group_id=gid))


# ============================================================
# 4. 栏目下的话术/档期列表 + 新增编辑
# ============================================================

@bp.route('/marketing/period/<int:period_id>', methods=['GET'])
@login_required
def period_schedules(period_id):
    """栏目详情 - 话术列表（按日期分组展示，管理员可编辑，业务员可读+执行）"""
    period = MarketingPeriod.query.get_or_404(period_id)
    if not can_access_group(period.group_id):
        flash('没有权限访问该栏目', 'danger')
        return redirect(url_for('marketing.index'))
    today = _date_bj()

    schedules = MarketingSchedule.query.filter_by(period_id=period_id).order_by(
        MarketingSchedule.schedule_date, MarketingSchedule.time_point, MarketingSchedule.sort_order
    ).all()

    # 是否为管理模式
    can_edit = can_manage_marketing(period.group_id)

    # 业务员模式：只展示当天话术，并定位到当前时间点最近的那一条
    today_only = not can_edit
    target_sched_id = None
    if today_only:
        schedules = [s for s in schedules if s.schedule_date == today]
        if schedules:
            # 找到当前时间（HH:MM）最接近的那一条
            from datetime import datetime
            now_time = datetime.now().strftime('%H:%M')
            closest = None
            closest_diff = None
            for s in schedules:
                tp = s.time_point or '00:00'
                try:
                    diff = abs((datetime.strptime(tp, '%H:%M') - datetime.strptime(now_time, '%H:%M')).total_seconds())
                except ValueError:
                    diff = 0
                if closest_diff is None or diff < closest_diff:
                    closest_diff = diff
                    closest = s
            if closest:
                target_sched_id = closest.id

    # 按日期分组
    by_date = {}
    for s in schedules:
        key = s.schedule_date.strftime('%Y-%m-%d')
        by_date.setdefault(key, []).append(s)

    # 排序日期
    date_list = sorted(by_date.keys())

    # 用户自身的执行记录（用来在界面上标"已执行"）
    exec_by_schedule = {}
    records = MarketingExecution.query.filter_by(
        period_id=period_id, user_id=current_user.id
    ).all()
    for r in records:
        exec_by_schedule.setdefault(r.schedule_id, []).append(r)

    return render_template(
        'marketing_period_schedules.html',
        period=period,
        group=period.group,
        schedules=schedules,
        by_date=by_date,
        date_list=date_list,
        can_edit=can_edit,
        today_only=today_only,
        target_sched_id=target_sched_id,
        today=today,
        exec_by_schedule=exec_by_schedule,
        unread_count=get_unread_count(current_user.id),
    )


@bp.route('/marketing/period/<int:period_id>/schedule/add', methods=['GET', 'POST'])
@login_required
def schedule_add(period_id):
    """新增话术"""
    period = MarketingPeriod.query.get_or_404(period_id)
    if not can_manage_marketing(period.group_id):
        flash('没有权限', 'danger')
        return redirect(url_for('marketing.index'))

    if request.method == 'POST':
        schedule_date = parse_date(request.form.get('schedule_date'))
        time_point = request.form.get('time_point', '').strip()
        # 处理富文本 HTML 中的 base64 图片
        raw_content = request.form.get('content', '').strip()
        content = process_html_images(raw_content)
        remark = request.form.get('remark', '').strip()
        sort_order = int(request.form.get('sort_order') or 0)

        # 图片上传
        image = save_upload_image(request.files.get('image'))
        # 支持额外粘贴图片 URL
        extra_image = request.form.get('image_url', '').strip()

        image_urls = []
        if image:
            image_urls.append(image)
        if extra_image:
            image_urls.append(extra_image)

        if not schedule_date or not time_point or not content:
            flash('请填写完整的日期、时间点和话术内容', 'danger')
        elif not (period.start_date <= schedule_date <= period.end_date):
            flash(f'话术日期必须在栏目的档期范围内（{period.start_date} ~ {period.end_date}）', 'danger')
        else:
            sched = MarketingSchedule(
                period_id=period.id,
                schedule_date=schedule_date,
                time_point=time_point,
                content=content,
                image_url=','.join(image_urls) if image_urls else None,
                remark=remark,
                sort_order=sort_order,
                created_by=current_user.id,
            )
            db.session.add(sched)
            db.session.commit()
            flash('话术已添加', 'success')
            return redirect(url_for('marketing.period_schedules', period_id=period.id))

    today = _date_bj()
    default_date = today if period.start_date <= today <= period.end_date else period.start_date

    return render_template(
        'marketing_schedule_form.html',
        period=period,
        schedule=None,
        default_date=default_date,
        unread_count=get_unread_count(current_user.id),
    )


@bp.route('/marketing/schedule/<int:schedule_id>/edit', methods=['GET', 'POST'])
@login_required
def schedule_edit(schedule_id):
    """编辑话术"""
    sched = MarketingSchedule.query.get_or_404(schedule_id)
    if not can_manage_marketing(sched.period.group_id):
        flash('没有权限', 'danger')
        return redirect(url_for('marketing.index'))

    if request.method == 'POST':
        sd = parse_date(request.form.get('schedule_date'))
        if sd:
            sched.schedule_date = sd
        sched.time_point = request.form.get('time_point', '').strip() or sched.time_point
        # 处理富文本 HTML 中的 base64 图片
        raw_content = request.form.get('content', '').strip()
        sched.content = process_html_images(raw_content)
        sched.remark = request.form.get('remark', '').strip()
        sched.sort_order = int(request.form.get('sort_order') or sched.sort_order or 0)

        # 图片处理
        new_img = save_upload_image(request.files.get('image'))
        extra_img = request.form.get('image_url', '').strip()
        keep_old = request.form.get('keep_images') == '1'

        urls = []
        if keep_old and sched.image_url:
            urls.extend(sched.image_url.split(','))
        if new_img:
            urls.append(new_img)
        if extra_img:
            urls.append(extra_img)
        sched.image_url = ','.join(urls) if urls else None

        db.session.commit()
        flash('话术已更新', 'success')
        return redirect(url_for('marketing.period_schedules', period_id=sched.period_id))

    return render_template(
        'marketing_schedule_form.html',
        period=sched.period,
        schedule=sched,
        default_date=sched.schedule_date,
        unread_count=get_unread_count(current_user.id),
    )


@bp.route('/marketing/schedule/<int:schedule_id>/delete', methods=['POST'])
@login_required
def schedule_delete(schedule_id):
    sched = MarketingSchedule.query.get_or_404(schedule_id)
    if not can_manage_marketing(sched.period.group_id):
        flash('没有权限', 'danger')
        return redirect(url_for('marketing.index'))
    pid = sched.period_id
    db.session.delete(sched)
    db.session.commit()
    flash('话术已删除', 'info')
    return redirect(url_for('marketing.period_schedules', period_id=pid))


# ============================================================
# 5. 话术一键复制 & 执行标记
# ============================================================

@bp.route('/marketing/schedule/<int:schedule_id>/execute', methods=['POST'])
@login_required
def schedule_execute(schedule_id):
    """点击"复制话术"后自动记录为已执行（兼容 AJAX / 表单两种模式）"""
    sched = MarketingSchedule.query.get_or_404(schedule_id)
    notes = (request.form.get('notes', '') or '').strip()
    channel = (request.form.get('channel', '') or '').strip() or '点击复制'

    # 避免同一用户对同一条话术重复记录（1 分钟内只算一次）
    now = _now_bj()
    existing = MarketingExecution.query.filter_by(
        schedule_id=sched.id, user_id=current_user.id
    ).order_by(MarketingExecution.executed_at.desc()).first()
    already_recent = existing and (now - existing.executed_at).total_seconds() < 60

    if not already_recent:
        exec_record = MarketingExecution(
            period_id=sched.period_id,
            schedule_id=sched.id,
            user_id=current_user.id,
            notes=notes,
            channel=channel,
            executed_at=now,
        )
        db.session.add(exec_record)
        db.session.commit()

    if _wants_json():
        return jsonify({'success': True, 'executed_at': now.strftime('%Y-%m-%d %H:%M')})

    flash('已记录本次营销执行', 'success')
    return redirect(url_for('marketing.period_schedules', period_id=sched.period_id))


@bp.route('/marketing/api/schedule/<int:schedule_id>/image', methods=['POST'])
@login_required
def schedule_append_image(schedule_id):
    """为已有话术追加图片（AJAX 调用，返回图片URL）"""
    sched = MarketingSchedule.query.get_or_404(schedule_id)
    image_url = save_upload_image(request.files.get('file'))
    if not image_url:
        return jsonify({'success': False, 'message': '上传失败或格式不支持'}), 400

    # 追加到 image_url 字段（逗号分隔）
    current_imgs = [u.strip() for u in (sched.image_url or '').split(',') if u.strip()]
    current_imgs.append(image_url)
    sched.image_url = ','.join(current_imgs)
    sched.update_time = _now_bj()
    db.session.commit()
    return jsonify({'success': True, 'url': image_url, 'image_url': sched.image_url})


# ============================================================
# 6. 执行结果看板
# ============================================================

@bp.route('/marketing/period/<int:period_id>/results', methods=['GET'])
@login_required
def period_results(period_id):
    """栏目执行结果看板 - 组管理员可见"""
    period = MarketingPeriod.query.get_or_404(period_id)
    if not can_manage_marketing(period.group_id):
        flash('没有权限查看执行结果', 'danger')
        return redirect(url_for('marketing.index'))

    # 统计每个业务员的执行情况
    # 找到所有属于该组的业务员
    users_in_group = User.query.filter_by(group_id=period.group_id, is_active=True).all()

    # 所有话术
    schedules = MarketingSchedule.query.filter_by(period_id=period.id).order_by(
        MarketingSchedule.schedule_date, MarketingSchedule.time_point
    ).all()
    total_schedules = len(schedules)

    # 所有执行记录
    all_executions = MarketingExecution.query.filter_by(period_id=period.id).all()

    # 按用户统计
    user_stats = []
    exec_by_user_schedule = {}
    for e in all_executions:
        exec_by_user_schedule.setdefault(e.user_id, {}).setdefault(e.schedule_id, []).append(e)

    for u in users_in_group:
        user_schedule_ids = set(exec_by_user_schedule.get(u.id, {}).keys())
        executed_count = len(user_schedule_ids)
        rate = (executed_count / total_schedules * 100) if total_schedules else 0
        latest = max(
            (e.executed_at for e in all_executions if e.user_id == u.id),
            default=None
        )
        user_stats.append({
            'user': u,
            'executed_count': executed_count,
            'total_schedules': total_schedules,
            'completion_rate': round(rate, 1),
            'latest_execution': latest,
        })

    # 按话术统计
    schedule_stats = []
    for s in schedules:
        count = sum(1 for e in all_executions if e.schedule_id == s.id)
        rate = (count / len(users_in_group) * 100) if users_in_group else 0
        schedule_stats.append({
            'schedule': s,
            'execution_count': count,
            'user_count': len(users_in_group),
            'completion_rate': round(rate, 1),
        })

    # 详细执行明细
    detail = []
    for e in sorted(all_executions, key=lambda x: x.executed_at, reverse=True):
        detail.append({
            'execution': e,
            'schedule': next((s for s in schedules if s.id == e.schedule_id), None),
            'user': next((u for u in users_in_group if u.id == e.user_id), None),
        })

    return render_template(
        'marketing_period_results.html',
        period=period,
        group=period.group,
        user_stats=user_stats,
        schedule_stats=schedule_stats,
        detail=detail[:200],
        total_executions=len(all_executions),
        unread_count=get_unread_count(current_user.id),
    )


# ============================================================
# 7. 图片上传 API（支持拖拽 / Ctrl+V 粘贴）
# ============================================================

@bp.route('/marketing/api/upload-image', methods=['POST'])
@login_required
def api_upload_image():
    """接收拖拽或粘贴的图片，上传到服务器，返回 URL。

    支持：
      - multipart/form-data 文件上传（drag & drop）
      - application/json 的 base64 图片数据（Ctrl+V）
    返回: {"success": true, "url": "/static/marketing_images/xxx.png"}
    """
    import base64, uuid

    # 方式1：文件上传
    if 'file' in request.files:
        f = request.files['file']
        if f and f.filename:
            ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else 'png'
            if ext not in ALLOWED_EXT:
                ext = 'png'
        else:
            return jsonify({'success': False, 'message': '未找到文件'})
    else:
        # 方式2：base64粘贴
        body = request.get_json(silent=True) or {}
        b64_data = body.get('data', '')
        if not b64_data:
            return jsonify({'success': False, 'message': '未找到图片数据'})
        # data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAE... 格式
        if ',' in b64_data:
            meta, b64_data = b64_data.split(',', 1)
            ext = 'png'
            if 'jpeg' in meta or 'jpg' in meta:
                ext = 'jpg'
            elif 'gif' in meta:
                ext = 'gif'
            elif 'webp' in meta:
                ext = 'webp'
        else:
            ext = 'png'
        try:
            img_bytes = base64.b64decode(b64_data)
        except Exception:
            return jsonify({'success': False, 'message': '图片数据解析失败'})

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        token = uuid.uuid4().hex[:12]
        new_name = f'paste_{token}.{ext}'
        full_path = os.path.join(UPLOAD_FOLDER, new_name)
        with open(full_path, 'wb') as wf:
            wf.write(img_bytes)
        url = f'/{UPLOAD_FOLDER}/{new_name}'
        return jsonify({'success': True, 'url': url})

    # 文件上传方式
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    token = uuid.uuid4().hex[:12]
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else 'png'
    new_name = f'upload_{token}.{ext}'
    full_path = os.path.join(UPLOAD_FOLDER, new_name)
    f.save(full_path)
    url = f'/{UPLOAD_FOLDER}/{new_name}'
    return jsonify({'success': True, 'url': url})


# ============================================================
# 8. 内联编辑/新增话术（从首页直接操作）
# ============================================================

@bp.route('/marketing/api/schedule', methods=['POST'])
@login_required
def api_schedule():
    """新建或更新话术（JSON API，用于首页内联编辑）

    新建: POST /marketing/api/schedule  {period_id, schedule_date, time_point, content, remark}
    更新: POST /marketing/api/schedule  {schedule_id, content, remark}
    """
    data = request.get_json() or {}
    period_id = data.get('period_id')
    schedule_id = data.get('schedule_id')

    if schedule_id:
        sched = MarketingSchedule.query.get(schedule_id)
        if not sched or not can_manage_marketing(sched.period.group_id):
            return jsonify({'success': False, 'message': '无权操作'})
        sched.content = data.get('content', sched.content)
        sched.remark = data.get('remark', sched.remark or '')
        sched.time_point = data.get('time_point', sched.time_point)
        db.session.commit()
        return jsonify({'success': True, 'schedule_id': sched.id})

    if not period_id:
        return jsonify({'success': False, 'message': '缺少 period_id'})

    period = MarketingPeriod.query.get(period_id)
    if not period or not can_manage_marketing(period.group_id):
        return jsonify({'success': False, 'message': '无权操作'})

    sched = MarketingSchedule(
        period_id=period.id,
        schedule_date=parse_date(data.get('schedule_date')) or _date_bj(),
        time_point=data.get('time_point', '09:00'),
        content=data.get('content', ''),
        remark=data.get('remark', ''),
        sort_order=int(data.get('sort_order') or 0),
        created_by=current_user.id,
    )
    db.session.add(sched)
    db.session.commit()
    return jsonify({
        'success': True,
        'schedule_id': sched.id,
        'schedule': {
            'id': sched.id,
            'schedule_date': sched.schedule_date.strftime('%Y-%m-%d'),
            'time_point': sched.time_point,
            'content': sched.content,
            'remark': sched.remark or '',
            'image_url': sched.image_url or '',
        }
    })


@bp.route('/marketing/api/schedule/<int:schedule_id>', methods=['DELETE'])
@login_required
def api_schedule_delete(schedule_id):
    """删除话术"""
    sched = MarketingSchedule.query.get(schedule_id)
    if not sched or not can_manage_marketing(sched.period.group_id):
        return jsonify({'success': False, 'message': '无权操作'})
    db.session.delete(sched)
    db.session.commit()
    return jsonify({'success': True})


# ============================================================
# 9. 一键快速填充（根据日期范围，每天按常见时间点生成骨架）
# ============================================================

@bp.route('/marketing/period/<int:period_id>/auto-fill', methods=['POST'])
@login_required
def period_auto_fill(period_id):
    """根据常见时间点（09:00 / 12:00 / 14:30 / 18:00 / 20:30）生成空骨架"""
    period = MarketingPeriod.query.get_or_404(period_id)
    if not can_manage_marketing(period.group_id):
        flash('没有权限', 'danger')
        return redirect(url_for('marketing.index'))

    time_points = ['09:00', '12:00', '14:30', '18:00', '20:30']

    added = 0
    cur = period.start_date
    while cur <= period.end_date:
        for idx, tp in enumerate(time_points):
            sched = MarketingSchedule(
                period_id=period.id,
                schedule_date=cur,
                time_point=tp,
                content='（待填入营销话术）',
                sort_order=idx,
                created_by=current_user.id,
            )
            db.session.add(sched)
            added += 1
        cur += timedelta(days=1)

    db.session.commit()
    flash(f'已为 {period.total_days} 天 × {len(time_points)} 个时间点生成 {added} 条话术骨架，请逐个编辑内容', 'success')
    return redirect(url_for('marketing.period_schedules', period_id=period.id))
