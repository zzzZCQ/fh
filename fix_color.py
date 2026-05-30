# -*- coding: utf-8 -*-
"""修改颜色：完播改为蓝色"""

file_path = 'd:/fh/routes_behavior.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 修改Excel保存时的颜色
content = content.replace(
    "fill = PatternFill(start_color='FF00FF00', end_color='FF00FF00', fill_type='solid')\n                print(f\"[颜色设置] 用户 {nick} - 值 {fill_value} - 绿色\")",
    "fill = PatternFill(start_color='FF0000FF', end_color='FF0000FF', fill_type='solid')\n                print(f\"[颜色设置] 用户 {nick} - 值 {fill_value} - 蓝色\")"
)

# 2. 修改数据库读取时的颜色映射
content = content.replace(
    "color_map = {1: 'FF00FF00', 2: 'FFFFFF00', 3: 'FFFF0000'}",
    "color_map = {1: 'FF0000FF', 2: 'FFFFFF00', 3: 'FFFF0000'}"
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 颜色已修改：完播=蓝色, 未完播=黄色, 未观看=红色")
