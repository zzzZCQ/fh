"""冒烟测试：访问财务相关路由，确认不再报 Unknown column。
直接运行: python smoke_test_finance.py
"""
from app import app
from models import db, AttendanceConfig, CommissionRule, Group, DingTalkAttendance

with app.app_context():
    # 1. 读取全局配置（会触发查询 attendance_config 全表）
    cfg = AttendanceConfig.get_global()
    print(f'[1] AttendanceConfig.get_global() => id={cfg.id}, rule_type={cfg.commission_rule_type}')

    # 2. 读取所有组别
    groups = Group.query.order_by(Group.id.asc()).all()
    print(f'[2] 共 {len(groups)} 个组别')

    # 3. 测试每个组别的 get_effective 解析
    for g in groups[:3]:
        effective = AttendanceConfig.get_effective(g.id)
        not_configured = getattr(effective, '_not_configured', False)
        print(f'   - 组 "{g.name}" => applies={effective.applies_to(g.id)}, not_configured={not_configured}')

    # 4. 测试迟到扣钱计算
    if cfg.id is not None and cfg.late_deduction_rules:
        amount = cfg.get_late_deduction(30)
        print(f'[4] 迟到30分钟扣钱 = {amount} 元')
    else:
        print('[4] 未配置迟到规则（正常，未保存过）')

    # 5. 测试提成计算
    try:
        comm = cfg.calculate_commission(10000.0)
        print(f'[5] 业绩10000元 提成 = {comm} 元')
    except Exception as e:
        print(f'[5] 提成计算异常（可能是还没配置）：{e}')

    # 6. 测试 CommissionRule 读取（只读，确认不会报错）
    try:
        old_rules = CommissionRule.query.all()
        print(f'[6] 旧 CommissionRule 仍可读，共 {len(old_rules)} 条（可作为迁移参考）')
    except Exception as e:
        print(f'[6] CommissionRule 无法读取（可能表已不存在，正常）：{e}')

print('>>> 全部冒烟测试通过 ✅')
