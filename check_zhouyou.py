from app import app, db
from models import CustomerFollowUp, Order

with app.app_context():
    # 查询周游的发货单
    orders = Order.query.filter(Order.customer_name.like('%周游%')).all()
    print(f'周游的发货单数量: {len(orders)}')
    for o in orders:
        print(f'  订单ID: {o.id}, 客户名: {repr(o.customer_name)}, 电话: {o.phone}, 状态: {o.status}')

    # 查询周游的客户对接记录
    records = CustomerFollowUp.query.filter(CustomerFollowUp.customer_name.like('%周游%')).all()
    print(f'\n周游的客户对接记录数量: {len(records)}')
    for r in records:
        print(f'  ID: {r.id}, 客户名: {repr(r.customer_name)}, 电话: {r.phone}, 业务员: {r.salesman_name}')
