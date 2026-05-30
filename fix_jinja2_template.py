# -*- coding: utf-8 -*-
"""修复Jinja2模板语法错误 - 直接字符串替换"""
import os

# 要修复的文件列表
files_to_fix = [
    'd:/fh/templates/dashboard.html',
    'd:/fh/templates/admin_dashboard.html',
    'd:/fh/templates/shipper_dashboard.html',
    'd:/fh/templates/salesman_dashboard.html'
]

# 旧的代码（需要移除 [:50]）
# Jinja2不允许在过滤器后面直接使用切片
# 文件中只有 [:50 而不是 [:50]
old_code = "|default('', true)[:50}}"

# 替换为三元表达式
new_code = "[:50] if order.logistics_warning_remark else '' }}"

for file_path in files_to_fix:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if old_code in content:
            content = content.replace(old_code, new_code)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ 已修复: {file_path}")
        else:
            print(f"⚠ 未找到: {file_path}")
    except Exception as e:
        print(f"❌ 修复失败 {file_path}: {e}")

print("\n修复完成！")
