# -*- coding: utf-8 -*-
"""调试：检查字符串匹配"""
file_path = 'd:/fh/templates/dashboard.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 查找包含 logistics_warning_remark 的行
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'logistics_warning_remark' in line:
        # 搜索字符串
        search_str = "|default('', true)[:50}}"
        print(f"搜索字符串: {repr(search_str)}")
        print(f"搜索字符串长度: {len(search_str)}")
        
        if search_str in line:
            print("✅ 找到匹配！")
        else:
            print("❌ 未找到匹配")
            
        # 尝试查找包含 default 的部分
        idx = line.find("|default('', true)")
        if idx != -1:
            segment = line[idx:idx+30]
            print(f"文件中的片段: {repr(segment)}")
