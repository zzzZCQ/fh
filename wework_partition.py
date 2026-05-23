"""
企业微信通话记录分表管理模块
按日期分表存储，自动创建和管理表结构
"""
from datetime import datetime, date, timedelta
from models import db, _now_bj, User
from sqlalchemy import inspect, func


def get_table_suffix(dt):
    """根据日期获取表后缀格式: YYYYMMDD"""
    if isinstance(dt, (datetime, date)):
        return dt.strftime('%Y%m%d')
    return dt


def get_partition_model(dt):
    """
    根据日期获取对应的分表模型类
    自动创建表结构（如果不存在）
    """
    suffix = get_table_suffix(dt)
    table_name = f'wework_call_record_{suffix}'
    
    # 检查表是否已经存在
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    table_exists = table_name in tables
    
    # 动态创建模型类
    class WeworkCallRecordPartition(db.Model):
        __tablename__ = table_name
        __table_args__ = {'extend_existing': True}
        
        id = db.Column(db.Integer, primary_key=True)
        user_name = db.Column(db.String(100), nullable=False)
        call_start_time = db.Column(db.DateTime, nullable=False)
        call_end_time = db.Column(db.DateTime)
        call_duration_seconds = db.Column(db.Integer)
        status = db.Column(db.String(20), default='ongoing')
        uploader_id = db.Column(db.Integer, db.ForeignKey('user.id'))
        upload_time = db.Column(db.DateTime, default=_now_bj)
        create_time = db.Column(db.DateTime, default=_now_bj)
        
        # 关联关系
        uploader = db.relationship('User')
    
    # 创建表结构（如果不存在）
    if not table_exists:
        try:
            db.create_all()
        except Exception as e:
            print(f'[分表] 创建表 {table_name} 已存在或失败: {e}')
    
    return WeworkCallRecordPartition


def save_record_to_partition(data):
    """
    保存通话记录到对应的分表中
    返回 (success, record_id, action, error)
    """
    try:
        call_start_time = data.get('call_start_time')
        if isinstance(call_start_time, str):
            call_start_time = datetime.fromisoformat(call_start_time)
        
        # 根据通话开始时间确定分表
        PartitionModel = get_partition_model(call_start_time)
        
        user_name = data.get('user_name')
        uploader_id = data.get('uploader_id')
        
        # 检查是否已经存在进行中的相同通话记录
        # 使用更宽松的匹配条件：相同用户、相同上传者、时间间隔在5秒内的进行中记录
        existing = PartitionModel.query.filter(
            PartitionModel.user_name == user_name,
            PartitionModel.uploader_id == uploader_id,
            PartitionModel.status == 'ongoing',
            PartitionModel.call_start_time >= call_start_time - timedelta(seconds=5),
            PartitionModel.call_start_time <= call_start_time + timedelta(seconds=5)
        ).first()
        
        if existing:
            call_end_time = data.get('call_end_time')
            if call_end_time:
                if isinstance(call_end_time, str):
                    call_end_time = datetime.fromisoformat(call_end_time)
                
                # 更新结束时间（只在尚未设置结束时间时更新）
                if not existing.call_end_time or existing.call_end_time > call_end_time:
                    existing.call_end_time = call_end_time
                    if call_start_time and call_end_time:
                        existing.call_duration_seconds = int(
                            (call_end_time - call_start_time).total_seconds()
                        )
                        existing.status = 'completed'
                    db.session.commit()
                    print(f'[分表] 更新通话记录结束时间: ID={existing.id}')
                    return True, existing.id, 'updated', None
            return True, existing.id, 'existing', None
        
        # 创建新记录
        call_end_time = data.get('call_end_time')
        if call_end_time and isinstance(call_end_time, str):
            call_end_time = datetime.fromisoformat(call_end_time)
        
        call_duration_seconds = None
        status = 'ongoing'
        if call_start_time and call_end_time:
            call_duration_seconds = int((call_end_time - call_start_time).total_seconds())
            status = 'completed'
        
        record = PartitionModel(
            user_name=user_name,
            call_start_time=call_start_time,
            call_end_time=call_end_time,
            call_duration_seconds=call_duration_seconds,
            status=status,
            uploader_id=uploader_id
        )
        db.session.add(record)
        db.session.commit()
        return True, record.id, 'created', None
        
    except Exception as e:
        db.session.rollback()
        print(f'[分表] 保存记录失败: {e}')
        return False, None, 'error', str(e)


def get_records_by_date(target_date, uploader_id=None, visible_uploader_ids=None):
    """
    获取指定日期的通话记录
    """
    # 先检查分表是否存在
    suffix = get_table_suffix(target_date)
    table_name = f'wework_call_record_{suffix}'
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if table_name not in tables:
        return []
    
    PartitionModel = get_partition_model(target_date)
    
    query = PartitionModel.query
    
    if uploader_id is not None:
        query = query.filter_by(uploader_id=uploader_id)
    
    if visible_uploader_ids is not None:
        query = query.filter(PartitionModel.uploader_id.in_(visible_uploader_ids))
    
    return query.order_by(PartitionModel.call_start_time.desc()).all()


def get_stats_by_date(target_date, visible_uploader_ids=None):
    """
    获取指定日期的统计数据
    """
    # 先检查分表是否存在
    suffix = get_table_suffix(target_date)
    table_name = f'wework_call_record_{suffix}'
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if table_name not in tables:
        return {
            'total_count': 0,
            'total_duration': 0,
            'uploader_stats': []
        }
    
    PartitionModel = get_partition_model(target_date)
    
    query = PartitionModel.query
    
    if visible_uploader_ids is not None:
        query = query.filter(PartitionModel.uploader_id.in_(visible_uploader_ids))
    
    total_count = query.count()
    total_duration = query.with_entities(
        func.sum(PartitionModel.call_duration_seconds)
    ).scalar() or 0
    
    # 按业务员统计
    stats_query = db.session.query(
        PartitionModel.uploader_id,
        func.count(PartitionModel.id).label('call_count'),
        func.sum(PartitionModel.call_duration_seconds).label('total_duration')
    )
    
    if visible_uploader_ids is not None:
        stats_query = stats_query.filter(PartitionModel.uploader_id.in_(visible_uploader_ids))
    
    stats_query = stats_query.group_by(PartitionModel.uploader_id).order_by(
        func.sum(PartitionModel.call_duration_seconds).desc()
    )
    
    stats = stats_query.all()
    
    return {
        'total_count': total_count,
        'total_duration': total_duration,
        'uploader_stats': stats
    }


def get_available_dates():
    """
    获取所有已存在分表的日期列表
    """
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    dates = []
    prefix = 'wework_call_record_'
    for table in tables:
        if table.startswith(prefix):
            date_str = table[len(prefix):]
            if len(date_str) == 8 and date_str.isdigit():
                try:
                    dt = datetime.strptime(date_str, '%Y%m%d').date()
                    dates.append(dt)
                except ValueError:
                    pass
    
    dates.sort(reverse=True)
    return dates
