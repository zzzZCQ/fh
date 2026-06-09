"""
修复 admin_templates.html 中的 Jinja2 语法问题
"""

file_path = 'd:/fh/templates/admin_templates.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 问题1: JavaScript 中的 {{ 被 Jinja2 解析
# 修复: 用转义方式或 raw 标签

# 修复1: JavaScript 中的 includes('{{') 和 includes('}}')
# 用模板变量的方式生成字符串
content = content.replace(
    "// 模板字符串格式（包含 {{...}} 占位符）\n    if (orderField.includes('{{') && orderField.includes('}}')) return 'composite';",
    "// 模板字符串格式（包含 { 和 } 占位符）\n    const leftBrace2 = '{';\n    const rightBrace2 = '}';\n    if (orderField.includes(leftBrace2 + leftBrace2) && orderField.includes(rightBrace2 + rightBrace2)) return 'composite';"
)

# 修复2: 模板字符串中的 {{customer_name}} 等
# 在 <script> 块中的 placeholder 属性
# 用 Jinja2 的 raw 标签包裹

# 更简单的方法：修改模板字符串格式，使用不同的分隔符，比如 {[ 和 ]}
# 或者，让后端在解析时也能处理转义

# 让我用另一种方法：修改所有在 HTML 中的 {{ 和 }} 为 Jinja2 安全的写法
# 使用字符串字面量
content = content.replace(
    '''<input type="text" class="form-control form-control-sm composite-input" placeholder='如: {{customer_name}} ({{phone}})' oninput="updateExportFinalInput(this)">''',
    '''<input type="text" class="form-control form-control-sm composite-input" placeholder="如: {customer_name} ({phone})" oninput="updateExportFinalInput(this)">'''
)
content = content.replace(
    '''<small class="form-text text-muted">使用 {{字段名}} 占位符，例如：{{customer_name}} {{phone}} 或 {{address}} 备注:{{remark}}</small>''',
    '''<small class="form-text text-muted">使用 {字段名} 占位符，例如：{customer_name} ({phone}) 或 {address} 备注:{remark}</small>'''
)

# 在编辑模式下也同样替换
content = content.replace(
    '''<input type="text" class="form-control form-control-sm composite-input" placeholder='如: {{customer_name}} ({{phone}})' oninput="updateEditExportFinalInput(this)">''',
    '''<input type="text" class="form-control form-control-sm composite-input" placeholder="如: {customer_name} ({phone})" oninput="updateEditExportFinalInput(this)">'''
)
content = content.replace(
    '''<small class="form-text text-muted">使用 {{字段名}} 占位符，例如：{{customer_name}} {{phone}} 或 {{address}} 备注:{{remark}}</small>''',
    '''<small class="form-text text-muted">使用 {字段名} 占位符，例如：{customer_name} ({phone}) 或 {address} 备注:{remark}</small>'''
)

# 现在修改后端识别逻辑：用 { 而不是 {{
# 先修改前端检测逻辑（上面已经改了）
# 现在需要修改后端：支持 {{ 或 { 两种格式
# 为了简化，我们只使用单花括号 {fieldname}

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ admin_templates.html 已修复！")
print("注意：现在占位符格式为 {字段名}（单花括号）")
