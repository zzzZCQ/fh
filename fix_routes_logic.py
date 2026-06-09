"""
修复 routes_export.py 中的逻辑顺序问题
"""

file_path = 'd:/fh/routes_export.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 找到并替换处理模板字符串格式的代码块
# 问题：以 { 开头的字符串先被 JSON 解析尝试，但解析失败时应继续检查是否为模板格式

old_section = '''    # 处理模板字符串格式（支持 {字段名} 占位符）
    if isinstance(order_field, str) and '{' in order_field and '}' in order_field:
        import re as _re
        template = order_field
        # 使用非贪婪匹配，查找 {xxx} 格式，但排除 { 和 } 之间有空格或特殊字符的情况
        # 同时避免匹配到 JSON 格式的 {{ 或 }}
        placeholders = _re.findall(r'\\{([^{}]+)\\}', template)
        if placeholders and not order_field.startswith('{'):
            # 这是模板字符串格式，不是 JSON 配置
            result = template
            for placeholder in placeholders:
                field_value = _get_order_field_value(order, placeholder.strip(), default_zero)
                if field_value is not None and field_value != '':
                    result = result.replace('{' + placeholder + '}', str(field_value))
                else:
                    result = result.replace('{' + placeholder + '}', '')
            return result'''

new_section = '''    # 处理模板字符串格式（支持 {字段名} 占位符）
    # 注意：只有非 JSON 格式（不是以 { 开头或以 } 结尾的结构化数据）才是模板字符串
    if isinstance(order_field, str) and '{' in order_field and '}' in order_field:
        # 先检查是否是 JSON 配置（以 { 开头且包含 type 字段）
        is_json_config = False
        if order_field.startswith('{'):
            try:
                import json as _json_test
                test_config = _json_test.loads(order_field)
                if isinstance(test_config, dict) and 'type' in test_config:
                    is_json_config = True
            except (ValueError, TypeError):
                is_json_config = False

        # 如果不是 JSON 配置，才作为模板字符串处理
        if not is_json_config:
            import re as _re
            template = order_field
            # 使用非贪婪匹配，查找 {字段名} 格式
            placeholders = _re.findall(r'\\{([^{}]+)\\}', template)
            if placeholders:
                result = template
                for placeholder in placeholders:
                    # 跳过 JSON 的关键字（如 "type", "value" 等）
                    field_name = placeholder.strip()
                    # 如果占位符内容是 JSON 关键字（包含引号或冒号），跳过
                    if '"' in field_name or ':' in field_name or ',' in field_name:
                        continue
                    # 递归获取字段值
                    field_value = _get_order_field_value(order, field_name, default_zero)
                    if field_value is not None and field_value != '':
                        result = result.replace('{' + field_name + '}', str(field_value))
                    else:
                        result = result.replace('{' + field_name + '}', '')
                return result'''

content = content.replace(old_section, new_section)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ routes_export.py 已修复！")
print("现在：")
print("1. 先检查是否是 JSON 配置（包含 type 字段）")
print("2. 非 JSON 配置才作为模板字符串处理")
print("3. 跳过 JSON 关键字（引号、冒号、逗号等）")
