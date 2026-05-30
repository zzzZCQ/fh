from flask import Blueprint, render_template, request, jsonify, abort, send_file
from flask_login import login_required, current_user
from models import db, WeworkCallRecord, _now_bj, User
from helpers import get_unread_count, role_required
from datetime import datetime, timedelta, date
import re
import os
import base64
from io import BytesIO
from PIL import Image
import threading
import time
from wework_partition import (
    save_record_to_partition, 
    get_records_by_date, 
    get_stats_by_date, 
    get_available_dates,
    get_partition_model
)

# 客户端连接状态管理
_client_connections = {}
_connections_lock = threading.Lock()
_config_change_time = None  # 配置变更时间戳

def get_call_recording_enabled():
    """从数据库获取通话读取功能配置"""
    try:
        from sqlalchemy import text
        result = db.session.execute(text("SELECT config_value FROM app_config WHERE config_key='call_recording_enabled'"))
        row = result.fetchone()
        if row:
            return row[0].lower() == 'true'
    except Exception as e:
        print(f"[配置] 读取通话读取配置失败: {e}")
    return False

def set_call_recording_enabled(enabled):
    """设置通话读取功能配置"""
    try:
        from sqlalchemy import text
        db.session.execute(text("UPDATE app_config SET config_value=:value WHERE config_key='call_recording_enabled'"), 
                         {'value': 'True' if enabled else 'False'})
        db.session.commit()
        return True
    except Exception as e:
        print(f"[配置] 设置通话读取配置失败: {e}")
        return False

# 通话读取功能配置
CALL_RECORDING_ENABLED = False

def init_call_recording_config(app):
    """初始化通话读取配置（需要在应用上下文中）"""
    global CALL_RECORDING_ENABLED
    with app.app_context():
        CALL_RECORDING_ENABLED = get_call_recording_enabled()
        print(f'[配置] 初始化通话读取配置: {"已启用" if CALL_RECORDING_ENABLED else "已停用"}')

def cleanup_stale_connections(timeout_seconds=2100):
    """清理超时的连接（默认35分钟）"""
    now = time.time()
    stale_ids = []
    with _connections_lock:
        for client_id, info in _client_connections.items():
            if now - info.get('last_heartbeat', 0) > timeout_seconds:
                stale_ids.append(client_id)
        for client_id in stale_ids:
            del _client_connections[client_id]
    return stale_ids

# 使用cnocr - 纯Python中文OCR
OCR_AVAILABLE = False
reader = None
_ocr_lock = threading.Lock()
_ocr_initialized = False

def init_ocr_async():
    """异步初始化OCR模块，后台线程"""
    global OCR_AVAILABLE, reader, _ocr_initialized
    time.sleep(5)  # 延时5秒启动，不影响主项目
    with _ocr_lock:
        if _ocr_initialized:
            return
        try:
            from cnocr import CnOcr
            
            print('[OCR] 正在后台初始化cnocr...')
            
            # 初始化cnocr
            try:
                reader = CnOcr()
                OCR_AVAILABLE = True
                print('[OCR] cnocr初始化成功！')
            except Exception as e:
                print(f'[OCR] cnocr初始化失败: {e}')
                
        except ImportError:
            print('[OCR] cnocr未安装，请运行: pip install cnocr')
        finally:
            _ocr_initialized = True

def start_ocr_init():
    """在后台启动OCR初始化"""
    thread = threading.Thread(target=init_ocr_async, daemon=True)
    thread.start()

# 启动OCR后台初始化线程
print('[OCR] OCR模块将在后台延时5秒启动...')
start_ocr_init()

bp = Blueprint('wework', __name__, url_prefix='/wework')


@bp.route('/dashboard')
@login_required
def dashboard():
    """企业微信通话记录页面 - 仅组别为1的管理员可见"""
    # 检查是否为管理员且组别为1
    if not current_user.has_role('admin'):
        abort(403)
    
    # 检查用户所属组别层级是否为1（超级管理员组，如"今禧"）
    if current_user.group and current_user.group.level != 1:
        abort(403)
    
    # 获取日期参数，默认今天
    target_date_str = request.args.get('date', '')
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = _now_bj().date()
    else:
        target_date = _now_bj().date()
    
    # 获取当前管理员可查看的上传者ID列表
    visible_uploader_ids = get_visible_uploader_ids(current_user)
    
    # 获取统计数据 - 只查分表
    try:
        stats = get_stats_by_date(target_date, visible_uploader_ids)
    except Exception as e:
        print(f'[查询统计] 异常: {e}')
        stats = {'total_count': 0, 'total_duration': 0, 'uploader_stats': []}
    
    # 构建统计数据，获取业务员名称
    uploader_stats = {}
    for uploader_id, call_count, total_duration in stats['uploader_stats']:
        if uploader_id:
            uploader = User.query.get(uploader_id)
            if uploader:
                uploader_name = uploader.name if uploader.name else uploader.username
            else:
                uploader_name = f'用户{uploader_id}'
        else:
            uploader_name = '未知用户'
        
        uploader_stats[uploader_id or 0] = {
            'name': uploader_name,
            'count': call_count,
            'duration': total_duration or 0
        }
    
    # 获取可用日期列表
    available_dates = get_available_dates()
    
    # 从数据库获取最新的通话读取配置
    call_recording_enabled = get_call_recording_enabled()
    
    return render_template('wework_call_dashboard.html',
        today_total_duration=stats['total_duration'],
        today_call_count=stats['total_count'],
        uploader_stats=uploader_stats,
        unread_count=get_unread_count(current_user.id),
        selected_date=target_date,
        available_dates=available_dates,
        call_recording_enabled=call_recording_enabled
    )


@bp.route('/api/heartbeat', methods=['POST'])
def client_heartbeat():
    """客户端心跳API - 客户端定期发送心跳表明在线"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无数据'}), 400
        
        client_id = data.get('client_id')
        user_id = data.get('user_id')
        user_name = data.get('user_name', '')
        computer_name = data.get('computer_name', '')
        
        if not client_id:
            return jsonify({'success': False, 'error': '缺少client_id'}), 400
        
        # 清理过期连接（客户端每30分钟发送一次心跳，超时设置为35分钟）
        cleanup_stale_connections(timeout_seconds=2100)
        
        # 更新连接状态：确保一个用户只保留一个最新连接
        with _connections_lock:
            # 先移除该用户的旧连接
            if user_id:
                old_client_ids = [
                    cid for cid, info in _client_connections.items()
                    if info.get('user_id') == user_id
                ]
                for old_cid in old_client_ids:
                    if old_cid != client_id:
                        del _client_connections[old_cid]
                        print(f'[客户端] 移除用户 {user_name} 的旧连接: {old_cid}')
            
            # 添加新连接
            _client_connections[client_id] = {
                'user_id': user_id,
                'user_name': user_name,
                'computer_name': computer_name,
                'last_heartbeat': time.time(),
                'ip_address': request.remote_addr
            }
        
        return jsonify({
            'success': True, 
            'online_count': len(_client_connections),
            'call_recording_enabled': CALL_RECORDING_ENABLED,
            'config_change_time': _config_change_time
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/disconnect', methods=['POST'])
def client_disconnect():
    """客户端断开连接API - 客户端退出时调用"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '无数据'}), 400
        
        client_id = data.get('client_id')
        
        if not client_id:
            return jsonify({'success': False, 'error': '缺少client_id'}), 400
        
        # 移除连接记录
        with _connections_lock:
            if client_id in _client_connections:
                del _client_connections[client_id]
                print(f'[客户端] 客户端断开连接: {client_id}')
        
        return jsonify({'success': True, 'online_count': len(_client_connections)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/call_recording/settings', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def call_recording_settings():
    """通话读取功能配置API"""
    global CALL_RECORDING_ENABLED
    
    if request.method == 'GET':
        # 每次GET都从数据库读取最新配置
        CALL_RECORDING_ENABLED = get_call_recording_enabled()
        return jsonify({
            'success': True,
            'call_recording_enabled': CALL_RECORDING_ENABLED
        })
    
    if request.method == 'POST':
        data = request.get_json()
        if 'enabled' in data:
            enabled = bool(data['enabled'])
            # 保存到数据库
            if set_call_recording_enabled(enabled):
                CALL_RECORDING_ENABLED = enabled
                import time
                global _config_change_time
                _config_change_time = time.time()
                print(f'[配置] 通话读取功能已{"启用" if CALL_RECORDING_ENABLED else "停用"}')
                return jsonify({
                    'success': True,
                    'call_recording_enabled': CALL_RECORDING_ENABLED,
                    'message': f'通话读取功能已{"启用" if CALL_RECORDING_ENABLED else "停用"}'
                })
            else:
                return jsonify({'success': False, 'error': '保存配置失败'}), 500
        return jsonify({'success': False, 'error': '缺少enabled参数'}), 400


@bp.route('/api/config_check', methods=['POST'])
def config_check():
    """客户端快速检查配置变更（轻量级接口）"""
    try:
        data = request.get_json() or {}
        client_id = data.get('client_id')
        
        return jsonify({
            'success': True,
            'call_recording_enabled': CALL_RECORDING_ENABLED,
            'config_change_time': _config_change_time
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/online_users', methods=['GET'])
@login_required
def get_online_users():
    """获取当前在线的用户列表"""
    # 清理过期连接（客户端每30分钟发送一次心跳，超时设置为35分钟）
    cleanup_stale_connections(timeout_seconds=2100)
    
    online_users = []
    with _connections_lock:
        for client_id, info in _client_connections.items():
            user_id = info.get('user_id')
            user_name = info.get('user_name', '')
            computer_name = info.get('computer_name', '')
            
            # 获取用户信息
            display_name = user_name
            if user_id:
                user = User.query.get(user_id)
                if user:
                    display_name = user.name if user.name else user.username
            
            online_users.append({
                'client_id': client_id,
                'user_id': user_id,
                'user_name': display_name,
                'computer_name': computer_name,
                'last_heartbeat': datetime.fromtimestamp(info['last_heartbeat']).strftime('%H:%M:%S')
            })
    
    # 按用户名排序
    online_users.sort(key=lambda x: x['user_name'] or '')
    
    return jsonify({
        'success': True,
        'online_users': online_users,
        'total': len(online_users)
    })


@bp.route('/api/records')
@login_required
def get_salesman_records():
    """获取指定业务员的通话记录（分页）"""
    uploader_id = request.args.get('uploader_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    date_str = request.args.get('date', '')
    
    # 验证每页数量
    if per_page not in [10, 50, 100]:
        per_page = 10
    
    # 获取目标日期
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            target_date = _now_bj().date()
    else:
        target_date = _now_bj().date()
    
    # 只查询分表
    try:
        PartitionModel = get_partition_model(target_date)
        query = PartitionModel.query
        if uploader_id is not None:
            query = query.filter(PartitionModel.uploader_id == uploader_id)
        
        pagination = query.order_by(PartitionModel.call_start_time.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        records = []
        for record in pagination.items:
            records.append({
                'id': record.id,
                'user_name': record.user_name,
                'call_start_time': record.call_start_time.strftime('%H:%M:%S') if record.call_start_time else '',
                'call_end_time': record.call_end_time.strftime('%H:%M:%S') if record.call_end_time else '',
                'call_duration_seconds': record.call_duration_seconds or 0,
                'status': record.status
            })
        
        return jsonify({
            'success': True,
            'records': records,
            'total': pagination.total,
            'pages': pagination.pages,
            'page': pagination.page,
            'per_page': per_page,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        })
    except Exception as e:
        print(f'[查询记录] 分表查询失败: {e}')
        return jsonify({
            'success': True,
            'records': [],
            'total': 0,
            'pages': 0,
            'page': 1,
            'per_page': per_page,
            'has_next': False,
            'has_prev': False
        })


@bp.route('/api/export')
@login_required
def export_records():
    """导出指定日期的通话记录为Excel"""
    if not current_user.has_role('admin'):
        abort(403)
    
    date_str = request.args.get('date', '')
    
    if not date_str:
        return jsonify({'success': False, 'error': '请指定日期'}), 400
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': '日期格式错误'}), 400
    
    # 获取可见的上传者ID
    visible_uploader_ids = get_visible_uploader_ids(current_user)
    
    # 只查询分表
    records = []
    try:
        records = get_records_by_date(target_date, visible_uploader_ids=visible_uploader_ids)
    except Exception as e:
        print(f'[导出] 查询数据失败: {e}')
        records = []
    
    # 导出Excel
    try:
        import openpyxl
        from io import BytesIO
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '通话记录'
        
        # 表头
        headers = ['ID', '业务员', '联系人', '开始时间', '结束时间', '通话时长(秒)', '状态', '上传时间']
        ws.append(headers)
        
        # 数据
        for record in records:
            uploader_name = ''
            if record.uploader_id:
                uploader = User.query.get(record.uploader_id)
                if uploader:
                    uploader_name = uploader.name if uploader.name else uploader.username
            
            row = [
                record.id,
                uploader_name,
                record.user_name,
                record.call_start_time.strftime('%Y-%m-%d %H:%M:%S') if record.call_start_time else '',
                record.call_end_time.strftime('%Y-%m-%d %H:%M:%S') if record.call_end_time else '',
                record.call_duration_seconds or 0,
                '已完成' if record.status == 'completed' else '进行中',
                record.upload_time.strftime('%Y-%m-%d %H:%M:%S') if record.upload_time else ''
            ]
            ws.append(row)
        
        # 调整列宽
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column].width = adjusted_width
        
        # 保存到内存
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        # 发送文件
        filename = f'通话记录_{target_date.strftime("%Y%m%d")}.xlsx'
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    except ImportError:
        return jsonify({'success': False, 'error': 'openpyxl未安装，请联系管理员'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def get_visible_uploader_ids(admin_user):
    """获取管理员可查看的上传者ID列表"""
    try:
        # 超级管理员可以查看所有记录
        if admin_user.username == 'admin':
            return None
        
        # 普通管理员：查看本组用户 + 自己上传的记录
        visible_ids = [admin_user.id]
        
        if admin_user.group:
            for user in admin_user.group.users:
                if user.id != admin_user.id and user.is_active:
                    visible_ids.append(user.id)
        
        return visible_ids
    except Exception:
        return [admin_user.id]


@bp.route('/api/record', methods=['POST'])
def create_record():
    """创建通话记录API（供客户端调用）"""
    try:
        data = request.get_json()
        if not data:
            print('[WEWORK] 警告: 接收到空数据')
            return jsonify({'success': False, 'error': '无数据'}), 400
        
        print(f'[WEWORK] 接收到请求: {data}')
        
        user_name = data.get('user_name')
        call_start_time_str = data.get('call_start_time')
        call_end_time_str = data.get('call_end_time')
        uploader_id = data.get('uploader_id')
        
        if not user_name or not call_start_time_str:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400
        
        # 准备保存到分表的数据
        save_data = {
            'user_name': user_name,
            'call_start_time': call_start_time_str,
            'call_end_time': call_end_time_str,
            'uploader_id': uploader_id
        }
        
        # 保存到分表
        success, record_id, action, error = save_record_to_partition(save_data)
        
        if success:
            print(f'[WEWORK] 创建记录成功: ID={record_id}, 动作={action}')
            return jsonify({'success': True, 'id': record_id, 'action': action})
        else:
            print(f'[WEWORK] 创建记录失败: {error}')
            return jsonify({'success': False, 'error': error}), 500
    
    except Exception as e:
        db.session.rollback()
        print(f'[WEWORK] 创建记录失败: {str(e)}')
        import traceback
        print(f'[WEWORK] 错误详情:\n{traceback.format_exc()}')
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/record/<int:record_id>', methods=['PUT'])
@login_required
def update_record(record_id):
    """更新通话记录"""
    if not current_user.has_role('admin'):
        return jsonify({'success': False, 'error': '无权限'}), 403
    
    record = WeworkCallRecord.query.get_or_404(record_id)
    
    try:
        data = request.get_json()
        
        if 'user_name' in data:
            record.user_name = data['user_name']
        
        if 'call_start_time' in data:
            record.call_start_time = datetime.fromisoformat(data['call_start_time'])
        
        if 'call_end_time' in data:
            if data['call_end_time']:
                record.call_end_time = datetime.fromisoformat(data['call_end_time'])
            else:
                record.call_end_time = None
        
        if record.call_start_time and record.call_end_time:
            record.call_duration_seconds = int((record.call_end_time - record.call_start_time).total_seconds())
            record.status = 'completed'
        else:
            record.call_duration_seconds = None
            record.status = 'ongoing'
        
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/record/<int:record_id>', methods=['DELETE'])
@login_required
def delete_record(record_id):
    """删除通话记录"""
    if not current_user.has_role('admin'):
        return jsonify({'success': False, 'error': '无权限'}), 403
    
    record = WeworkCallRecord.query.get_or_404(record_id)
    
    try:
        db.session.delete(record)
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/ocr', methods=['POST'])
def ocr_image():
    """OCR识别接口"""
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'success': False, 'error': '缺少图片数据'}), 400
        
        image_data = data['image']
        
        # 解码base64图片
        try:
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            img_bytes = base64.b64decode(image_data)
            img = Image.open(BytesIO(img_bytes))
        except Exception as e:
            print(f'[OCR] 图片解码失败: {str(e)}')
            return jsonify({'success': False, 'error': f'图片解码失败: {str(e)}'}), 400
        
        # 保存截图到服务器（方便调试）
        screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots')
        print(f'[OCR] 截图目录: {screenshot_dir}')
        os.makedirs(screenshot_dir, exist_ok=True)
        
        # 生成唯一文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        screenshot_path = os.path.join(screenshot_dir, f'screenshot_{timestamp}.png')
        print(f'[OCR] 准备保存截图到: {screenshot_path}')
        img.save(screenshot_path)
        print(f'[OCR] 截图保存成功，大小: {len(img_bytes)} bytes')
        
        # 生成可访问的URL
        screenshot_url = f'/wework/screenshot/{timestamp}.png'
        print(f'[OCR] 截图已保存: {screenshot_path}')
        
        text = ''
        contact_name = None
        if OCR_AVAILABLE and reader:
            try:
                # cnocr识别
                result = reader.ocr(img)
                print(f'[OCR] 原始识别结果: {result}')
                
                # 合并结果 - cnocr返回的是字典列表，每个字典包含text字段
                if result:
                    # 处理两种可能的格式
                    if isinstance(result[0], dict) and 'text' in result[0]:
                        # 新版cnocr格式: [{'text': 'xxx', 'score': xxx, ...}, ...]
                        lines = [item['text'] for item in result]
                    else:
                        # 旧版格式: [[(char1, score1), (char2, score2), ...], ...]
                        lines = [''.join([char[0] for char in line]) for line in result]
                    text = '\n'.join(lines)
                
                print(f'[OCR] 识别结果: {repr(text[:500])}')
                
                # 提取联系人名称
                contact_name = extract_contact_name(text)
                if contact_name:
                    print(f'[OCR] 最终提取联系人: {contact_name}')
            except Exception as e:
                print(f'[OCR] 识别失败: {str(e)}')
                pass
        else:
            print('[OCR] OCR未就绪，跳过识别')
        
        # 异步删除截图文件
        def delete_screenshot_async(path):
            try:
                import time
                time.sleep(5)  # 延迟5秒后删除，确保客户端已获取结果
                if os.path.exists(path):
                    os.remove(path)
                    print(f'[OCR] 截图已异步删除: {path}')
            except Exception as e:
                print(f'[OCR] 删除截图失败: {e}')

        # 启动异步删除线程
        import threading
        delete_thread = threading.Thread(target=delete_screenshot_async, args=(screenshot_path,))
        delete_thread.daemon = True
        delete_thread.start()
        
        return jsonify({
            'success': True, 
            'text': text, 
            'contact_name': contact_name,
            'screenshot_url': screenshot_url
        })
    
    except Exception as e:
        print(f'[OCR] 接口异常: {str(e)}')
        return jsonify({'success': True, 'text': ''})  # 出错也返回空，不中断流程


@bp.route('/screenshot/<filename>')
def serve_screenshot(filename):
    """提供截图预览"""
    screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots')
    file_path = os.path.join(screenshot_dir, f'screenshot_{filename}')
    
    if not os.path.exists(file_path):
        abort(404)
    
    return send_file(file_path, mimetype='image/png')


def extract_contact_name(text):
    """从OCR结果中提取联系人名称"""
    if not text:
        return None
    
    # 清理文本：移除常见的前缀字符（如X、数字等）
    # 匹配模式：数字+完、字母+数字+完等前缀 + 联系人名称@微信
    # 例如：0522完清酒@微信 -> 清酒, SB0211完苗先生@微信 -> 苗先生
    
    # 首先尝试匹配带前缀的格式：任意字符+完+联系人@微信
    prefix_pattern = r'(?:[A-Za-z]*\d+[A-Za-z]*完)?([^\s@]{2,10})@(?:微信|企业微信)'
    match = re.search(prefix_pattern, text)
    if match:
        name = match.group(1).strip()
        # 清理可能残留的"完"字
        name = name.replace('完', '')
        if name and len(name) >= 2:
            print(f'[OCR] 提取联系人（带前缀格式）: {name}')
            return name
    
    # 标准格式：联系人@微信
    patterns = [
        (r'([^\s@]{2,10})@(?:微信|企业微信)', 1),
        (r'(?:正在)?呼叫\s*([^\s，。,，]{2,10})', 1),
        (r'(?:正在)?拨打\s*([^\s，。,，]{2,10})', 1),
        (r'(?:与|和)\s*([^\s，。,，]{2,10}?)(?:的)?(?:通话|视频)', 1),
    ]
    
    for pattern, group in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(group).strip()
            exclude_words = ['语音通话', '视频通话', '正在呼叫', '企业微信', '微信', '通话', '接通', '等待', '结束', '取消', '的', '和', '与']
            for word in exclude_words:
                name = name.replace(word, '')
            name = re.sub(r'[^\w\u4e00-\u9fa5]', '', name)
            if name and len(name) >= 2:
                print(f'[OCR] 提取联系人: {name}')
                return name
    
    # 尝试提取中文名称
    matches = re.findall(r'[\u4e00-\u9fa5]{2,10}', text)
    exclude_list = ['语音通话', '视频通话', '正在呼叫', '企业微信', '微信', '通话', '正在']
    for m in matches:
        if m not in exclude_list:
            print(f'[OCR] 提取联系人（中文匹配）: {m}')
            return m
    
    return None


def format_duration(seconds):
    """格式化时长显示"""
    if not seconds:
        return '-'
    minutes, secs = divmod(seconds, 60)
    hours, mins = divmod(minutes, 60)
    if hours > 0:
        return f'{hours}时{mins}分{secs}秒'
    elif minutes > 0:
        return f'{mins}分{secs}秒'
    else:
        return f'{secs}秒'
