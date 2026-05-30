# -*- coding: utf-8 -*-
"""修复_update_order_status_from_routes函数的commit问题"""
import re

file_path = 'd:/fh/services.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 旧的代码块
old_code = '''        # 检查物流异常关键词
    warning_keywords = ['派送不成功', '送不成功', '送不出去', '无法送达', '无法派送', '拒收', '退回', '异常', '滞留']
    is_warning = any(keyword in remark for keyword in warning_keywords)
    
    # 更新异常标识
    if is_warning:
        order.logistics_warning = True
        order.logistics_warning_remark = remark
        print(f"[物流异常] 订单 {order.id}: 检测到异常 - {remark}")
    else:
        order.logistics_warning = False
        order.logistics_warning_remark = None
    
    if new_status:
        # 如果remark包含退回关键词，并且是已签收相关状态，强制设置为退回已签收
        if is_return and new_status in ['已签收', '退回已签收']:
            target_status = '退回已签收'
            if order.logistics_status != target_status:
                old_status = order.logistics_status
                order.logistics_status = target_status
                from models import db
                db.session.commit()
                print(f"[物流状态更新] 订单 {order.id}: {old_status} -> 退回已签收 (remark: {remark})")
                # 记录签收时间
                accept_time = latest.get('acceptTime', '') or latest.get('accepttime', '') or ''
                if accept_time:
                    try:
                        order.sign_time = datetime.strptime(accept_time, '%Y-%m-%d %H:%M:%S')
                        db.session.commit()
                    except ValueError:
                        pass
            return  # 已更新为退回已签收，无需继续
        
        # 正常状态更新
        if new_status != order.logistics_status:
            old_status = order.logistics_status
            order.logistics_status = new_status
            
            if new_status in ['已签收', '退回已签收']:
                accept_time = latest.get('acceptTime', '') or latest.get('accepttime', '') or ''
                if accept_time:
                    from models import db
                    try:
                        order.sign_time = datetime.strptime(accept_time, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        pass
            
            from models import db
            db.session.commit()
            print(f"[物流状态更新] 订单 {order.id}: {old_status} -> {order.logistics_status} (remark: {remark})")'''

# 新的代码块
new_code = '''        # 检查物流异常关键词
    warning_keywords = ['派送不成功', '送不成功', '送不出去', '无法送达', '无法派送', '拒收', '退回', '异常', '滞留']
    is_warning = any(keyword in remark for keyword in warning_keywords)
    
    # 更新异常标识（无论状态是否变化，都要更新异常标识）
    from models import db
    if is_warning:
        order.logistics_warning = True
        order.logistics_warning_remark = remark
        print(f"[物流异常] 订单 {order.id}: 检测到异常 - {remark}")
    else:
        order.logistics_warning = False
        order.logistics_warning_remark = None
    
    if new_status:
        # 如果remark包含退回关键词，并且是已签收相关状态，强制设置为退回已签收
        if is_return and new_status in ['已签收', '退回已签收']:
            target_status = '退回已签收'
            if order.logistics_status != target_status:
                old_status = order.logistics_status
                order.logistics_status = target_status
                db.session.commit()
                print(f"[物流状态更新] 订单 {order.id}: {old_status} -> 退回已签收 (remark: {remark})")
                # 记录签收时间
                accept_time = latest.get('acceptTime', '') or latest.get('accepttime', '') or ''
                if accept_time:
                    try:
                        order.sign_time = datetime.strptime(accept_time, '%Y-%m-%d %H:%M:%S')
                        db.session.commit()
                    except ValueError:
                        pass
            else:
                # 状态没变，但异常标识可能变了，需要commit
                db.session.commit()
            return  # 已更新为退回已签收，无需继续
        
        # 正常状态更新
        if new_status != order.logistics_status:
            old_status = order.logistics_status
            order.logistics_status = new_status
            
            if new_status in ['已签收', '退回已签收']:
                accept_time = latest.get('acceptTime', '') or latest.get('accepttime', '') or ''
                if accept_time:
                    try:
                        order.sign_time = datetime.strptime(accept_time, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        pass
            
            db.session.commit()
            print(f"[物流状态更新] 订单 {order.id}: {old_status} -> {order.logistics_status} (remark: {remark})")
        else:
            # 状态没变，但异常标识可能变了，需要commit
            db.session.commit()'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ 已修复 _update_order_status_from_routes 函数")
else:
    print("⚠ 未找到目标代码块")

print("\n修复完成！")
