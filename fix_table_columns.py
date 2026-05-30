# -*- coding: utf-8 -*-
"""修复业务员订单详情表格列对齐问题"""

file_path = 'd:/fh/templates/admin_team_performance.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 修复表格列对齐问题：添加组别和业务员列
old_html = '''                    return `
                        <tr>
                            <td>${order.customer_name}</td>
                            <td>${order.category}</td>
                            <td>${order.paid_amount || '-'}</td>
                            <td>${order.collect_amount || '-'}</td>
                            <td class="text-primary"><strong>${formatMoney(order.total_amount)}</strong></td>
                            <td><span class="badge" ${badgeStyle}>${order.status}</span></td>
                            <td>${order.tracking_number || '-'}</td>
                            <td>${order.create_time || '-'}</td>
                            <td>${order.sign_time || '-'}</td>
                        </tr>
                    `;'''

new_html = '''                    return `
                        <tr>
                            <td>${order.group_name || '-'}</td>
                            <td>${order.salesman_name || '-'}</td>
                            <td>${order.customer_name}</td>
                            <td>${order.category}</td>
                            <td>${order.paid_amount || '-'}</td>
                            <td>${order.collect_amount || '-'}</td>
                            <td class="text-primary"><strong>${formatMoney(order.total_amount)}</strong></td>
                            <td><span class="badge" ${badgeStyle}>${order.status}</span></td>
                            <td>${order.tracking_number || '-'}</td>
                            <td>${order.sign_time || '-'}</td>
                            <td>${order.create_time || '-'}</td>
                        </tr>
                    `;'''

content = content.replace(old_html, new_html)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 已修复业务员订单详情表格列对齐问题")
