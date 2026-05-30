# -*- coding: utf-8 -*-
"""添加物流异常通知功能"""
import re

file_path = 'd:/fh/services.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 通知代码
notification_code = '''

    # 发送通知给业务员
    if is_warning and order.salesman_id:
        try:
            from models import User, BroadcastNotification, NotificationReceipt
            from socket_events import push_notification_to_user

            # 获取业务员信息
            salesman = db.session.get(User, order.salesman_id)
            if salesman:
                # 创建通知
                notification = BroadcastNotification(
                    title='📦 物流异常提醒',
                    content=f"[物流异常] 客户 {order.customer_name or '未知'} 的订单出现物流异常：\\n\\n快递单号：{order.tracking_number or '未填写'}\\n收货地址：{order.address or '未知'}\\n异常信息：{remark}\\n\\n请及时处理！",
                    priority='important',
                    target_type='user',
                    target_ids=str(order.salesman_id),
                    sender_id=1,  # 系统发送
                    status='sent',
                    sent_time=_now_bj()
                )
                db.session.add(notification)
                db.session.flush()  # 获取notification.id

                # 创建接收记录
                receipt = NotificationReceipt(
                    notification_id=notification.id,
                    user_id=order.salesman_id
                )
                db.session.add(receipt)

                # 推送给在线用户
                notification_data = {
                    'id': notification.id,
                    'title': notification.title,
                    'content': notification.content,
                    'image_url': None,
                    'priority': notification.priority,
                    'timestamp': notification.sent_time.isoformat() if notification.sent_time else None
                }
                push_notification_to_user(order.salesman_id, notification_data)

                print(f"[物流异常通知] 已发送通知给业务员 {salesman.name} (ID: {order.salesman_id})")
        except Exception as notify_err:
            print(f"[物流异常通知] 发送通知失败: {notify_err}")
'''

# 在 "# 更新异常标识（无论状态是否变化，都要更新异常标识）" 后添加
content = content.replace(
    "    # 更新异常标识（无论状态是否变化，都要更新异常标识）\n    from models import db\n    if is_warning:",
    "    # 更新异常标识（无论状态是否变化，都要更新异常标识）\n    from models import db\n    if is_warning:" + notification_code
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ 已添加物流异常通知功能")
