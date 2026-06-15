# -*- coding: utf-8 -*-
"""客情应答话术库路由"""
import re
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify
from flask_login import current_user, login_required
from sqlalchemy import or_

from models import db, KnowledgeEntry, KnowledgeEntryVote, _now_bj
from helpers import role_required, get_unread_count

bp = Blueprint('knowledge', __name__)


# ============ 排序权重 ============
VOTE_WEIGHT_MULTIPLIER = 10  # 每差1票的权重
VIEW_COUNT_WEIGHT = 1  # 查看次数权重

# ============ 关键词自动提取（从标题分词） ============

# 常见停用词（搜索无意义）
_STOPWORDS = {
    '常用', '常见', '普通', '一般', '相关', '方法', '技巧', '说明', '介绍',
    '解答', '问题', '答案', '注意', '须知', '事项', '知识', '科普', '指南',
    '手册', '大全', '汇总', '整理', '汇总', '专题', '专栏', '详情', '详细',
    '简介', '概念', '什么是', '什么是', '为什么', '怎么', '如何', '怎么办',
    '的话', '话术', '模板', '参考', '示例', '例子', '范例', '案例',
    '服务', '沟通', '交流', '推广', '营销', '产品', '公司',
}


def extract_keywords_from_title(title, max_keywords=8):
    """从标题中自动提取关键词。
    策略：
    1) 按中文/英文/数字分隔成若干片段
    2) 尝试 2-4 字短词组合 + 英文/数字整词
    3) 去停用词、去重复，返回逗号分隔字符串
    """
    if not title:
        return ''

    # 先按标点符号和中英文分界分割
    segments = re.split(r'[，。、！？,.!?;:：；\s\/\\\|（）()【】\[\]"\'\-—…]+', title)
    keywords = []

    for seg in segments:
        if not seg or len(seg) < 2:
            continue

        # 英文/数字整词
        if re.match(r'^[A-Za-z0-9]+$', seg):
            if seg.lower() not in _STOPWORDS and len(seg) >= 2:
                keywords.append(seg)
            continue

        # 中文：按连续字符组合提取 2-4 字短词
        chinese_parts = re.findall(r'[\u4e00-\u9fa5]+', seg)
        for part in chinese_parts:
            # 2字词
            for i in range(len(part) - 1):
                w = part[i:i + 2]
                if w not in _STOPWORDS:
                    keywords.append(w)
            # 3字词
            for i in range(len(part) - 2):
                w = part[i:i + 3]
                if w not in _STOPWORDS:
                    keywords.append(w)
            # 4字词
            for i in range(len(part) - 3):
                w = part[i:i + 4]
                if w not in _STOPWORDS:
                    keywords.append(w)
            # 整段
            if len(part) >= 2 and part not in _STOPWORDS:
                keywords.append(part)

    # 按出现频率排序
    freq = {}
    for kw in keywords:
        if len(kw) < 2:
            continue
        freq[kw] = freq.get(kw, 0) + 1

    # 优先保留更长、更常见的词
    ranked = sorted(freq.items(), key=lambda kv: (-len(kv[0]), -kv[1]))
    picked = []
    seen = set()
    for kw, _ in ranked:
        # 去重（已包含在更长词中的短词不重复）
        if any(kw in p for p in picked):
            continue
        if kw in seen:
            continue
        seen.add(kw)
        picked.append(kw)
        if len(picked) >= max_keywords:
            break

    return ', '.join(picked)


# ============ 公共搜索页 ============
@bp.route('/knowledge/search')
@login_required
def knowledge_search():
    """搜索话术库（关键词 + 标题 + 正文模糊匹配，按权重排序）"""
    keyword = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 10

    if keyword:
        search = f"%{keyword}%"
        query = (KnowledgeEntry.query
                 .filter(KnowledgeEntry.is_active == True)
                 .filter(or_(KnowledgeEntry.keywords.like(search),
                             KnowledgeEntry.title.like(search),
                             KnowledgeEntry.content.like(search))))
    else:
        query = (KnowledgeEntry.query
                 .filter_by(is_active=True))

    # 先取所有匹配结果，按权重（有用-无用）+ 查看次数排序
    all_entries = query.all()
    # 按投票权重 + 查看次数 + 更新时间 综合排序
    all_entries.sort(
        key=lambda e: (
            e.vote_weight * VOTE_WEIGHT_MULTIPLIER + (e.view_count or 0) * VIEW_COUNT_WEIGHT,
            e.update_time.timestamp() if e.update_time else 0
        ),
        reverse=True
    )

    # 手动分页
    total = len(all_entries)
    start = (page - 1) * per_page
    end = start + per_page
    entries = all_entries[start:end]

    class FakePagination:
        def __init__(self, items, page, per_page, total_count):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total_count
            self.pages = (total_count + per_page - 1) // per_page
            self.has_prev = page > 1
            self.prev_num = page - 1
            self.has_next = page < self.pages
            self.next_num = page + 1

    pagination = FakePagination(entries, page, per_page, total)

    # 搜索到就累加查看次数
    if keyword and entries:
        for e in entries:
            e.view_count = (e.view_count or 0) + 1
        db.session.commit()

    # 获取当前用户对所有显示话术的投票状态
    if entries:
        entry_ids = [e.id for e in entries]
        user_votes = {
            v.entry_id: v.vote for v in
            KnowledgeEntryVote.query.filter(
                KnowledgeEntryVote.entry_id.in_(entry_ids),
                KnowledgeEntryVote.user_id == current_user.id
            ).all()
        }
    else:
        user_votes = {}

    return render_template(
        'knowledge_search.html',
        entries=entries,
        pagination=pagination,
        keyword=keyword,
        unread_count=get_unread_count(current_user.id),
        user_votes=user_votes,
    )


# ============ 管理员：话术管理页 ============
@bp.route('/admin/knowledge')
@role_required('admin')
def admin_knowledge():
    keyword = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 15

    if keyword:
        search = f"%{keyword}%"
        query = (KnowledgeEntry.query
                 .filter(or_(KnowledgeEntry.keywords.like(search),
                             KnowledgeEntry.title.like(search),
                             KnowledgeEntry.content.like(search)))
                 .order_by(KnowledgeEntry.update_time.desc()))
    else:
        query = KnowledgeEntry.query.order_by(KnowledgeEntry.update_time.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    entries = pagination.items

    editing_entry = None
    edit_id = request.args.get('edit', type=int)
    if edit_id:
        editing_entry = KnowledgeEntry.query.get(edit_id)

    return render_template(
        'admin_knowledge.html',
        entries=entries,
        pagination=pagination,
        keyword=keyword,
        editing_entry=editing_entry,
        unread_count=get_unread_count(current_user.id),
    )


# ============ 管理员：新增话术 ============
@bp.route('/admin/knowledge/add', methods=['POST'])
@role_required('admin')
def add_knowledge():
    title = request.form.get('title', '').strip()
    keywords_input = request.form.get('keywords', '').strip()
    content = request.form.get('content', '').strip()

    if not title or not content:
        flash('标题和话术正文不能为空', 'danger')
        return redirect(url_for('knowledge.admin_knowledge'))

    # 关键词自动从标题提取，不填时自动提取
    if keywords_input:
        keywords = keywords_input
    else:
        keywords = extract_keywords_from_title(title) or title

    entry = KnowledgeEntry(
        title=title,
        keywords=keywords,
        content=content,
        is_active=True,
        view_count=0,
        author_id=current_user.id,
    )
    db.session.add(entry)
    db.session.commit()
    flash(f'话术「{title}」已提交，关键词：{keywords}', 'success')
    return redirect(url_for('knowledge.admin_knowledge'))


# ============ 管理员：编辑话术 ============
@bp.route('/admin/knowledge/edit/<int:entry_id>', methods=['POST'])
@role_required('admin')
def edit_knowledge(entry_id):
    entry = KnowledgeEntry.query.get_or_404(entry_id)

    entry.title = request.form.get('title', entry.title).strip() or entry.title
    keywords_input = request.form.get('keywords', '').strip()
    if keywords_input:
        entry.keywords = keywords_input
    else:
        entry.keywords = extract_keywords_from_title(entry.title) or entry.title
    entry.content = request.form.get('content', entry.content).strip() or entry.content
    entry.is_active = request.form.get('is_active') == 'on'
    entry.update_time = _now_bj()

    db.session.commit()
    flash(f'话术「{entry.title}」已更新', 'success')
    return redirect(url_for('knowledge.admin_knowledge'))


# ============ 管理员：删除话术 ============
@bp.route('/admin/knowledge/delete/<int:entry_id>', methods=['POST'])
@role_required('admin')
def delete_knowledge(entry_id):
    entry = KnowledgeEntry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash(f'话术「{entry.title}」已删除', 'info')
    return redirect(url_for('knowledge.admin_knowledge'))


# ============ 管理员：切换启用状态 ============
@bp.route('/admin/knowledge/toggle/<int:entry_id>', methods=['POST'])
@role_required('admin')
def toggle_knowledge(entry_id):
    entry = KnowledgeEntry.query.get_or_404(entry_id)
    entry.is_active = not entry.is_active
    db.session.commit()
    status = '已启用' if entry.is_active else '已停用'
    flash(f'话术「{entry.title}」{status}', 'info')
    return redirect(url_for('knowledge.admin_knowledge'))


# ============ 话术投票 API ============

@bp.route('/knowledge/api/entry/<int:entry_id>/vote', methods=['POST'])
@login_required
def vote_knowledge_entry(entry_id):
    """对话术投"有用"或"无用"，或更新已有投票"""
    entry = KnowledgeEntry.query.get_or_404(entry_id)
    data = request.get_json() or {}
    vote_type = data.get('vote', '')

    if vote_type not in ('useful', 'useless'):
        return jsonify({'success': False, 'message': '无效的投票类型'}), 400

    existing = KnowledgeEntryVote.query.filter_by(
        entry_id=entry_id, user_id=current_user.id
    ).first()

    if existing:
        existing.vote = vote_type
        existing.updated_at = _now_bj()
    else:
        existing = KnowledgeEntryVote(
            entry_id=entry_id,
            user_id=current_user.id,
            vote=vote_type,
        )
        db.session.add(existing)

    db.session.commit()
    return jsonify({
        'success': True,
        'vote_weight': entry.vote_weight,
        'useful_count': entry.useful_count,
        'useless_count': entry.useless_count,
    })


@bp.route('/knowledge/api/entry/<int:entry_id>/vote', methods=['GET'])
@login_required
def get_knowledge_vote(entry_id):
    """获取当前用户对话术的投票状态"""
    vote_record = KnowledgeEntryVote.query.filter_by(
        entry_id=entry_id, user_id=current_user.id
    ).first()
    return jsonify({'vote': vote_record.vote if vote_record else None})


@bp.route('/knowledge/api/entry/<int:entry_id>/vote', methods=['DELETE'])
@login_required
def delete_knowledge_vote(entry_id):
    """取消自己的投票"""
    vote_record = KnowledgeEntryVote.query.filter_by(
        entry_id=entry_id, user_id=current_user.id
    ).first()
    if vote_record:
        db.session.delete(vote_record)
        db.session.commit()
    return jsonify({'success': True})


# ============ 客情应答 AI 智能搜索（客户身体情况分词检索）============

@bp.route('/knowledge/api/search', methods=['POST'])
@login_required
def api_knowledge_search():
    """按客户身体情况/用药情况分词检索客情应答话术"""
    data = request.get_json() or {}
    raw_keywords = data.get('keywords', '').strip()

    if not raw_keywords:
        return jsonify({'success': True, 'entries': [], 'matched_keywords': []})

    # 分词：按标点/空白分隔
    parts = re.split(r'[，。、！？,.!?;:：；\s\/\\\|（）()【】\[\]\'\-—…]+', raw_keywords)
    parts = [p.strip() for p in parts if p.strip()]

    # 对每个长句做2字/3字滑窗提取词
    extracted_kw_list = []
    for p in parts:
        if re.match(r'^[A-Za-z0-9]+$', p):
            extracted_kw_list.append(p)
            continue
        # 中文：保留原句 + 2字组合
        if len(p) >= 2 and p not in extracted_kw_list:
            extracted_kw_list.append(p)
        # 2字滑窗
        for i in range(len(p) - 1):
            w = p[i:i+2]
            if w not in extracted_kw_list:
                extracted_kw_list.append(w)
        # 3字滑窗
        for i in range(len(p) - 2):
            w = p[i:i+3]
            if w not in extracted_kw_list:
                extracted_kw_list.append(w)

    # 按关键词逐个搜索话术
    matched_entries = []
    seen_ids = set()
    all_keywords = []

    for kw in extracted_kw_list:
        if len(kw) < 2:
            continue
        search = f"%{kw}%"
        query = (KnowledgeEntry.query
                 .filter(KnowledgeEntry.is_active == True)
                 .filter(or_(KnowledgeEntry.keywords.like(search),
                             KnowledgeEntry.title.like(search),
                             KnowledgeEntry.content.like(search)))).all()
        if query:
            all_keywords.append(kw)
            for entry in query:
                if entry.id not in seen_ids:
                    seen_ids.add(entry.id)
                    matched_entries.append(entry)

    # 按投票权重 + 查看次数排序
    matched_entries.sort(
        key=lambda e: (
            e.vote_weight * VOTE_WEIGHT_MULTIPLIER + (e.view_count or 0) * VIEW_COUNT_WEIGHT,
            e.update_time.timestamp() if e.update_time else 0
        ),
        reverse=True
    )

    # 获取当前用户对所有显示话术的投票状态
    user_votes = {}
    if matched_entries:
        entry_ids = [e.id for e in matched_entries]
        user_votes = {
            v.entry_id: v.vote for v in
            KnowledgeEntryVote.query.filter(
                KnowledgeEntryVote.entry_id.in_(entry_ids),
                KnowledgeEntryVote.user_id == current_user.id
            ).all()
        }

    # 返回前 10 条
    top_entries = matched_entries[:10]

    result_list = []
    for e in top_entries:
        info = e.to_dict()
        info['user_vote'] = user_votes.get(e.id, None)
        result_list.append(info)

    return jsonify({
        'success': True,
        'entries': result_list,
        'matched_keywords': all_keywords[:20],
        'total_count': len(matched_entries)
    })
