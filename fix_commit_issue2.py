# -*- coding: utf-8 -*-
"""修复_update_order_status_from_routes函数的commit问题"""
import re

file_path = 'd:/fh/services.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # 找到 "# 检查物流异常关键词" 这一行
    if '# 检查物流异常关键词' in line:
        # 添加from models import db
        new_lines.append('    # 检查物流异常关键词\n')
        i += 1
        # 添加 warning_keywords
        new_lines.append(lines[i])  # warning_keywords行
        i += 1
        # 添加 is_warning
        new_lines.append(lines[i])  # is_warning行
        i += 1
        
        # 跳过旧的 "更新异常标识" 注释和from models import db
        if '    # 更新异常标识' in lines[i]:
            i += 1  # 跳过注释
        
        # 替换 if is_warning: 块
        new_lines.append('    # 更新异常标识（无论状态是否变化，都要更新异常标识）\n')
        new_lines.append('    from models import db\n')
        new_lines.append(lines[i])  # if is_warning:
        i += 1
        new_lines.append(lines[i])  # order.logistics_warning = True
        i += 1
        new_lines.append(lines[i])  # order.logistics_warning_remark = remark
        i += 1
        new_lines.append(lines[i])  # print
        i += 1
        new_lines.append('    else:\n')
        new_lines.append(lines[i+2])  # order.logistics_warning = False
        i += 3
        new_lines.append(lines[i+2])  # logistics_warning_remark = None
        i += 3
        
        # 修改状态判断后的commit逻辑
        # 找到 "if new_status:" 并继续处理
        while i < len(lines):
            line = lines[i]
            if 'from models import db' in line and i > 0 and 'db.session.commit()' not in lines[i-1]:
                # 这是在状态判断内的import，删除它
                i += 1
                continue
            
            # 在 db.session.commit() 后添加 else 分支
            if 'db.session.commit()' in line and 'if new_status != order.logistics_status:' not in lines[i-1]:
                new_lines.append(line)
                i += 1
                
                # 检查是否是在状态更新块内
                if i < len(lines) and 'if new_status != order.logistics_status:' in lines[i]:
                    # 跳过旧的状态判断
                    new_lines.append(lines[i])  # if new_status != order.logistics_status:
                    i += 1
                    new_lines.append(lines[i])  # old_status =
                    i += 1
                    new_lines.append(lines[i])  # order.logistics_status = new_status
                    i += 1
                    
                    # 跳过状态相关的处理
                    while i < len(lines) and 'db.session.commit()' not in lines[i]:
                        i += 1
                    new_lines.append(lines[i])  # db.session.commit()
                    i += 1
                    new_lines.append(lines[i])  # print
                    i += 1
                    
                    # 添加else分支
                    new_lines.append('        else:\n')
                    new_lines.append('            # 状态没变，但异常标识可能变了，需要commit\n')
                    new_lines.append('            db.session.commit()\n')
                    continue
                continue
            
            new_lines.append(line)
            i += 1
    else:
        new_lines.append(line)
        i += 1

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✅ 已修复")
