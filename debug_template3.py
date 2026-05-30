# -*- coding: utf-8 -*-
"""调试：检查文件内容"""
file_path = 'd:/fh/templates/dashboard.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 查找包含 logistics_warning_remark 的行
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'logistics_warning_remark' in line:
        print(f"第 {i+1} 行:")
        # 查找并打印从 default 开始到 title 结束的内容
        start = line.find('default')
        if start != -1:
            end = line.find('">', start)
            segment = line[start:end]
            print(f"内容: {segment}")
            print(f"repr: {repr(segment)}")
        print()
        
        # 检查是否包含我们要找的字符串
        search_str = "|default('', true)[:50}}"
        if search_str in line:
            print("✅ 找到目标字符串！")
        else:
            print("❌ 未找到目标字符串")
            # 尝试查找类似的
            if "default('', true)" in line:
                print("  找到了 default('', true)，但 [:50] 不匹配")
