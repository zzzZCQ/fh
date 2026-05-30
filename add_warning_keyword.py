# -*- coding: utf-8 -*-
"""添加派送不成功关键词"""
import re

# 要修改的文件
files_to_fix = [
    'd:/fh/services.py'
]

# 旧的关键词列表
old_pattern = r"warning_keywords\s*=\s*\[([^\]]+)\]"

# 新关键词列表（添加'派送不成功'）
new_keywords = "['派送不成功', '送不成功', '送不出去', '无法送达', '无法派送', '拒收', '退回', '异常', '滞留']"

for file_path in files_to_fix:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'warning_keywords' in content:
            # 使用正则替换两处
            content = re.sub(old_pattern, f"warning_keywords = {new_keywords}", content)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ 已修复: {file_path}")
        else:
            print(f"⚠ 未找到关键词: {file_path}")
    except Exception as e:
        print(f"❌ 修复失败 {file_path}: {e}")

print("\n修复完成！")
