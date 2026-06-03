/**
 * 订单详情相关函数 - 公共模块（基础只读版本）
 */

/**
 * 显示订单详情（只读模式）
 * @param {number} orderId - 订单ID
 */
function showOrderDetail(orderId) {
    fetch('/api/order/' + orderId)
        .then(r => {
            if (!r.ok) return r.json().then(e => { throw new Error(e.error || '加载失败'); });
            return r.json();
        })
        .then(data => {
            if (!data || data.error) {
                document.getElementById('orderDetailContent').innerHTML = '<div class="text-danger">加载订单失败：' + (data?.error || '未知错误') + '</div>';
                new bootstrap.Modal(document.getElementById('orderDetailModal')).show();
                return;
            }

            const statusMap = {'draft': '草稿', 'submitted': '待发货', 'shipped': '已发货'};
            const status = data.status === 'shipped' ? (data.logistics_status || '已发货') : (statusMap[data.status] || data.status);

            // 只读模式（与发货单列表一致）
            document.getElementById('orderDetailContent').innerHTML = `
                <div class="row">
                    <div class="col-md-6">
                        <table class="table table-sm">
                            <tr><th width="100">组别</th><td>${data.group_name}</td></tr>
                            <tr><th>微信名</th><td>${data.customer_wechat || '-'}</td></tr>
                            <tr><th>客户名</th><td>${data.customer_name}</td></tr>
                            <tr><th>已付定金</th><td>${data.paid_amount || '-'}</td></tr>
                            <tr><th>类别</th><td>${data.category}</td></tr>
                            <tr><th>快递</th><td>${data.express_type || '-'}</td></tr>
                            <tr><th>状态</th><td>${status}</td></tr>
                        </table>
                    </div>
                    <div class="col-md-6">
                        <table class="table table-sm">
                            <tr><th width="100">业务员</th><td>${data.salesman_name}</td></tr>
                            <tr><th>性别</th><td>${data.gender || '-'}</td></tr>
                            <tr><th>电话</th><td>${data.phone}</td></tr>
                            <tr><th>代收金额</th><td>${data.collect_amount || '-'}</td></tr>
                            <tr><th>地址</th><td>${data.address}</td></tr>
                            <tr><th>单号</th><td>${data.tracking_number || '-'}</td></tr>
                        </table>
                    </div>
                </div>
                <div class="row mt-2">
                    <div class="col-12">
                        <strong>产品信息：</strong>
                        <div class="border rounded p-2 mt-1 bg-light">${data.product_info || '-'}</div>
                    </div>
                </div>
                ${data.gift_info ? `<div class="row mt-2"><div class="col-12"><strong>赠品信息：</strong><div class="border rounded p-2 mt-1 bg-light">${data.gift_info}</div></div></div>` : ''}
                ${data.remark ? `<div class="row mt-2"><div class="col-12"><strong>备注：</strong><div class="border rounded p-2 mt-1 bg-light">${data.remark}</div></div></div>` : ''}
                <div class="row mt-2">
                    <div class="col-6 text-muted small">创建时间：${data.create_time}</div>
                    <div class="col-6 text-muted small text-end">更新时间：${data.update_time}</div>
                </div>
                <div id="logisticsSection"></div>
            `;

            // 设置模态框标题
            document.getElementById('orderDetailModalTitle').textContent = '订单详情';

            // 设置模态框底部按钮（只有关闭按钮）
            const footer = document.querySelector('#orderDetailModal .modal-footer');
            footer.innerHTML = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>';

            new bootstrap.Modal(document.getElementById('orderDetailModal')).show();

            // 顺丰已发货订单，加载物流信息
            if (data.express_type === '顺丰' && data.status === 'shipped' && data.tracking_number) {
                loadLogistics(data.id);
            }
        })
        .catch(err => {
            document.getElementById('orderDetailContent').innerHTML = '<div class="text-danger">加载订单失败：' + err.message + '</div>';
            new bootstrap.Modal(document.getElementById('orderDetailModal')).show();
        });
}

/**
 * 加载物流信息
 * @param {number} orderId - 订单ID
 */
function loadLogistics(orderId) {
    const section = document.getElementById('logisticsSection');
    section.innerHTML = '<div class="text-center mt-3"><div class="spinner-border spinner-border-sm text-primary"></div> <span class="text-muted">查询物流信息...</span></div>';

    fetch('/api/order/' + orderId + '/logistics')
        .then(r => r.json())
        .then(result => {
            if (result.error) { section.innerHTML = ''; return; }
            const routes = result.routes || [];
            if (routes.length === 0) {
                section.innerHTML = `
                    <div class="text-center mt-3">
                        <div class="text-muted small mb-2">暂无物流信息</div>
                        <button class="btn btn-outline-secondary btn-sm ms-2" onclick="refreshLogistics(${orderId})" title="刷新物流">
                            <i class="bi bi-arrow-clockwise"></i>
                        </button>
                    </div>`;
                return;
            }

            const groups = {};
            routes.forEach(r => {
                const date = (r.acceptTime || '').substring(0, 10);
                if (!groups[date]) groups[date] = [];
                groups[date].push(r);
            });

            const statusMap = {'已签收': 'success', '退回已签收': 'warning', '拒签': 'danger', '派送中': 'warning', '待派送': 'warning', '运送中': 'primary', '已发货': 'info'};
            const statusBadge = statusMap[result.logistics_status] || 'secondary';
            const cacheBadge = result.from_cache ? '<span class="badge bg-secondary ms-1">缓存</span>' : '';

            let html = `
                <div class="mt-3 pt-3 border-top">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h6 class="mb-0"><i class="bi bi-truck me-1"></i>物流信息${cacheBadge}</h6>
                        <div>
                            <span class="text-muted small me-2">${result.tracking_number}</span>
                            <span class="badge bg-${statusBadge}">${result.logistics_status || '已发货'}</span>
                            <button class="btn btn-outline-secondary btn-sm ms-2" onclick="refreshLogistics(${orderId})" title="刷新物流">
                                <i class="bi bi-arrow-clockwise"></i>
                            </button>
                        </div>
                    </div>
                    <div style="max-height: 350px; overflow-y: auto; padding-left: 8px;">`;

            const dates = Object.keys(groups).sort().reverse();
            dates.forEach((date, di) => {
                html += `<div class="fw-bold small text-muted mb-2 ${di > 0 ? 'mt-3 pt-2 border-top' : ''}">${date}</div>`;
                const items = groups[date].sort((a, b) => (b.acceptTime || '').localeCompare(a.acceptTime || ''));
                items.forEach((item, idx) => {
                    const time = (item.acceptTime || '').substring(11);
                    const desc = item.remark || '';
                    const isLatest = (di === 0 && idx === 0);
                    html += `
                        <div class="d-flex mb-2" style="font-size: 13px;">
                            <div class="text-nowrap text-muted small me-3" style="width: 70px;">${time}</div>
                            <div class="position-relative" style="padding-left: 20px;">
                                <div class="position-absolute rounded-circle ${isLatest ? 'bg-danger' : 'bg-secondary'}" style="width: 10px; height: 10px; top: 4px; left: 0;"></div>
                                <div class="${isLatest ? 'fw-bold text-dark' : 'text-muted'}">${item.secondaryStatusName || ''}</div>
                                <div class="text-muted small">${desc}</div>
                            </div>
                        </div>`;
                });
            });

            html += '</div></div>';
            section.innerHTML = html;
        })
        .catch(() => { section.innerHTML = '<div class="text-muted text-center mt-3 small">物流查询失败</div>'; });
}

/**
 * 手动刷新物流信息
 */
function refreshLogistics(orderId) {
    const section = document.getElementById('logisticsSection');
    section.innerHTML = '<div class="text-center mt-3"><div class="spinner-border spinner-border-sm text-primary"></div> <span class="text-muted">刷新物流信息...</span></div>';

    fetch('/api/order/' + orderId + '/logistics/refresh', {method: 'POST'})
        .then(r => r.json())
        .then(result => {
            if (result.error) {
                section.innerHTML = '<div class="text-danger text-center mt-3 small">' + result.error + '</div>';
                return;
            }
            // 刷新成功后重新加载
            loadLogistics(orderId);
        })
        .catch(() => { section.innerHTML = '<div class="text-muted text-center mt-3 small">物流刷新失败</div>'; });
}
