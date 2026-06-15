# 客情应答话术优先级投票功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现话术优先级投票功能，业务员可对话术点"有用/无用"，主页按优先级加权时间综合排序，管理员可查看统计并重置。

**Architecture:** 新增 `MarketingScheduleVote` 投票模型，话术列表查询时 JOIN 投票统计计算优先级，权重公式：排序分 = priority × 10 + 距离今天天数 × (-1)，前端 AJAX 更新投票状态。

**Tech Stack:** Python/Flask, SQLAlchemy, Bootstrap, Vanilla JS

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `models.py` | 新增 `MarketingScheduleVote` 模型，话术模型新增投票统计属性 |
| `routes_marketing.py` | 新增投票 API、主页综合排序、管理员投票管理路由 |
| `templates/marketing_index.html` | 话术卡片新增投票按钮，排序切换 |
| `templates/marketing_schedule_votes_admin.html` | 管理员投票管理页面（新建） |

---

## Task 1: 新增 MarketingScheduleVote 模型

**Files:**
- Modify: `d:\fh\models.py`（在 `MarketingSchedule` 类定义后、`MarketingExecution` 类前插入新模型）

- [ ] **Step 1: 添加 MarketingScheduleVote 模型**

在 `models.py` 第 1356 行（`MarketingExecution` 类前）插入：

```python
class MarketingScheduleVote(db.Model):
    """话术投票记录 - 业务员对话术投"有用"或"无用" """
    __tablename__ = 'marketing_schedule_vote'
    __table_args__ = (
        db.UniqueConstraint('schedule_id', 'user_id', name='uq_schedule_user_vote'),
        db.Index('idx_vote_schedule', 'schedule_id'),
        db.Index('idx_vote_user', 'user_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('marketing_schedule.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vote = db.Column(db.String(10), nullable=False)  # 'useful' 或 'useless'
    created_at = db.Column(db.DateTime, default=_now_bj)
    updated_at = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)

    schedule = db.relationship('MarketingSchedule', backref=db.backref('votes', cascade='all, delete-orphan'))
    user = db.relationship('User', foreign_keys=[user_id])
```

- [ ] **Step 2: 在 MarketingSchedule 模型中添加投票统计属性**

在 `MarketingSchedule` 类的 `content_text` 属性后（第 1378 行后）添加：

```python
    @property
    def vote_useful_count(self):
        """有用票数"""
        return db.session.query(MarketingScheduleVote).filter_by(
            schedule_id=self.id, vote='useful'
        ).count()

    @property
    def vote_useless_count(self):
        """无用票数"""
        return db.session.query(MarketingScheduleVote).filter_by(
            schedule_id=self.id, vote='useless'
        ).count()

    @property
    def vote_priority(self):
        """优先级 = 有用票数 - 无用票数"""
        return self.vote_useful_count - self.vote_useless_count
```

---

## Task 2: 新增投票 API 路由

**Files:**
- Modify: `d:\fh\routes_marketing.py`

- [ ] **Step 1: 在 routes_marketing.py 末尾添加投票 API 路由**

在文件末尾（最后一个路由后）添加：

```python
@bp.route('/marketing/api/schedule/<int:schedule_id>/vote', methods=['POST'])
@login_required
def schedule_vote(schedule_id):
    """投票或更新投票"""
    sched = MarketingSchedule.query.get_or_404(schedule_id)
    data = request.get_json() or {}
    vote_type = data.get('vote', '')

    if vote_type not in ('useful', 'useless'):
        return jsonify({'success': False, 'message': '无效的投票类型'}), 400

    existing = MarketingScheduleVote.query.filter_by(
        schedule_id=schedule_id, user_id=current_user.id
    ).first()

    if existing:
        existing.vote = vote_type
        existing.updated_at = _now_bj()
    else:
        existing = MarketingScheduleVote(
            schedule_id=schedule_id,
            user_id=current_user.id,
            vote=vote_type,
        )
        db.session.add(existing)

    db.session.commit()
    return jsonify({
        'success': True,
        'priority': sched.vote_priority,
        'useful_count': sched.vote_useful_count,
        'useless_count': sched.vote_useless_count,
    })


@bp.route('/marketing/api/schedule/<int:schedule_id>/vote', methods=['GET'])
@login_required
def get_schedule_vote(schedule_id):
    """获取当前用户对某话术的投票状态"""
    vote_record = MarketingScheduleVote.query.filter_by(
        schedule_id=schedule_id, user_id=current_user.id
    ).first()
    return jsonify({'vote': vote_record.vote if vote_record else None})


@bp.route('/marketing/api/schedule/<int:schedule_id>/vote', methods=['DELETE'])
@login_required
def delete_schedule_vote(schedule_id):
    """删除自己的投票（取消投票）"""
    vote_record = MarketingScheduleVote.query.filter_by(
        schedule_id=schedule_id, user_id=current_user.id
    ).first()
    if vote_record:
        db.session.delete(vote_record)
        db.session.commit()
    return jsonify({'success': True})
```

---

## Task 3: 修改主页查询，添加综合排序

**Files:**
- Modify: `d:\fh\routes_marketing.py`（修改 `index` 路由）

- [ ] **Step 1: 查看当前 index 路由中的话术查询代码**

找到 `index` 路由函数，阅读其话术查询逻辑（大约在 `schedule_execute` 路由之前）

- [ ] **Step 2: 添加排序权重配置常量**

在文件顶部（其他常量附近）添加：

```python
# 话术投票排序权重
VOTE_PRIORITY_WEIGHT = 10    # 优先级权重
VOTE_TIME_WEIGHT = -1         # 时间权重（越近越高）
```

- [ ] **Step 3: 修改话术查询，添加综合排序逻辑**

在主页的日程数据查询部分，找到 `period['schedules']` 的赋值逻辑，在排序之前：
1. 为每个话术计算排序分
2. 按排序分降序排列

如果当前是按日期分组的时间流，需要在每个组内对话术进行排序。

典型查询模式（需根据实际代码调整）：

```python
from datetime import date

# 综合排序分计算
def calc_sort_score(sched):
    priority = sched.vote_priority
    days_diff = (sched.schedule_date - date.today()).days
    return priority * VOTE_PRIORITY_WEIGHT + days_diff * VOTE_TIME_WEIGHT

# 在生成 schedule 字典时添加排序分
sched_dict = {
    'id': sched.id,
    'time_point': sched.time_point,
    'content': sched.content_text,
    'image_list': sched.image_list,
    'vote_priority': sched.vote_priority,
    'vote_useful': sched.vote_useful_count,
    'vote_useless': sched.vote_useless_count,
    'sort_score': calc_sort_score(sched),
}
# ... 其他字段

# 在返回前按 sort_score 降序排序
schedules = sorted(schedules, key=lambda x: x.get('sort_score', 0), reverse=True)
```

同时在 `render_template` 的上下文变量中添加当前用户的投票状态（用于前端初始化按钮样式）：

```python
# 获取当前用户对所有今日话术的投票状态
sched_ids = [s.id for s in today_schedules]
user_votes = {
    v.schedule_id: v.vote
    for v in MarketingScheduleVote.query.filter(
        MarketingScheduleVote.schedule_id.in_(sched_ids),
        MarketingScheduleVote.user_id == current_user.id
    ).all()
}
# 传入模板
return render_template('marketing_index.html',
    # ... 其他变量
    user_votes=user_votes,
    sort_mode='priority',  # 或 'time'
)
```

---

## Task 4: 前端添加投票按钮和交互

**Files:**
- Modify: `d:\fh\templates\marketing_index.html`

- [ ] **Step 1: 在话术卡片操作行添加投票按钮**

在"复制话术并执行"按钮后添加：

```html
<button class="btn btn-sm btn-outline-secondary btn-vote-useful"
        data-sched-id="{{ sched.id }}"
        title="点有用">
    <i class="bi bi-hand-thumbs-up"></i> <span class="vote-count useful">{{ sched.vote_useful_count }}</span>
</button>
<button class="btn btn-sm btn-outline-secondary btn-vote-useless"
        data-sched-id="{{ sched.id }}"
        title="点无用">
    <i class="bi bi-hand-thumbs-down"></i> <span class="vote-count useless">{{ sched.vote_useless_count }}</span>
</button>
<span class="badge bg-{{ 'success' if sched.vote_priority > 0 else 'danger' if sched.vote_priority < 0 else 'secondary' }} priority-badge ms-1" title="优先级">
    {{ '%+d'|format(sched.vote_priority) if sched.vote_priority != 0 else '±0' }}
</span>
```

- [ ] **Step 2: 添加按钮状态初始化脚本**

在 `initScheduleCard` 函数中（或者在页面底部 `document.querySelectorAll('.schedule-card-col').forEach(initScheduleCard);` 后）添加：

```javascript
// ========== 初始化投票按钮状态 ==========
function initVoteButtons() {
    // 读取后端传入的 user_votes 数据
    var userVotes = window.__userVotes__ || {};

    document.querySelectorAll('.schedule-card-col').forEach(function(cardCol) {
        var schedId = parseInt(cardCol.dataset.schedId);
        var usefulBtn = cardCol.querySelector('.btn-vote-useful');
        var uselessBtn = cardCol.querySelector('.btn-vote-useless');
        var userVote = userVotes[schedId];

        if (userVote === 'useful' && usefulBtn) {
            usefulBtn.classList.remove('btn-outline-secondary');
            usefulBtn.classList.add('btn-success');
        }
        if (userVote === 'useless' && uselessBtn) {
            uselessBtn.classList.remove('btn-outline-secondary');
            uselessBtn.classList.add('btn-danger');
        }

        // 绑定点击事件
        if (usefulBtn) {
            usefulBtn.addEventListener('click', function() {
                voteForSchedule(schedId, 'useful', cardCol);
            });
        }
        if (uselessBtn) {
            uselessBtn.addEventListener('click', function() {
                voteForSchedule(schedId, 'useless', cardCol);
            });
        }
    });
}

// ========== 投票 AJAX ==========
function voteForSchedule(schedId, voteType, cardCol) {
    fetch('/marketing/api/schedule/' + schedId + '/vote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ vote: voteType })
    }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.success) {
            var usefulBtn = cardCol.querySelector('.btn-vote-useful');
            var uselessBtn = cardCol.querySelector('.btn-vote-useless');
            var priorityBadge = cardCol.querySelector('.priority-badge');

            // 更新计数
            var usefulCount = cardCol.querySelector('.vote-count.useful');
            var uselessCount = cardCol.querySelector('.vote-count.useless');
            if (usefulCount) usefulCount.textContent = data.useful_count;
            if (uselessCount) uselessCount.textContent = data.useless_count;

            // 更新优先级徽章
            if (priorityBadge) {
                var p = data.priority;
                priorityBadge.textContent = (p > 0 ? '+' : '') + p || '±0';
                priorityBadge.className = 'badge ' + (p > 0 ? 'bg-success' : p < 0 ? 'bg-danger' : 'bg-secondary') + ' priority-badge ms-1';
            }

            // 更新按钮高亮
            if (voteType === 'useful') {
                if (usefulBtn) {
                    usefulBtn.classList.remove('btn-outline-secondary');
                    usefulBtn.classList.add('btn-success');
                }
                if (uselessBtn) {
                    uselessBtn.classList.remove('btn-danger');
                    uselessBtn.classList.add('btn-outline-secondary');
                }
            } else {
                if (uselessBtn) {
                    uselessBtn.classList.remove('btn-outline-secondary');
                    uselessBtn.classList.add('btn-danger');
                }
                if (usefulBtn) {
                    usefulBtn.classList.remove('btn-success');
                    usefulBtn.classList.add('btn-outline-secondary');
                }
            }
        }
    });
}

// 页面加载完成后初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVoteButtons);
} else {
    initVoteButtons();
}
```

- [ ] **Step 3: 添加排序切换功能**

在主页标题/筛选区域附近添加切换按钮：

```html
<div class="d-flex gap-2 mb-3">
    <button class="btn btn-sm {{ 'btn-primary' if sort_mode == 'priority' else 'btn-outline-secondary' }}" id="sort-priority">
        综合排序
    </button>
    <button class="btn btn-sm {{ 'btn-primary' if sort_mode == 'time' else 'btn-outline-secondary' }}" id="sort-time">
        时间排序
    </button>
</div>
```

添加切换脚本：

```javascript
document.getElementById('sort-priority')?.addEventListener('click', function() {
    window.location.href = '{{ url_for("marketing.index", sort="priority") }}';
});
document.getElementById('sort-time')?.addEventListener('click', function() {
    window.location.href = '{{ url_for("marketing.index", sort="time") }}';
});
```

---

## Task 5: 管理员投票管理页面

**Files:**
- Create: `d:\fh\templates\marketing_schedule_votes_admin.html`
- Modify: `d:\fh\routes_marketing.py`

- [ ] **Step 1: 添加管理员投票管理路由**

在 `routes_marketing.py` 中添加：

```python
@bp.route('/marketing/admin/schedule-votes')
@login_required
def admin_schedule_votes():
    """管理员：话术投票统计管理"""
    if not (current_user.is_admin or current_user.role == 'admin'):
        flash('需要管理员权限', 'danger')
        return redirect(url_for('marketing.index'))

    period_id = request.args.get('period_id', type=int)
    date_filter = request.args.get('date', '')

    query = db.session.query(
        MarketingSchedule.id,
        MarketingSchedule.content,
        MarketingSchedule.schedule_date,
        MarketingSchedule.time_point,
        MarketingPeriod.name.label('period_name'),
        func.count(db.case((MarketingScheduleVote.vote == 'useful', 1))).label('useful_count'),
        func.count(db.case((MarketingScheduleVote.vote == 'useless', 1))).label('useless_count'),
    ).select_from(MarketingSchedule).join(
        MarketingPeriod, MarketingSchedule.period_id == MarketingPeriod.id
    ).outerjoin(
        MarketingScheduleVote, MarketingSchedule.id == MarketingScheduleVote.schedule_id
    ).group_by(MarketingSchedule.id)

    if period_id:
        query = query.filter(MarketingSchedule.period_id == period_id)
    if date_filter:
        query = query.filter(MarketingSchedule.schedule_date == date_filter)

    query = query.order_by(
        (func.count(db.case((MarketingScheduleVote.vote == 'useful', 1))) -
         func.count(db.case((MarketingScheduleVote.vote == 'useless', 1)))).desc()
    )

    votes = query.all()
    periods = MarketingPeriod.query.order_by(MarketingPeriod.name).all()

    return render_template('marketing_schedule_votes_admin.html',
                           votes=votes, periods=periods,
                           selected_period=period_id, selected_date=date_filter)
```

同时在文件顶部添加 func 导入：

```python
from sqlalchemy import func
```

- [ ] **Step 2: 添加重置投票 API**

在投票管理路由前添加：

```python
@bp.route('/marketing/api/admin/schedule/<int:schedule_id>/vote/reset', methods=['POST'])
@login_required
def admin_reset_schedule_vote(schedule_id):
    """管理员：重置某话术的所有投票"""
    if not (current_user.is_admin or current_user.role == 'admin'):
        return jsonify({'success': False, 'message': '权限不足'}), 403

    deleted = MarketingScheduleVote.query.filter_by(schedule_id=schedule_id).delete()
    db.session.commit()
    return jsonify({'success': True, 'deleted_count': deleted})
```

- [ ] **Step 3: 创建管理页面模板**

创建 `d:\fh\templates\marketing_schedule_votes_admin.html`：

```html
{% extends "base.html" %}

{% block content %}
<div class="container mt-4">
    <h4><i class="bi bi-bar-chart"></i> 话术投票管理</h4>

    <form method="get" class="row g-3 mb-3">
        <div class="col-md-4">
            <label class="form-label">栏目</label>
            <select name="period_id" class="form-select">
                <option value="">全部栏目</option>
                {% for p in periods %}
                <option value="{{ p.id }}" {{ 'selected' if selected_period == p.id else '' }}>{{ p.name }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="col-md-3">
            <label class="form-label">日期</label>
            <input type="date" name="date" class="form-control" value="{{ selected_date }}">
        </div>
        <div class="col-md-2 d-flex align-items-end">
            <button type="submit" class="btn btn-primary w-100">筛选</button>
        </div>
    </form>

    <table class="table table-hover">
        <thead>
            <tr>
                <th>日期</th>
                <th>时间</th>
                <th>栏目</th>
                <th>话术摘要</th>
                <th>👍 有用</th>
                <th>👎 无用</th>
                <th>优先级</th>
                <th>操作</th>
            </tr>
        </thead>
        <tbody>
            {% for v in votes %}
            <tr>
                <td>{{ v.schedule_date }}</td>
                <td>{{ v.time_point }}</td>
                <td>{{ v.period_name }}</td>
                <td><small class="text-muted">{{ v.content[:50] }}...</small></td>
                <td class="text-success">{{ v.useful_count or 0 }}</td>
                <td class="text-danger">{{ v.useless_count or 0 }}</td>
                <td>
                    {% set priority = (v.useful_count or 0) - (v.useless_count or 0) %}
                    <span class="badge {{ 'bg-success' if priority > 0 else 'bg-danger' if priority < 0 else 'bg-secondary' }}">
                        {{ '%+d'|format(priority) if priority != 0 else '±0' }}
                    </span>
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-danger btn-reset-vote"
                            data-sched-id="{{ v.id }}"
                            onclick="resetVote(this, {{ v.id }})">
                        重置
                    </button>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="8" class="text-center text-muted">暂无数据</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<script>
function resetVote(btn, schedId) {
    if (!confirm('确定重置此话术的所有投票？')) return;
    fetch('/marketing/api/admin/schedule/' + schedId + '/vote/reset', {
        method: 'POST', headers: { 'Accept': 'application/json' }
    }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.success) {
            location.reload();
        } else {
            alert('重置失败');
        }
    });
}
</script>
{% endblock %}
```

---

## Task 6: 在营销管理菜单添加入口

**Files:**
- Modify: `d:\fh\templates\base.html`（或找到营销管理的菜单定义位置）

- [ ] **Step 1: 在营销管理子菜单中添加投票管理入口**

找到类似这样的菜单结构：

```html
<li class="nav-item dropdown">
    <a class="nav-link dropdown-toggle" href="#" data-bs-toggle="dropdown">营销管理</a>
    <ul class="dropdown-menu">
        <!-- 现有菜单项 -->
        <li><a class="dropdown-item" href="{{ url_for('marketing.index') }}">营销首页</a></li>
        <li><a class="dropdown-item" href="{{ url_for('marketing.admin_schedule_votes') }}">话术投票管理</a></li>
        <!-- 其他菜单项 -->
    </ul>
</li>
```

---

## 自检清单

- [ ] `MarketingScheduleVote` 模型是否有 `schedule_id + user_id` 联合唯一约束？
- [ ] `vote_useful_count`、`vote_useless_count`、`vote_priority` 属性是否正确？
- [ ] 投票 API 是否处理了"已投票则更新"的逻辑？
- [ ] 主页查询是否按 sort_score 降序排序？
- [ ] 前端投票按钮状态是否正确初始化（根据 user_votes）？
- [ ] 管理员页面是否只在 admin 用户可见？
- [ ] 管理员重置投票是否需要权限检查？
