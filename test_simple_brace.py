"""
测试字段组合的新格式（单花括号 {字段名}）
"""

class MockOrder:
    def __init__(self):
        self.customer_name = "张三"
        self.phone = "13800138000"
        self.address = "北京市朝阳区某某街道123号"
        self.product_info = "固本回元x3"
        self.remark = "请尽快发货"
        self.paid_amount = "已付定金"
        self.collect_amount = "货到付款"
        self.group_name = "一组"
        self.salesman_name = "李四"
        self.has_gift = True
        self.gift_info = "赠品：毛巾"


def get_order_field_value(order, order_field, default_zero=False):
    """根据字段名获取订单对应值 - 使用新的单花括号格式"""
    import re as _re

    # 处理模板字符串格式（支持 {字段名} 占位符）
    if isinstance(order_field, str) and '{' in order_field and '}' in order_field:
        template = order_field
        # 使用非贪婪匹配，查找 {xxx} 格式
        placeholders = _re.findall(r'\{([^{}]+)\}', template)
        if placeholders and not order_field.startswith('{'):
            # 这是模板字符串格式，不是 JSON 配置
            result = template
            for placeholder in placeholders:
                field_value = get_order_field_value(order, placeholder.strip(), default_zero)
                if field_value is not None and field_value != '':
                    result = result.replace('{' + placeholder + '}', str(field_value))
                else:
                    result = result.replace('{' + placeholder + '}', '')
            return result

    # 处理 JSON 配置（以 { 开头的情况）
    if isinstance(order_field, str) and order_field.startswith('{'):
        try:
            config = _json.loads(order_field) if isinstance(order_field, str) else order_field
            config_type = config.get('type', '')
            if config_type == 'fixed':
                return config.get('value', '')
        except:
            pass

    # 处理字符串格式的字段名
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
    elif order_field_str == 'group_name':
        return order.group_name or ''
    elif order_field_str == 'salesman_name':
        return order.salesman_name or ''
    return ''


# 测试用例
print("=" * 60)
print("测试字段组合功能（单花括号 {字段名} 格式）")
print("=" * 60)

order = MockOrder()

test_cases = [
    ("客户名+电话", "{customer_name} ({phone})"),
    ("地址+备注", "{address} 备注: {remark}"),
    ("客户名+地址", "{customer_name} {address}"),
    ("产品名+客户", "{product_info} 收件人: {customer_name}"),
    ("简单字段", "customer_name"),
    ("空字段测试", "{customer_name} {不存在的字段}"),
    ("固定文本+字段", "电话: {phone}"),
]

for desc, template in test_cases:
    result = get_order_field_value(order, template)
    print(f"\n{desc}:")
    print(f"  输入: {template}")
    print(f"  输出: {result}")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
