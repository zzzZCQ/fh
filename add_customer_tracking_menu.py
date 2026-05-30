# -*- coding: utf-8 -*-
"""在导航栏添加客户跟踪菜单"""

file_path = 'd:/fh/templates/base.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 在团队业绩统计之后添加客户跟踪菜单
old_html = '''                {% if current_user.has_role('admin') %}
                <a class="nav-link {% if request.endpoint == 'performance.team_performance_dashboard' %}active{% endif %}" href="{{ url_for('performance.team_performance_dashboard') }}">
                    <i class="bi bi-people"></i> 团队业绩统计
                </a>
                {% endif %}
            </nav>
        </div>'''

new_html = '''                {% if current_user.has_role('admin') %}
                <a class="nav-link {% if request.endpoint == 'performance.team_performance_dashboard' %}active{% endif %}" href="{{ url_for('performance.team_performance_dashboard') }}">
                    <i class="bi bi-people"></i> 团队业绩统计
                </a>
                <a class="nav-link {% if request.endpoint == 'behavior.customer_tracking' %}active{% endif %}" href="{{ url_for('behavior.customer_tracking') }}">
                    <i class="bi bi-eye"></i> 客户跟踪
                </a>
                {% endif %}
            </nav>
        </div>'''

content = content.replace(old_html, new_html)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 客户跟踪菜单已添加到导航栏")
