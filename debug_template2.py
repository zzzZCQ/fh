# -*- coding: utf-8 -*-
"""调试：检查文件内容的原始字节"""
file_path = 'd:/fh/templates/dashboard.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 查找包含 logistics_warning_remark 的行
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'logistics_warning_remark' in line:
        print(f"第 {i+1} 行:")
        # 打印这一行中 default 和 [:50] 之间的部分
        idx = line.find('default')
        if idx != -1:
            segment = line[idx:idx+30]
            print(f"default后的内容: {repr(segment)}")
        print()
