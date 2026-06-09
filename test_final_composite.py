"""
测试修复后的字段组合功能
"""
import sys
import json
import re
from datetime import datetime

# 模拟 order 对象
class MockOrder:
    def __init__(self):
        self.customer_name = "张三"
        self.phone = "13800138000"
        self.address = "北京市朝阳区某某街道123号"
        self.product_info = "固本回元胶囊 x3"
        self.remark = "请尽快发货"
        self.paid_amount = 100
        self.collect_amount = 0
        self.group_name = "一组"
        self.has_gift = False
        self.gift_info = ""

    @property
    def salesman(self):
        class Salesman:
            name = "李四"
        return Salesman()

def extract_product_qty(product_info):
    match = re.search(r'[xX×*]\s*(\d+)', product_info)
    if match:
        return int(match.group(1))
    match = re.search(r'(\d+)\s*[件盒瓶袋套个只箱]', product_info)
    if match:
        return int(match.group(1))
    return 1

# 从 routes_export.py 导入（简化版本用于测试）
def _get_order_field_value(order, order_field, default_zero=False):
    """根据字段名获取订单对应值 - 测试版本"""
    import json as _json
    import re as _re

    if not order_field:
        return ''

    # ========== 第一步：检查是否是真正的 JSON 配置 ==========
    is_json_config = False
    config = None

    if isinstance(order_field, dict):
        if 'type' in order_field:
            is_json_config = True
            config = order_field
    elif isinstance(order_field, str) and order_field.strip().startswith('{') and order_field.strip().endswith('}'):
        try:
            test_config = _json.loads(order_field)
            if isinstance(test_config, dict) and 'type' in test_config:
                is_json_config = True
                config = test_config
        except (ValueError, TypeError):
            pass

    if is_json_config and config:
        config_type = config.get('type', '')

        # 固定文本
        if config_type == 'fixed':
            return config.get('value', '')

        # 条件匹配
        elif config_type == 'condition':
            source_field = config.get('field', 'product_info')
            source_value = getattr(order, source_field, '') or ''
            numeric_fields = ['collect_amount', 'paid_amount', 'has_gift']
            conditions = config.get('conditions', [])
            for cond in conditions:
                match = cond.get('match', '')
                result = cond.get('result', '')
                operator = cond.get('operator', '==')
                if match == '*' or match == '':
                    return result
                if source_field in numeric_fields:
                    try:
                        source_num = float(source_value) if source_value else 0
                        match_num = float(match)
                        if operator == '==':
                            if source_num == match_num:
                                return result
                        elif operator == '>':
                            if source_num > match_num:
                                return result
                    except (ValueError, TypeError):
                        pass
            return config.get('default', '')

    # ========== 第二步：处理正则表达式格式 ==========
    if isinstance(order_field, str) and order_field.startswith('/') and order_field.endswith('/'):
        expr = order_field[1:-1]
        source_field = 'product_info'
        parts = expr.split('/')
        if len(parts) >= 3:
            source_field = parts[0]
            regex_part = '/'.join(parts[1:])
        else:
            regex_part = expr
        pattern = regex_part
        source_value = getattr(order, source_field, '') or ''
        try:
            m = _re.search(pattern, str(source_value))
            if m:
                return m.group(1) if len(m.groups()) >= 1 else m.group(0)
        except _re.error:
            pass
        return ''

    # ========== 第三步：处理模板字符串格式（支持 {字段名} 占位符） ==========
    if isinstance(order_field, str) and '{' in order_field and '}' in order_field:
        template = str(order_field)
        placeholders = _re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', template)
        if placeholders:
            result = template
            for placeholder in placeholders:
                field_value = _get_order_field_value(order, placeholder, default_zero)
                if field_value is not None and field_value != '':
                    result = result.replace('{' + placeholder + '}', str(field_value))
                else:
                    result = result.replace('{' + placeholder + '}', '')
            return result

    # ========== 第四步：处理简单字段名 ==========
    order_field_str = str(order_field) if order_field else ''
    if order_field_str == 'customer_name': return order.customer_name or ''
    elif order_field_str == 'phone': return order.phone or ''
    elif order_field_str == 'address': return order.address or ''
    elif order_field_str == 'product_info': return order.product_info or ''
    elif order_field_str == 'has_gift': return 1 if order.has_gift else 0
    elif order_field_str == 'gift_info': return order.gift_info or ''
    elif order_field_str == 'remark': return order.remark or ''
    elif order_field_str == 'paid_amount': return order.paid_amount or ''
    elif order_field_str == 'collect_amount': return order.collect_amount if order.collect_amount else 0
    elif order_field_str == '__extract_qty__': return extract_product_qty(order.product_info)
    elif order_field_str == 'group_name': return order.group_name or ''
    elif order_field_str == 'salesman_name': return order.salesman.name if order.salesman else ''
    return ''

# 运行测试
print("=" * 60)
print("测试字段组合功能")
print("=" * 60)

order = MockOrder()

test_cases = [
    ("简单字段", "customer_name"),
    ("固定文本", json.dumps({"type": "fixed", "value": "测试文本"})),
    ("客户名+电话", "{customer_name} ({phone})"),
    ("地址+备注", "{address} 备注: {remark}"),
    ("组合字段", "{product_info} 收件人: {customer_name}"),
    ("代收金额条件", json.dumps({"type": "condition", "field": "collect_amount", "conditions": [{"operator": "==", "match": "0", "result": "在线支付"}], "default": "货到付款"})),
    ("空字段测试", "{customer_name} {不存在的字段}"),
    ("组合+固定文本", "电话: {phone}"),
]

for desc, field_value in test_cases:
    result = _get_order_field_value(order, field_value)
    print(f"\n{desc}:")
    print(f"  输入: {field_value}")
    print(f"  输出: {result}")

print("\n" + "=" * 60)
print("✅ 所有测试完成！")
print("=" * 60)
