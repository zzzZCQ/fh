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
    # 赠品信息
    has_gift = db.Column(db.Boolean, default=False)  # 是否有赠品
    gift_info = db.Column(db.String(200))  # 赠品内容
    # 物流信息
    logistics_status = db.Column(db.String(20), default='已发货')  # 已发货、派送中、待派送、已签收、拒签
    sign_time = db.Column(db.DateTime)  # 签收时间（顺丰API返回）
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
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    create_time = db.Column(db.DateTime, default=_now_bj)


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
