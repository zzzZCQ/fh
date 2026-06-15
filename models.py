"""数据库模型"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta

# 北京时间 UTC+8
_BJ_TZ = timezone(timedelta(hours=8))

def _now_bj():
    """获取当前北京时间"""
    return datetime.now(_BJ_TZ).replace(tzinfo=None)


def _date_bj():
    """获取当前北京日期"""
    from datetime import date as _dt_date
    return _dt_date.today()


db = SQLAlchemy()


class Group(db.Model):
    """组别模型（树形结构）"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)  # 组名
    code = db.Column(db.String(20), unique=True)  # 组编码
    parent_id = db.Column(db.Integer, db.ForeignKey('group.id'))  # 父级ID
    level = db.Column(db.Integer, default=1)  # 层级（1=顶级，2=二级...）
    is_active = db.Column(db.Boolean, default=True)  # 是否启用
    create_time = db.Column(db.DateTime, default=_now_bj)
    
    # 自关联关系
    parent = db.relationship('Group', remote_side=[id], backref=db.backref('children', lazy=True))
    
    def get_all_children_ids(self):
        """获取所有子组ID（包括间接子组）"""
        ids = []
        for child in self.children:
            if child.is_active:
                ids.append(child.id)
                ids.extend(child.get_all_children_ids())
        return ids
    
    def get_full_path(self):
        """获取完整路径名称"""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name


class User(UserMixin, db.Model):
    """用户模型"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    roles = db.Column('role', db.String(100), nullable=False, default='salesman')  # 多角色，逗号分隔：salesman,shipper,admin
    name = db.Column(db.String(80), nullable=False)  # 用户姓名
    is_active = db.Column(db.Boolean, default=True)  # 是否启用
    can_dingtalk_export = db.Column(db.Boolean, default=False)  # 是否有导出时发送钉钉的权限
    can_broadcast = db.Column(db.Boolean, default=False)  # 是否有发送广播通知的权限
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))  # 所属组别
    
    group = db.relationship('Group', backref=db.backref('users', lazy=True))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        try:
            # 处理可能是二进制格式的旧密码哈希
            password_hash_val = self.password_hash
            if password_hash_val is None:
                return False
            # 如果是二进制，尝试解码
            if isinstance(password_hash_val, bytes):
                password_hash_val = password_hash_val.decode('utf-8')
            return check_password_hash(password_hash_val, password)
        except Exception:
            return False
    
    @property
    def role(self):
        """兼容旧代码，返回主角色"""
        return self.get_roles()[0] if self.get_roles() else 'salesman'
    
    def get_roles(self):
        """获取所有角色列表"""
        return [r.strip() for r in (self.roles or '').split(',') if r.strip()]
    
    def has_role(self, role_name):
        """检查是否有某个角色"""
        return role_name in self.get_roles()
    
    def add_role(self, role_name):
        """添加角色"""
        roles = self.get_roles()
        if role_name not in roles:
            roles.append(role_name)
            self.roles = ','.join(roles)
    
    def remove_role(self, role_name):
        """移除角色"""
        roles = self.get_roles()
        if role_name in roles:
            roles.remove(role_name)
            self.roles = ','.join(roles)
    
    def get_managed_group_ids(self):
        """获取可管理的所有组别ID（自己的组别及其所有子组）"""
        if not self.group_id:
            return []
        group = Group.query.get(self.group_id)
        if not group:
            return []
        ids = [group.id]
        ids.extend(group.get_all_children_ids())
        return ids
    
    def get_visible_group_ids(self):
        """获取可见的组别ID（同级组 + 自己的组 + 所有下级组）"""
        if not self.group_id:
            return []
        group = Group.query.get(self.group_id)
        if not group:
            return []
        ids = [group.id]
        ids.extend(group.get_all_children_ids())
        # 加上同级组
        if group.parent_id:
            siblings = Group.query.filter_by(parent_id=group.parent_id).all()
            for s in siblings:
                if s.id not in ids:
                    ids.append(s.id)
                    ids.extend(s.get_all_children_ids())
        return ids


class Order(db.Model):
    """订单模型"""
    __table_args__ = (
        db.Index('idx_order_salesman', 'salesman_id'),
        db.Index('idx_order_group', 'group_id'),
        db.Index('idx_order_status', 'status'),
        db.Index('idx_order_create_time', 'create_time'),
        db.Index('idx_order_logistics_status', 'logistics_status'),
        db.Index('idx_order_salesman_create', 'salesman_id', 'create_time'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(80), nullable=False)
    salesman_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_info = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=False)
    remark = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')  # draft, submitted, shipped
    tracking_number = db.Column(db.String(50))
    express_type = db.Column(db.String(20))  # 快递类型：顺丰/中通/申通/韵达/极兔/京东
    # 客户与金额信息
    customer_name = db.Column(db.String(80))  # 客户名
    customer_wechat = db.Column(db.String(80))  # 客户微信名
    paid_amount = db.Column(db.String(200))  # 已付定金（文本，如"100企微410"）
    pay_date = db.Column(db.Date)  # 付款日期
    collect_amount = db.Column(db.Float)  # 代收金额
    gender = db.Column(db.String(10))  # 性别（非必填）
    # 赠品信息
    has_gift = db.Column(db.Boolean, default=False)  # 是否有赠品
    gift_info = db.Column(db.String(200))  # 赠品内容
    # 物流信息
    logistics_status = db.Column(db.String(20), default='已发货')  # 已发货、派送中、待派送、已签收、拒签、退回已签收
    sign_time = db.Column(db.DateTime)  # 签收时间（顺丰API返回）
    # 物流异常标识
    logistics_warning = db.Column(db.Boolean, default=False)  # 是否有物流异常
    logistics_warning_remark = db.Column(db.Text)  # 物流异常备注
    # 关联组别（冗余存储，方便查询）
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    # 时间戳
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)
    # 删除申请
    delete_requested = db.Column(db.Boolean, default=False)
    delete_request_time = db.Column(db.DateTime)
    # 导出标记
    export_marked = db.Column(db.Boolean, default=False)  # 是否已标记导出
    export_mark_time = db.Column(db.DateTime)  # 标记时间

    salesman = db.relationship('User', backref=db.backref('orders', lazy=True))
    group = db.relationship('Group', backref=db.backref('orders', lazy=True))
    
    @property
    def salesman_name(self):
        """获取业务员姓名"""
        if self.salesman:
            return self.salesman.name
        return ''
    
    @property
    def status_text(self):
        """获取状态文本"""
        status_map = {
            'draft': '草稿',
            'submitted': '待发货',
            'shipped': self.logistics_status or '已发货'
        }
        return status_map.get(self.status, self.status)


class Notification(db.Model):
    """通知模型"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    create_time = db.Column(db.DateTime, default=_now_bj)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    importance = db.Column(db.String(20), default='normal')  # normal=一般, important=重要, urgent=紧急

    user = db.relationship('User', backref=db.backref('notifications', lazy=True))
    order = db.relationship('Order', backref=db.backref('notifications', lazy=True))


class Category(db.Model):
    """产品类别配置"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    example = db.Column(db.Text, default='')  # 示例，新增订单时展示在产品信息上方
    is_main_product = db.Column(db.Boolean, default=True)  # 是否为主品（主品需要填写完整信息，非主品如赠品只需简单信息）
    is_gift = db.Column(db.Boolean, default=False)  # 是否为赠品（用于补发赠品功能）
    related_main_product_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)  # 关联的主品ID（仅赠品有效，为空表示通用赠品）
    unit_price = db.Column(db.Float, default=0.0)  # 单价
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    expire_time = db.Column(db.DateTime, nullable=True)  # 有效期，过了这个时间后类别不再显示在新增订单中
    create_time = db.Column(db.DateTime, default=_now_bj)
    
    related_main_product = db.relationship('Category', remote_side=[id])  # 关联的主品


class Gift(db.Model):
    """赠品配置"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)  # 关联类别，为空表示通用赠品
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    create_time = db.Column(db.DateTime, default=_now_bj)
    
    category = db.relationship('Category', backref=db.backref('gifts', lazy=True))


class ExcelTemplate(db.Model):
    """Excel模板配置（导出用）"""
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)  # 原始文件名
    filepath = db.Column(db.String(500), nullable=False)  # 存储路径
    field_mapping = db.Column(db.Text, default='{}')  # 字段映射JSON: {"收件人":"customer_name","电话":"phone",...}
    create_time = db.Column(db.DateTime, default=_now_bj)
    
    category = db.relationship('Category', backref=db.backref('templates', lazy=True))


class PerformanceReportTemplate(db.Model):
    """业绩报表模板配置"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 模板名称
    filepath = db.Column(db.String(500), nullable=False)  # 模板文件路径
    categories = db.Column(db.Text, default='[]')  # 可导出的产品类别JSON列表 ["康欣胶囊","睡眠仪"]
    field_mapping = db.Column(db.Text, default='{}')  # 字段映射JSON
    is_active = db.Column(db.Boolean, default=True)
    create_time = db.Column(db.DateTime, default=_now_bj)


class ImportTemplate(db.Model):
    """Excel导入模板配置（批量更新快递信息用）"""
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)  # 原始文件名
    filepath = db.Column(db.String(500), nullable=False)  # 存储路径
    field_mapping = db.Column(db.Text, default='{}')  # 字段映射JSON: {"组别":"group_name","快递单号":"tracking_number",...}
    default_express_type = db.Column(db.String(50))  # 默认快递种类（Excel中没有时使用）
    # 列预处理配置JSON: {"客户姓名":{"type":"regex_replace","pattern":"KS\\d+","replacement":""},"手机号":{"type":"trim"}}
    column_preprocessing = db.Column(db.Text, default='{}')
    skip_rows = db.Column(db.Integer, default=0)  # 跳过前 N 行（用于第一行非表头的情况）
    create_time = db.Column(db.DateTime, default=_now_bj)
    
    category = db.relationship('Category', backref=db.backref('import_templates', lazy=True))


class CustomerFollowUp(db.Model):
    """客户对接表"""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True)
    group_name = db.Column(db.String(100), default='')
    salesman_name = db.Column(db.String(100), default='')
    salesman_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    follow_up_person = db.Column(db.String(100), default='')
    customer_name = db.Column(db.String(100), default='')
    customer_wechat = db.Column(db.String(100), default='')
    gender = db.Column(db.String(10), default='')  # 性别
    phone = db.Column(db.String(50), default='')  # 电话
    address = db.Column(db.String(500), default='')  # 地址
    category = db.Column(db.String(100), default='')  # 产品类别
    purchased_products = db.Column(db.String(500), default='')  # 已购产品（主品+数量）
    amount = db.Column(db.String(50), default='')  # 金额
    customer_status = db.Column(db.String(500), default='')  # 客户情况
    is_main_signed = db.Column(db.Boolean, default=False)  # 主品是否签收
    is_followed_up = db.Column(db.Boolean, default=False)  # 是否已对接
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)

    order = db.relationship('Order', backref=db.backref('follow_up', lazy=True))
    salesman = db.relationship('User', backref=db.backref('customer_follow_ups', lazy=True))


class ToolFile(db.Model):
    """工具箱文件管理"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)  # 文件名称
    filename = db.Column(db.String(200), nullable=False)  # 原始文件名
    filepath = db.Column(db.String(500), nullable=False)  # 存储路径
    category = db.Column(db.String(100))  # 文件分类
    uploader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 上传者ID
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)  # 上传者所在用户组ID
    create_time = db.Column(db.DateTime, default=_now_bj)
    
    uploader = db.relationship('User', backref=db.backref('tool_files', lazy=True))
    group = db.relationship('Group', backref=db.backref('tool_files', lazy=True))


class BroadcastNotification(db.Model):
    """广播通知模型"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))  # 通知标题
    content = db.Column(db.Text, nullable=False)  # 通知内容
    image_path = db.Column(db.String(500))  # 生成的图片相对路径
    user_image_path = db.Column(db.String(500))  # 用户上传的图片相对路径
    priority = db.Column(db.String(20), default='normal')  # normal/important/urgent
    target_type = db.Column(db.String(20))  # all/department/role/user
    target_ids = db.Column(db.Text)  # 目标ID列表，逗号分隔
    scheduled_time = db.Column(db.DateTime)  # 定时发送时间
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='draft')  # draft/scheduled/sent/cancelled
    create_time = db.Column(db.DateTime, default=_now_bj)
    sent_time = db.Column(db.DateTime)  # 实际发送时间
    
    sender = db.relationship('User', backref=db.backref('sent_notifications', lazy=True))


class OrderReminder(db.Model):
    """订单发货提醒模型"""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    expected_shipping_time = db.Column(db.DateTime, nullable=False)  # 预计发货时间
    is_sent = db.Column(db.Boolean, default=False)  # 是否已发送提醒
    sent_time = db.Column(db.DateTime)  # 提醒发送时间
    create_time = db.Column(db.DateTime, default=_now_bj)
    
    order = db.relationship('Order', backref=db.backref('reminders', lazy=True))
    user = db.relationship('User', backref=db.backref('order_reminders', lazy=True))


class NotificationReceipt(db.Model):
    """通知确认记录模型"""
    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer, db.ForeignKey('broadcast_notification.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    received_time = db.Column(db.DateTime)  # 客户端收到时间
    confirmed_time = db.Column(db.DateTime)  # 确认时间
    is_confirmed = db.Column(db.Boolean, default=False)
    
    notification = db.relationship('BroadcastNotification', 
                                   backref=db.backref('receipts', lazy=True))
    user = db.relationship('User', backref=db.backref('notification_receipts', lazy=True))


class WeworkCallRecord(db.Model):
    """企业微信通话记录"""
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100), nullable=False)  # 用户名
    call_start_time = db.Column(db.DateTime, nullable=False)  # 通话开始时间
    call_end_time = db.Column(db.DateTime)  # 通话结束时间
    call_duration_seconds = db.Column(db.Integer)  # 通话时长（秒）
    status = db.Column(db.String(20), default='ongoing')  # 状态: ongoing/completed
    uploader_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # 上传者ID（可选）
    upload_time = db.Column(db.DateTime, default=_now_bj)
    create_time = db.Column(db.DateTime, default=_now_bj)
    
    uploader = db.relationship('User', backref=db.backref('wework_call_records', lazy=True))


class SalesmanDailyStats(db.Model):
    """业务员每日统计（手动填写）"""
    __tablename__ = 'salesman_daily_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)  # 统计日期
    total_incoming = db.Column(db.Integer, default=0)  # 总进线
    touched_count = db.Column(db.Integer, default=0)  # 触达数
    activated_count = db.Column(db.Integer, default=0)  # 激活数
    completed_count = db.Column(db.Integer, default=0)  # 完播数
    note = db.Column(db.Text)  # 备注
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)
    
    user = db.relationship('User', backref=db.backref('daily_stats', lazy=True))
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'date', name='unique_user_date'),
    )


class BehaviorTrackingRecord(db.Model):
    """行为轨迹记录模型"""
    __tablename__ = 'behavior_tracking_record'
    __table_args__ = (
        db.Index('idx_bt_user_nickname', 'user_id', 'nickname'),
        db.Index('idx_bt_date', 'month', 'day'),
        db.Index('idx_bt_user_date', 'user_id', 'month', 'day'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nickname = db.Column(db.String(200), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    day = db.Column(db.Integer, nullable=False)
    play_status = db.Column(db.Integer, nullable=False, default=0)  # 0=无记录,1=完播,2=未完播,3=未观看
    is_rejected = db.Column(db.Boolean, default=False)  # 是否拒接
    is_missed = db.Column(db.Boolean, default=False)  # 是否未接
    call_duration_seconds = db.Column(db.Integer, default=0)
    play_order = db.Column(db.Integer, default=0)
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)
    
    user = db.relationship('User', backref=db.backref('behavior_tracking_records', lazy=True))


class CustomerInfo(db.Model):
    """客户详细信息"""
    __tablename__ = 'customer_info'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    nickname = db.Column(db.String(200), nullable=False)
    customer_name = db.Column(db.String(100), default='')  # 客户名
    gender = db.Column(db.String(10), default='')  # 性别
    age = db.Column(db.Integer, default=0)  # 年龄
    address = db.Column(db.String(500), default='')  # 地址
    phone = db.Column(db.String(50), default='')  # 电话
    health_condition = db.Column(db.Text, default='')  # 身体情况
    medication_status = db.Column(db.Text, default='')  # 用药情况
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)
    
    user = db.relationship('User', backref=db.backref('customer_infos', lazy=True))
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'nickname', name='unique_user_nickname'),
    )


class WecomConfig(db.Model):
    """企业微信配置模型"""
    __tablename__ = 'wecom_config'
    
    id = db.Column(db.Integer, primary_key=True)
    corp_id = db.Column(db.String(100), default='')  # 企业ID
    agent_id = db.Column(db.String(50), default='')  # 应用ID
    secret = db.Column(db.String(200), default='')  # 应用密钥
    qr_app_id = db.Column(db.String(100), default='')  # 扫码登录应用ID
    qr_app_secret = db.Column(db.String(200), default='')  # 扫码登录密钥
    qr_redirect_uri = db.Column(db.String(500), default='')  # 回调地址
    contact_secret = db.Column(db.String(200), default='')  # 客户联系Secret
    message_token = db.Column(db.String(100), default='')  # 消息回调Token
    message_aes_key = db.Column(db.String(200), default='')  # 消息回调加密密钥
    is_active = db.Column(db.Boolean, default=True)  # 是否启用
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)
    
    @classmethod
    def get_active_config(cls):
        """获取活跃的配置（单例）"""
        config = cls.query.filter_by(is_active=True).first()
        if not config:
            # 创建默认配置
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config
    
    def to_dict(self):
        """转为字典"""
        return {
            'id': self.id,
            'corp_id': self.corp_id,
            'agent_id': self.agent_id,
            'secret': self.secret,
            'qr_app_id': self.qr_app_id,
            'qr_app_secret': self.qr_app_secret,
            'qr_redirect_uri': self.qr_redirect_uri,
            'contact_secret': self.contact_secret,
            'message_token': self.message_token,
            'message_aes_key': self.message_aes_key,
            'is_active': self.is_active
        }


class WecomAccount(db.Model):
    """企业微信托管账号模型（SCRM系统）"""
    __tablename__ = 'wecom_account'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # 所属用户
    
    # 账号信息
    account_name = db.Column(db.String(200), nullable=False)  # 账号名称/别名
    real_name = db.Column(db.String(100))  # 真实姓名
    wecom_id = db.Column(db.String(200))  # 企业微信ID
    wecom_alias = db.Column(db.String(200))  # 别名/备注
    
    # 状态信息
    status = db.Column(db.String(50), default='offline')  # offline/online/expired
    last_login_time = db.Column(db.DateTime)  # 最后登录时间
    last_sync_time = db.Column(db.DateTime)  # 最后同步时间
    
    # 浏览器/登录状态存储
    browser_storage = db.Column(db.Text)  # Playwright浏览器状态JSON存储
    cookies = db.Column(db.Text)  # Cookies JSON
    
    # 统计信息
    customer_count = db.Column(db.Integer, default=0)  # 客户数
    message_count = db.Column(db.Integer, default=0)  # 消息数
    
    is_active = db.Column(db.Boolean, default=True)
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)
    
    user = db.relationship('User', backref=db.backref('wecom_accounts', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'account_name': self.account_name,
            'real_name': self.real_name,
            'wecom_id': self.wecom_id,
            'wecom_alias': self.wecom_alias,
            'status': self.status,
            'last_login_time': self.last_login_time.isoformat() if self.last_login_time else None,
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'customer_count': self.customer_count,
            'message_count': self.message_count,
            'is_active': self.is_active,
            'create_time': self.create_time.isoformat() if self.create_time else None
        }


class BlacklistedPhone(db.Model):
    """黑名单模型（支持手机号和地址）"""
    __tablename__ = 'blacklisted_phone'

    id = db.Column(db.Integer, primary_key=True)
    entry_type = db.Column(db.String(20), default='phone', nullable=False, index=True)  # phone 或 address
    phone = db.Column(db.String(20), unique=True, nullable=True, index=True)  # 黑名单手机号（手机号类型必填且唯一）
    address = db.Column(db.Text, nullable=True)  # 黑名单地址（地址类型必填）
    normalized_address = db.Column(db.String(255), unique=True, nullable=True, index=True)  # 归一化地址（用于唯一性校验）
    reason = db.Column(db.Text)  # 拉黑原因
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # 创建者ID
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)

    creator = db.relationship('User', backref=db.backref('blacklisted_phones', lazy=True))

    @classmethod
    def is_blacklisted(cls, phone):
        """检查手机号是否在黑名单中（向后兼容）"""
        if not phone:
            return False
        return cls.query.filter_by(phone=phone.strip(), entry_type='phone').first() is not None

    @classmethod
    def get_blacklisted_info(cls, phone):
        """获取手机号黑名单信息（向后兼容）"""
        if not phone:
            return None
        return cls.query.filter_by(phone=phone.strip(), entry_type='phone').first()

    # ---------- 地址匹配工具 ----------
    @staticmethod
    def normalize_address(text):
        """地址归一化：转小写、去空白与常见符号，统一同义词"""
        if not text:
            return ''
        import re
        text = text.strip().lower()
        # 去除空白和标点
        text = re.sub(r'\s+', '', text)
        text = re.sub(r'[，,。.！!？?；;：:"“”\'（()）\-【\[\]】《》·/\\]+', '', text)
        # 常见同义词归一
        replacements = [
            ('自治区', ''), ('特别行政区', ''), ('自治州', ''),
            ('省', ''), ('市', ''), ('区', ''), ('县', ''),
            ('镇', ''), ('乡', ''), ('村', ''), ('街道', ''),
            ('路', 'l'), ('大道', 'l'), ('街', 'j'), ('巷', 'j'),
            ('号楼', 'h'), ('号', 'h'), ('单元', 'd'), ('室', 'r'), ('栋', 'd'),
            ('building', ''), ('room', ''), ('floor', ''), ('no', ''),
            ('number', ''), ('apt', ''), ('unit', ''), ('street', ''), ('st', ''),
            ('avenue', ''), ('ave', ''), ('road', ''), ('rd', ''), ('lane', ''),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        return text

    @staticmethod
    def _char_ngrams(text, n=2):
        """生成字符 n-gram 集合"""
        if len(text) < n:
            return {text} if text else set()
        return {text[i:i + n] for i in range(len(text) - n + 1)}

    @classmethod
    def address_similarity(cls, a, b):
        """计算两个地址的相似度（0~1）"""
        na = cls.normalize_address(a)
        nb = cls.normalize_address(b)
        if not na or not nb:
            return 0.0
        # 短地址包含检查（黑名单是关键词时直接命中）
        if len(na) >= len(nb) and nb in na:
            return 1.0
        if len(nb) >= len(na) and na in nb:
            return 1.0
        # Jaccard on 2-grams
        sa = cls._char_ngrams(na, 2)
        sb = cls._char_ngrams(nb, 2)
        if not sa or not sb:
            return 0.0
        intersection = len(sa & sb)
        union = len(sa | sb)
        jaccard = intersection / union if union else 0.0
        # 同时叠加 difflib ratio 作为第二信号
        try:
            import difflib
            ratio = difflib.SequenceMatcher(None, na, nb).ratio()
        except Exception:
            ratio = 0.0
        return max(jaccard, ratio)

    @classmethod
    def check_address_blacklist(cls, address, threshold=0.75):
        """检查地址是否命中黑名单
        返回 [(entry, similarity), ...] 命中列表，按相似度降序
        """
        if not address or not address.strip():
            return []
        na = cls.normalize_address(address)
        if not na:
            return []
        # 先精确匹配 normalized_address
        exact_hit = cls.query.filter_by(entry_type='address', normalized_address=na).first()
        if exact_hit:
            return [(exact_hit, 1.0)]
        # 无精确匹配时，遍历做相似度匹配（用于检测细微差异）
        items = cls.query.filter_by(entry_type='address').all()
        hits = []
        for it in items:
            if not it.address or not it.normalized_address:
                continue
            # 归一化后做相似度计算
            sim = cls.address_similarity(na, it.normalized_address)
            if sim >= threshold:
                hits.append((it, sim))
        hits.sort(key=lambda x: -x[1])
        return hits

    @classmethod
    def check_blacklist(cls, phone=None, address=None, address_threshold=0.75):
        """综合检测：同时检查手机号和地址
        返回 {'phone_hit': entry or None, 'address_hits': [(entry, sim), ...]}
        """
        result = {'phone_hit': None, 'address_hits': []}
        if phone:
            phone_hit = cls.get_blacklisted_info(phone)
            if phone_hit:
                result['phone_hit'] = phone_hit
        if address:
            result['address_hits'] = cls.check_address_blacklist(address, address_threshold)
        return result


class WecomCustomer(db.Model):
    """企业微信客户信息（SCRM系统）"""
    __tablename__ = 'wecom_customer'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('wecom_account.id'), nullable=False)  # 所属账号
    
    # 客户信息
    external_user_id = db.Column(db.String(200))  # 企业微信外部联系人ID
    name = db.Column(db.String(200), nullable=False)  # 客户名
    avatar = db.Column(db.String(500))  # 头像URL
    gender = db.Column(db.String(10))  # 性别
    position = db.Column(db.String(200))  # 职位
    corp_name = db.Column(db.String(200))  # 公司名称
    
    # 状态和备注
    remark = db.Column(db.Text)  # 备注
    tags = db.Column(db.Text)  # 标签JSON
    status = db.Column(db.String(50), default='normal')  # normal/blocked/deleted
    
    # 统计信息
    first_contact_time = db.Column(db.DateTime)  # 首次联系时间
    last_contact_time = db.Column(db.DateTime)  # 最后联系时间
    message_count = db.Column(db.Integer, default=0)  # 消息数
    
    is_active = db.Column(db.Boolean, default=True)
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)
    
    account = db.relationship('WecomAccount', backref=db.backref('customers', lazy=True))
    
    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'external_user_id': self.external_user_id,
            'name': self.name,
            'avatar': self.avatar,
            'gender': self.gender,
            'position': self.position,
            'corp_name': self.corp_name,
            'remark': self.remark,
            'tags': self.tags,
            'status': self.status,
            'first_contact_time': self.first_contact_time.isoformat() if self.first_contact_time else None,
            'last_contact_time': self.last_contact_time.isoformat() if self.last_contact_time else None,
            'message_count': self.message_count,
            'is_active': self.is_active,
            'create_time': self.create_time.isoformat() if self.create_time else None
        }


# ============ 定时任务配置 ============

class ScheduledTask(db.Model):
    """定时任务配置表"""
    __tablename__ = 'scheduled_task'

    id = db.Column(db.Integer, primary_key=True)
    task_key = db.Column(db.String(100), unique=True, nullable=False)  # 任务唯一标识，如 update_sf_logistics
    name = db.Column(db.String(200), nullable=False)  # 任务显示名称
    description = db.Column(db.String(500))  # 任务描述

    # 执行方式：interval（间隔N小时）、cron（每天定点）
    trigger_type = db.Column(db.String(20), default='interval')
    # interval 型：间隔小时数
    interval_hours = db.Column(db.Integer, default=6)
    # cron 型：每天执行时间 HH:MM
    cron_time = db.Column(db.String(10), default='01:00')

    is_enabled = db.Column(db.Boolean, default=True)  # 是否启用
    last_run_time = db.Column(db.DateTime)  # 上次执行时间
    last_run_status = db.Column(db.String(20))  # 上次执行状态 success/failed
    last_run_message = db.Column(db.String(500))  # 上次执行结果描述
    next_run_time = db.Column(db.DateTime)  # 预计下次执行时间

    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)

    def to_dict(self):
        return {
            'id': self.id,
            'task_key': self.task_key,
            'name': self.name,
            'description': self.description,
            'trigger_type': self.trigger_type,
            'interval_hours': self.interval_hours,
            'cron_time': self.cron_time,
            'is_enabled': self.is_enabled,
            'last_run_time': self.last_run_time.strftime('%Y-%m-%d %H:%M:%S') if self.last_run_time else '-',
            'last_run_status': self.last_run_status or '-',
            'last_run_message': (self.last_run_message or '')[:80] if self.last_run_message else '-',
            'next_run_time': self.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if self.next_run_time else '-',
        }


class ScheduledTaskLog(db.Model):
    """定时任务执行日志"""
    __tablename__ = 'scheduled_task_log'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('scheduled_task.id'), nullable=False)
    run_time = db.Column(db.DateTime, default=_now_bj)  # 执行开始时间
    duration_seconds = db.Column(db.Integer, default=0)  # 执行耗时（秒）
    status = db.Column(db.String(20))  # success/failed
    message = db.Column(db.Text)  # 执行结果/错误信息

    task = db.relationship('ScheduledTask', backref=db.backref('logs', lazy=True))


# ============ 客情应答话术库 ============

class KnowledgeEntry(db.Model):
    """客情应答话术条目"""
    __tablename__ = 'knowledge_entry'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)  # 话术标题 / 主题
    keywords = db.Column(db.String(500), nullable=False)  # 关键词，逗号分隔，便于搜索命中
    content = db.Column(db.Text, nullable=False)  # 话术正文

    is_active = db.Column(db.Boolean, default=True)  # 是否启用
    view_count = db.Column(db.Integer, default=0)  # 被查看次数
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # 提交人
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)

    author = db.relationship('User', foreign_keys=[author_id])

    @property
    def useful_count(self):
        """有用票数"""
        return db.session.query(KnowledgeEntryVote).filter_by(
            entry_id=self.id, vote='useful'
        ).count()

    @property
    def useless_count(self):
        """无用票数"""
        return db.session.query(KnowledgeEntryVote).filter_by(
            entry_id=self.id, vote='useless'
        ).count()

    @property
    def vote_weight(self):
        """权重 = 有用票数 - 无用票数，用于排序"""
        return self.useful_count - self.useless_count

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'keywords': self.keywords,
            'content': self.content,
            'is_active': self.is_active,
            'view_count': self.view_count,
            'useful_count': self.useful_count,
            'useless_count': self.useless_count,
            'vote_weight': self.vote_weight,
            'create_time': self.create_time.strftime('%Y-%m-%d %H:%M') if self.create_time else '',
        }


class KnowledgeEntryVote(db.Model):
    """客情应答话术投票记录 - 用户对话术投"有用"或"无用" """
    __tablename__ = 'knowledge_entry_vote'
    __table_args__ = (
        db.UniqueConstraint('entry_id', 'user_id', name='uq_knowledge_user_vote'),
        db.Index('idx_knowledge_vote_entry', 'entry_id'),
        db.Index('idx_knowledge_vote_user', 'user_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('knowledge_entry.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vote = db.Column(db.String(10), nullable=False)  # 'useful' 或 'useless'
    created_at = db.Column(db.DateTime, default=_now_bj)
    updated_at = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)

    entry = db.relationship('KnowledgeEntry', backref=db.backref('votes', cascade='all, delete-orphan'))
    user = db.relationship('User', foreign_keys=[user_id])


# ============ 财务模块 ============

class CommissionRule(db.Model):
    """组别提成规则表"""
    __tablename__ = 'commission_rule'
    __table_args__ = (
        db.UniqueConstraint('group_id', name='uq_commission_group'),
    )

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False, index=True)

    # 规则类型：fixed=固定比例；tiered=阶梯比例（业绩越高提成越高）
    rule_type = db.Column(db.String(20), default='fixed', nullable=False)

    # fixed 模式：单一提成比例（%）
    fixed_rate = db.Column(db.Float, default=5.0)

    # tiered 模式：JSON 配置，例如：
    # [{"min_amount": 0, "max_amount": 30000, "rate": 3},
    #  {"min_amount": 30000, "max_amount": 50000, "rate": 5},
    #  {"min_amount": 50000, "max_amount": null, "rate": 10}]
    tiered_config = db.Column(db.Text)

    # 说明备注
    remark = db.Column(db.String(500))

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)

    group = db.relationship('Group', backref=db.backref('commission_rule', lazy=True, uselist=False))
    creator = db.relationship('User', backref=db.backref('commission_rules', lazy=True))

    @classmethod
    def get_by_group(cls, group_id):
        """获取指定组的提成规则，没有则返回 None"""
        if not group_id:
            return None
        return cls.query.filter_by(group_id=group_id).first()

    def calculate_commission(self, performance_amount):
        """根据业绩金额计算提成金额"""
        amount = float(performance_amount or 0)
        if amount <= 0:
            return 0.0
        if self.rule_type == 'fixed':
            return round(amount * float(self.fixed_rate or 0) / 100, 2)
        # tiered 阶梯模式
        import json
        try:
            tiers = json.loads(self.tiered_config or '[]')
        except Exception:
            tiers = []
        if not tiers:
            return round(amount * float(self.fixed_rate or 0) / 100, 2)
        # 找到匹配的区间
        for tier in tiers:
            min_a = float(tier.get('min_amount') or 0)
            max_a = tier.get('max_amount')
            rate = float(tier.get('rate') or 0)
            if max_a is None or max_a == '':
                # 无上限区间
                if amount >= min_a:
                    return round(amount * rate / 100, 2)
            else:
                max_a = float(max_a)
                if min_a <= amount < max_a:
                    return round(amount * rate / 100, 2)
        # 没匹配到，用最低一档
        first_tier = tiers[0]
        rate = float(first_tier.get('rate') or 0)
        return round(amount * rate / 100, 2)


class AttendanceConfig(db.Model):
    """财务配置表（基础薪资 + 全勤奖 + 扣款规则 + 提成规则；全局一条记录）"""
    __tablename__ = 'attendance_config'

    id = db.Column(db.Integer, primary_key=True)
    # 保留旧字段以兼容已有数据库；后续逻辑中不再使用
    group_id = db.Column(db.Integer, nullable=True)

    # 适用范围：JSON 数组，存储适用的 group_id，如 [1, 3, 5]；空数组表示"所有组别"
    applicable_group_ids = db.Column(db.Text, default='[]')

    # ===== 基础薪资 & 全勤奖 =====
    base_salary = db.Column(db.Float, default=0)
    full_attendance_bonus = db.Column(db.Float, default=0)

    # ===== 考勤扣款 =====
    # 迟到扣钱规则（JSON）：[{"minutes": 15, "amount": 20}, ...]
    late_deduction_rules = db.Column(db.Text)
    absence_deduction = db.Column(db.Float, default=0)  # 缺旷每天扣钱
    sick_leave_deduction = db.Column(db.Float, default=0)  # 病假每天扣钱
    personal_leave_deduction = db.Column(db.Float, default=0)  # 事假每天扣钱

    # 标准工作天数
    standard_work_days = db.Column(db.Integer, default=22)

    # ===== 提成规则（从 CommissionRule 合并过来）=====
    commission_rule_type = db.Column(db.String(20), default='fixed')  # fixed/tiered
    commission_fixed_rate = db.Column(db.Float, default=5.0)
    commission_tiered_config = db.Column(db.Text)  # JSON 数组

    # ===== 备注 & 元信息 =====
    remark = db.Column(db.String(500))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)

    # ---------------- 辅助方法 ----------------

    def get_applicable_group_ids(self):
        """解析适用的组别ID列表"""
        import json
        try:
            ids = json.loads(self.applicable_group_ids or '[]')
            return [int(x) for x in ids]
        except Exception:
            return []

    def applies_to(self, group_id):
        """当前配置是否适用于指定组别"""
        if not group_id:
            return False
        ids = self.get_applicable_group_ids()
        # 空数组表示"所有组别"都适用
        if not ids:
            return True
        return int(group_id) in ids

    def get_late_deduction(self, total_late_minutes):
        """计算迟到扣钱金额（按累计分钟数匹配档位）"""
        if total_late_minutes <= 0:
            return 0.0
        import json
        try:
            rules = json.loads(self.late_deduction_rules or '[]')
        except Exception:
            rules = []
        if not rules:
            return min(float(total_late_minutes), 50)
        matched_amount = 0.0
        for rule in rules:
            minutes = float(rule.get('minutes') or 0)
            amount = float(rule.get('amount') or 0)
            if total_late_minutes >= minutes:
                matched_amount = amount
            else:
                break
        return matched_amount

    def is_full_attendance(self, absence_days, sick_leave_days, personal_leave_days, total_late_minutes):
        """判断是否全勤：无缺旷、无病事假、无迟到"""
        if (float(absence_days or 0) > 0
                or float(sick_leave_days or 0) > 0
                or float(personal_leave_days or 0) > 0
                or float(total_late_minutes or 0) > 0):
            return False
        return True

    def calculate_commission(self, signed_performance):
        """根据已签收业绩计算提成金额"""
        amount = float(signed_performance or 0)
        if amount <= 0:
            return 0.0
        rule_type = (self.commission_rule_type or 'fixed').lower()
        if rule_type == 'fixed':
            return round(amount * float(self.commission_fixed_rate or 0) / 100, 2)
        # tiered 阶梯
        import json
        try:
            tiers = json.loads(self.commission_tiered_config or '[]')
        except Exception:
            tiers = []
        if not tiers:
            return round(amount * float(self.commission_fixed_rate or 0) / 100, 2)
        for tier in tiers:
            min_a = float(tier.get('min_amount') or 0)
            max_a = tier.get('max_amount')
            rate = float(tier.get('rate') or 0)
            if max_a is None or max_a == '':
                if amount >= min_a:
                    return round(amount * rate / 100, 2)
            else:
                try:
                    max_a = float(max_a)
                except (ValueError, TypeError):
                    max_a = None
                    if amount >= min_a:
                        return round(amount * rate / 100, 2)
                    continue
                if min_a <= amount < max_a:
                    return round(amount * rate / 100, 2)
        first_tier = tiers[0]
        rate = float(first_tier.get('rate') or 0)
        return round(amount * rate / 100, 2)

    # ---------------- 查询方法 ----------------

    @classmethod
    def get_global(cls):
        """获取全局唯一配置（不存在则返回默认值对象）"""
        cfg = cls.query.first()
        if cfg:
            return cfg
        # 尚未保存过，返回默认值对象（不入库）
        cfg = cls()
        cfg.applicable_group_ids = '[]'
        cfg.base_salary = 0
        cfg.full_attendance_bonus = 0
        cfg.late_deduction_rules = '[{"minutes": 15, "amount": 20}, {"minutes": 30, "amount": 50}, {"minutes": 60, "amount": 100}]'
        cfg.absence_deduction = 0
        cfg.sick_leave_deduction = 0
        cfg.personal_leave_deduction = 0
        cfg.standard_work_days = 22
        cfg.commission_rule_type = 'fixed'
        cfg.commission_fixed_rate = 5.0
        cfg.commission_tiered_config = None
        return cfg

    @classmethod
    def get_effective(cls, group_id):
        """获取对指定组有效的配置；若组不在适用范围则返回空的占位对象"""
        cfg = cls.get_global()
        if cfg.id is None:
            empty = cls()
            empty.applicable_group_ids = '[]'
            empty.base_salary = 0
            empty.full_attendance_bonus = 0
            empty.late_deduction_rules = '[]'
            empty.absence_deduction = 0
            empty.sick_leave_deduction = 0
            empty.personal_leave_deduction = 0
            empty.standard_work_days = 22
            empty.commission_rule_type = 'fixed'
            empty.commission_fixed_rate = 0.0
            empty.commission_tiered_config = '[]'
            empty._not_configured = True
            return empty
        if cfg.applies_to(group_id):
            return cfg
        # 不在适用范围内
        empty = cls()
        empty.applicable_group_ids = '[]'
        empty.base_salary = 0
        empty.full_attendance_bonus = 0
        empty.late_deduction_rules = '[]'
        empty.absence_deduction = 0
        empty.sick_leave_deduction = 0
        empty.personal_leave_deduction = 0
        empty.standard_work_days = 22
        empty.commission_rule_type = 'fixed'
        empty.commission_fixed_rate = 0.0
        empty.commission_tiered_config = '[]'
        empty._not_configured = True
        return empty


class DingTalkAttendance(db.Model):
    """钉钉考勤数据缓存"""
    __tablename__ = 'dingtalk_attendance'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'attendance_date', name='uq_user_attendance_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)

    # 考勤日期
    attendance_date = db.Column(db.Date, nullable=False, index=True)

    # 考勤结果：Normal=正常；Late=迟到；Early=早退；Absent=缺旷；Leave=请假；BusinessTrip=出差；Outside=外勤
    check_type = db.Column(db.String(50))

    # 打卡时间
    checkin_time = db.Column(db.DateTime)
    checkout_time = db.Column(db.DateTime)

    # 迟到分钟数
    late_minutes = db.Column(db.Integer, default=0)

    # 早退分钟数
    early_minutes = db.Column(db.Integer, default=0)

    # 请假时长（天）
    leave_days = db.Column(db.Float, default=0)

    # 请假类型（病假/事假/年假等）
    leave_type = db.Column(db.String(50))

    # 原始响应 JSON（保留完整信息，便于排错）
    raw_data = db.Column(db.Text)

    # 数据来源说明（钉钉 API / 手动）
    source = db.Column(db.String(50), default='dingtalk_api')

    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)

    user = db.relationship('User', backref=db.backref('attendance_records', lazy=True))

    @classmethod
    def get_month_stats(cls, user_id, year, month):
        """汇总指定用户指定月份的考勤统计"""
        from calendar import monthrange
        records = cls.query.filter_by(user_id=user_id).filter(
            db.func.extract('year', cls.attendance_date) == year,
            db.func.extract('month', cls.attendance_date) == month
        ).all()
        stats = {
            'total_days': monthrange(year, month)[1],
            'normal_days': 0,  # 正常出勤
            'late_days': 0,    # 迟到天
            'early_days': 0,   # 早退天
            'absence_days': 0, # 缺旷天
            'sick_leave_days': 0.0,  # 病假
            'personal_leave_days': 0.0,  # 事假
            'other_leave_days': 0.0,   # 其他请假
            'total_late_minutes': 0,  # 累计迟到分钟
            'business_trip_days': 0,   # 出差
            'outside_days': 0,         # 外勤
            'record_count': len(records)
        }
        for r in records:
            ct = (r.check_type or '').lower()
            if ct == 'normal':
                stats['normal_days'] += 1
            elif 'late' in ct:
                stats['late_days'] += 1
                stats['total_late_minutes'] += int(r.late_minutes or 0)
            elif 'early' in ct:
                stats['early_days'] += 1
                stats['total_late_minutes'] += int(r.early_minutes or 0)
            elif 'absent' in ct:
                stats['absence_days'] += 1
            elif ct == 'leave' or 'leave' in ct:
                lt = (r.leave_type or '').lower()
                days = float(r.leave_days or 0) or 0
                if 'sick' in lt or '病假' in lt:
                    stats['sick_leave_days'] += days
                elif 'personal' in lt or '事假' in lt:
                    stats['personal_leave_days'] += days
                else:
                    stats['other_leave_days'] += days
            elif 'businesstrip' in ct or '出差' in ct:
                stats['business_trip_days'] += 1
            elif 'outside' in ct or '外勤' in ct:
                stats['outside_days'] += 1
        return stats


class SalaryRecord(db.Model):
    """薪资核算记录表（每月每个业务员一条）"""
    __tablename__ = 'salary_record'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'year', 'month', name='uq_user_year_month'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)

    # 基础薪资金额
    base_salary = db.Column(db.Float, default=0)
    # 全勤奖
    full_attendance_bonus = db.Column(db.Float, default=0)
    # 业绩金额（总）
    performance_amount = db.Column(db.Float, default=0)
    # 已签收业绩金额
    signed_performance_amount = db.Column(db.Float, default=0)
    # 订单数
    order_count = db.Column(db.Integer, default=0)
    # 提成金额（基于已签收业绩计算）
    commission_amount = db.Column(db.Float, default=0)
    # 提成规则摘要
    commission_rule_summary = db.Column(db.String(500))

    # 考勤
    attendance_normal_days = db.Column(db.Integer, default=0)
    attendance_late_days = db.Column(db.Integer, default=0)
    attendance_absence_days = db.Column(db.Integer, default=0)
    attendance_sick_leave_days = db.Column(db.Float, default=0)
    attendance_personal_leave_days = db.Column(db.Float, default=0)
    attendance_total_late_minutes = db.Column(db.Integer, default=0)

    # 扣款项
    late_deduction = db.Column(db.Float, default=0)
    absence_deduction = db.Column(db.Float, default=0)
    sick_leave_deduction = db.Column(db.Float, default=0)
    personal_leave_deduction = db.Column(db.Float, default=0)

    # 其他调整（可手动编辑）
    manual_adjustment = db.Column(db.Float, default=0)
    manual_remark = db.Column(db.String(500))

    # 合计实发
    net_salary = db.Column(db.Float, default=0)

    # 状态：draft / confirmed / finalized
    status = db.Column(db.String(20), default='draft')

    calculated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('salary_records', lazy=True))
    group = db.relationship('Group', backref=db.backref('salary_records', lazy=True))
    operator = db.relationship('User', foreign_keys=[calculated_by], backref=db.backref('calculated_salaries', lazy=True))

    def recalculate_net(self):
        """重新计算 net_salary"""
        total = (
            float(self.base_salary or 0)
            + float(self.full_attendance_bonus or 0)
            + float(self.commission_amount or 0)
            + float(self.manual_adjustment or 0)
            - float(self.late_deduction or 0)
            - float(self.absence_deduction or 0)
            - float(self.sick_leave_deduction or 0)
            - float(self.personal_leave_deduction or 0)
        )
        self.net_salary = round(total, 2)
        return self.net_salary


# ============================================================
# 营销模块
# ============================================================

class MarketingPeriod(db.Model):
    """营销栏目/期 - 每个组每一期栏目不同，时间长短也不一样"""
    __tablename__ = 'marketing_period'
    __table_args__ = (
        db.Index('idx_period_group', 'group_id'),
        db.Index('idx_period_status', 'status'),
        db.Index('idx_period_date', 'start_date', 'end_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False, index=True)
    period_name = db.Column(db.String(200), nullable=False)        # 栏目/期名称，如"双11预热期"
    description = db.Column(db.Text)                               # 营销策略说明
    start_date = db.Column(db.Date, nullable=False)                # 开始日期
    end_date = db.Column(db.Date, nullable=False)                  # 结束日期
    status = db.Column(db.String(20), default='active')            # active / ended
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)

    group = db.relationship('Group', backref=db.backref('marketing_periods', lazy=True))
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def total_days(self):
        """档期总天数"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0

    @property
    def schedule_count(self):
        """话术条数"""
        return MarketingSchedule.query.filter_by(period_id=self.id).count()

    @property
    def execution_count(self):
        """累计执行次数"""
        return MarketingExecution.query.filter_by(period_id=self.id).count()

    @classmethod
    def get_active_period(cls, group_id):
        """获取组当前正在进行的栏目"""
        today = _date_bj()
        return cls.query.filter(
            cls.group_id == group_id,
            cls.status == 'active',
            cls.start_date <= today,
            cls.end_date >= today
        ).order_by(cls.create_time.desc()).first()


class MarketingSchedule(db.Model):
    """营销话术/档期 - 每个时间点一条话术+图片"""
    __tablename__ = 'marketing_schedule'
    __table_args__ = (
        db.Index('idx_schedule_period', 'period_id'),
        db.Index('idx_schedule_date', 'schedule_date', 'time_point'),
    )

    id = db.Column(db.Integer, primary_key=True)
    period_id = db.Column(db.Integer, db.ForeignKey('marketing_period.id'), nullable=False, index=True)
    schedule_date = db.Column(db.Date, nullable=False)              # 档期日期
    time_point = db.Column(db.String(10), nullable=False)           # 时间点，如 "09:00" "14:30"
    content = db.Column(db.Text, nullable=False)                    # 营销话术正文
    image_url = db.Column(db.String(500))                           # 配套图片地址（支持多张用英文逗号分隔）
    remark = db.Column(db.String(500))                              # 备注/使用说明
    sort_order = db.Column(db.Integer, default=0)                   # 排序
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    create_time = db.Column(db.DateTime, default=_now_bj)
    update_time = db.Column(db.DateTime, default=_now_bj, onupdate=_now_bj)

    period = db.relationship('MarketingPeriod', backref=db.backref('schedules', cascade='all, delete-orphan', lazy=True))
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def execution_count(self):
        """本条话术被执行次数"""
        return MarketingExecution.query.filter_by(schedule_id=self.id).count()

    @property
    def image_list(self):
        """图片列表（兼容多图，同时从 content 中解析 [图片] URL 标记）"""
        import re
        urls = []
        seen = set()
        # 1. 来自 image_url 字段（逗号分隔）
        if self.image_url:
            for u in self.image_url.split(','):
                u = u.strip()
                if u and u not in seen:
                    seen.add(u)
                    urls.append(u)
        # 2. 来自 content 中的 [图片] URL 标记
        if self.content:
            for m in re.finditer(r'\[图片\]\s*(\S+)', self.content):
                u = m.group(1).strip()
                if u and u not in seen:
                    seen.add(u)
                    urls.append(u)
        return urls

    @property
    def content_text(self):
        """话术纯文本（去除所有 HTML 标签，用于复制到剪贴板）"""
        import re
        if not self.content:
            return ''
        # 如果是 HTML 内容，提取纯文本
        if '<' in self.content:
            # 提取 img 标签的 alt 或 src 文本
            texts = re.sub(r'<img[^>]+alt=["\']([^"\']+)["\'][^>]*>', r'[\1]', self.content)
            texts = re.sub(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', '[图片]', texts)
            # 去除所有其他 HTML 标签
            texts = re.sub(r'<[^>]+>', '', texts)
            # 解码 HTML 实体
            texts = texts.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
            return texts.strip()
        # 纯文本：去除 [图片] URL 标记
        return re.sub(r'\s*\[图片\]\s*\S+', '', self.content).strip()


class MarketingExecution(db.Model):
    """营销执行记录 - 业务员点"已执行"后生成"""
    __tablename__ = 'marketing_execution'
    __table_args__ = (
        db.Index('idx_exec_period', 'period_id'),
        db.Index('idx_exec_schedule', 'schedule_id'),
        db.Index('idx_exec_user', 'user_id'),
        db.Index('idx_exec_date', 'executed_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    period_id = db.Column(db.Integer, db.ForeignKey('marketing_period.id'), nullable=False, index=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('marketing_schedule.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    executed_at = db.Column(db.DateTime, default=_now_bj)          # 实际执行时间
    notes = db.Column(db.String(500))                               # 业务员备注/反馈
    channel = db.Column(db.String(50))                              # 推送渠道：企微/微信/短信...
    create_time = db.Column(db.DateTime, default=_now_bj)

    period = db.relationship('MarketingPeriod', backref=db.backref('executions', lazy=True))
    schedule = db.relationship('MarketingSchedule', backref=db.backref('executions', lazy=True))
    user = db.relationship('User', backref=db.backref('marketing_executions', lazy=True))
