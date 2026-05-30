# -*- coding: utf-8 -*-
"""修复_update_order_status_from_routes函数的commit问题"""
import re

file_path = 'd:/fh/services.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 在第一次出现检查物流异常关键词前添加 from models import db
# 在 "更新异常标识" 注释后添加 from models import db
# 在各个分支的db.session.commit()后添加else分支

# 1. 替换第一个函数（_update_order_status_from_routes）
# 在 "# 检查物流异常关键词" 前添加导入
content = content.replace(
    '    return_keywords = [\'退回\', \'拒收\', \'无人签收\', \'退回寄件人\', \'返程\']\n    is_return = any(keyword in remark for keyword in return_keywords)\n    \n    # 检查物流异常关键词',
    '    return_keywords = [\'退回\', \'拒收\', \'无人签收\', \'退回寄件人\', \'返程\']\n    is_return = any(keyword in remark for keyword in return_keywords)\n    \n    # 检查物流异常关键词'
)

# 2. 在 "# 更新异常标识" 后添加 from models import db
content = content.replace(
    '    # 更新异常标识\n    if is_warning:',
    '    # 更新异常标识（无论状态是否变化，都要更新异常标识）\n    from models import db\n    if is_warning:'
)

# 3. 在各个分支的 db.session.commit() 后添加 else 分支
# 第一个位置：退回已签收分支的commit后
content = content.replace(
    '                    db.session.commit()\n                    print(f"[物流状态更新] 订单 {order.id}: {old_status} -> 退回已签收 (remark: {remark})")\n                    # 记录签收时间',
    '                    db.session.commit()\n                    print(f"[物流状态更新] 订单 {order.id}: {old_status} -> 退回已签收 (remark: {remark})")\n                    # 记录签收时间'
)

# 4. 在签收时间更新后添加 else分支
content = content.replace(
    '                    except ValueError:\n                        pass\n            return  # 已更新为退回已签收，无需继续\n        \n        # 正常状态更新',
    '                    except ValueError:\n                        pass\n            else:\n                # 状态没变，但异常标识可能变了，需要commit\n                db.session.commit()\n            return  # 已更新为退回已签收，无需继续\n        \n        # 正常状态更新'
)

# 5. 在第二个 import from models import db (正常状态更新分支) 前删除它
content = content.replace(
    '                    if new_status in [\'已签收\', \'退回已签收\']:\n                        accept_time = latest.get(\'acceptTime\', \'\') or latest.get(\'accepttime\', \'\') or \'\'\n                        if accept_time:\n                            from models import db\n                            try:',
    '                    if new_status in [\'已签收\', \'退回已签收\']:\n                        accept_time = latest.get(\'acceptTime\', \'\') or latest.get(\'accepttime\', \'\') or \'\'\n                        if accept_time:\n                            try:'
)

# 6. 在正常状态更新的commit后添加else分支
content = content.replace(
    '            db.session.commit()\n            print(f"[物流状态更新] 订单 {order.id}: {old_status} -> {order.logistics_status} (remark: {remark})")\n\n# ============ 下载令牌管理',
    '            db.session.commit()\n            print(f"[物流状态更新] 订单 {order.id}: {old_status} -> {order.logistics_status} (remark: {remark})")\n        else:\n            # 状态没变，但异常标识可能变了，需要commit\n            db.session.commit()\n\n# ============ 下载令牌管理'
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 已修复")
