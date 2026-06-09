"""
直接替换 _get_order_field_value 函数
"""
import re

file_path = 'd:/fh/routes_export.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 找到函数起始位置
func_pattern = r'def _get_order_field_value\(order, order_field, default_zero=False\):.*?(?=^@|^def \w|\Z)'
match = re.search(func_pattern, content, re.DOTALL | re.MULTILINE)

if not match:
    print("❌ 找不到函数")
    exit(1)

print(f"✅ 找到函数，位置: {match.start()} - {match.end()}")

# 新的函数实现
new_func = '''def _get_order_field_value(order, order_field, default_zero=False):
    """根据字段名获取订单对应值

    支持多种格式：
    1. 简单字段名: customer_name, phone 等
    2. 正则表达式: /regex/ 或 /field_name/regex/
    3. 固定文本: {"type": "fixed", "value": "文本内容"}
    4. 条件匹配: {"type": "condition", "field": "字段名", "conditions": [{"match": "值1", "result": "结果1"}, ...], "default": "默认值"}
    5. 字段组合: "姓名: {customer_name}, 电话: {phone}" （支持 {字段名} 占位符）

    参数:
        default_zero: 正则未匹配时是否返回'0'（导出Excel时使用）
    """
    import json as _json
    import re as _re

    if not order_field:
        return ''

    # ========== 第一步：检查是否是真正的 JSON 配置 ==========
    # JSON 配置必须满足：以 { 开头、包含 type 关键字、解析成功
    is_json_config = False
    config = None
    if isinstance(order_field, str) and order_field.strip().startswith('{') and order_field.strip().endswith('}'):
        try:
            test_config = _json.loads(order_field)
            if isinstance(test_config, dict) and 'type' in test_config:
                is_json_config = True
                config = test_config
        except (ValueError, TypeError):
            pass
    elif isinstance(order_field, dict):
        if 'type' in order_field:
            is_json_config = True
            config = order_field

    # 如果是 JSON 配置，处理它
    if is_json_config and config:
        config_type = config.get('type', '')

        # 固定文本
        if config_type == 'fixed':
            return config.get('value', '')

        # 条件匹配
        elif config_type == 'condition':
            source_field = config.get('field', 'product_info')
            source_value = getattr(order, source_field, '') or ''

            # 特殊处理：数值字段使用数值比较
            numeric_fields = ['collect_amount', 'paid_amount', 'has_gift']

            conditions = config.get('conditions', [])
            for cond in conditions:
                match = cond.get('match', '')
                result = cond.get('result', '')
                operator = cond.get('operator', '==')

                # * 表示匹配所有（作为默认值）
                if match == '*' or match == '':
                    return result

                # 数值字段支持各种比较操作符
                if source_field in numeric_fields:
                    try:
                        source_num = float(source_value) if source_value else 0
                        match_num = float(match)

                        if operator == '==':
                            if source_num == match_num:
                                return result
                        elif operator == '!=':
                            if source_num != match_num:
                                return result
                        elif operator == '>':
                            if source_num > match_num:
                                return result
                        elif operator == '>=':
                            if source_num >= match_num:
                                return result
                        elif operator == '<':
                            if source_num < match_num:
                                return result
                        elif operator == '<=':
                            if source_num <= match_num:
                                return result
                    except (ValueError, TypeError):
                        if str(source_value) == match:
                            return result
                else:
                    # 普通字段只支持相等和包含匹配
                    if operator == '==':
                        if str(source_value) == match:
                            return result
                    else:
                        if match in str(source_value):
                            return result

            return config.get('default', '')

    # ========== 第二步：处理正则表达式格式 ==========
    if isinstance(order_field, str) and order_field.startswith('/') and order_field.endswith('/'):
        expr = order_field[1:-1]

        # 判断是否指定了源字段：/field_name/regex/group
        known_fields = ['product_info', 'address', 'phone', 'customer_name', 'remark',
                       'group_name', 'gift_info', 'paid_amount', 'collect_amount']

        source_field = 'product_info'
        parts = expr.split('/')

        if len(parts) >= 3 and parts[0] in known_fields:
            source_field = parts[0]
            regex_part = '/'.join(parts[1:])
        else:
            regex_part = expr

        # 解析组号
        rparts = regex_part.rsplit('/', 1)
        if len(rparts) == 2 and rparts[1].isdigit():
            pattern, group_idx = rparts[0], int(rparts[1])
        else:
            pattern, group_idx = regex_part, 1

        # 获取源字段值
        source_value = getattr(order, source_field, '') or ''
        if not isinstance(source_value, str):
            source_value = str(source_value)

        try:
            m = _re.search(pattern, source_value)
            if m:
                result = m.group(group_idx) if group_idx <= len(m.groups()) else (m.group(0) if group_idx == 0 else '')
                return result
            else:
                if default_zero and (r'\\d' in pattern or any(c.isdigit() for c in pattern)):
                    return '0'
        except _re.error as e:
            print(f"[WARN] 正则表达式错误: {order_field}, 错误: {e}")
        return ''

    # ========== 第三步：处理模板字符串格式（支持 {字段名} 占位符） ==========
    # 这不是 JSON 配置，而是模板字符串
    if isinstance(order_field, str) and '{' in order_field and '}' in order_field:
        template = str(order_field)

        # 查找所有 {字段名} 格式的占位符
        # 只匹配：{英文字母/中文开头，后面是字母/数字/下划线}
        placeholders = _re.findall(r'\\{([a-zA-Z_\\u4e00-\\u9fa5][a-zA-Z0-9_]*)\\}', template)

        if placeholders:
            result = template
            for placeholder in placeholders:
                # 递归获取字段值
                field_value = _get_order_field_value(order, placeholder, default_zero)
                if field_value is not None and field_value != '':
                    result = result.replace('{' + placeholder + '}', str(field_value))
                else:
                    result = result.replace('{' + placeholder + '}', '')
            return result

    # ========== 第四步：处理字符串格式的字段名（简单字段） ==========
    order_field_str = str(order_field) if order_field else ''

    if order_field_str == 'customer_name':
        return order.customer_name or ''
    elif order_field_str == 'phone':
        return order.phone or ''
    elif order_field_str == 'address':
        return order.address or ''
    elif order_field_str == 'product_info':
        return order.product_info or ''
    elif order_field_str == 'has_gift':
        return 1 if order.has_gift else 0
    elif order_field_str == 'gift_info':
        return order.gift_info or ''
    elif order_field_str == 'remark':
        return order.remark or ''
    elif order_field_str == 'paid_amount':
        return order.paid_amount or ''
    elif order_field_str == 'collect_amount':
        return order.collect_amount if order.collect_amount else 0
    elif order_field_str == '__extract_qty__':
        return extract_product_qty(order.product_info)
    elif order_field_str == 'group_name':
        return order.group_name or ''
    elif order_field_str == 'salesman_name':
        return order.salesman.name if order.salesman else ''
    elif order_field_str == '__date__':
        return datetime.now().strftime('%Y-%m-%d')
    elif order_field_str == '__seq__':
        return ''

    return ''

'''

# 替换
new_content = content[:match.start()] + new_func + content[match.end():]

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"✅ {file_path} 已成功更新！")
print("\n处理顺序：")
print("1. JSON 配置检查（type=fixed 或 condition）")
print("2. 正则表达式格式")
print("3. 模板字符串格式（{字段名} 占位符）")
print("4. 简单字段名")
