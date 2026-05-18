# -*- coding: utf-8 -*-
"""行为轨迹处理路由"""
import os
import re
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, flash, render_template, send_file
from flask_login import current_user
from openpyxl import load_workbook

from helpers import role_required, get_unread_count

bp = Blueprint('behavior', __name__)

# 行为轨迹文件存储目录（每个用户独立）
BEHAVIOR_DATA_DIR = os.path.join(os.path.dirname(__file__), 'behavior_tracking_data')


def get_user_behavior_dir(user_id):
    """获取用户的行为轨迹文件目录"""
    user_dir = os.path.join(BEHAVIOR_DATA_DIR, f'user_{user_id}')
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


def get_processed_dates_file(user_id):
    """获取用户的已处理日期文件路径"""
    user_dir = get_user_behavior_dir(user_id)
    return os.path.join(user_dir, 'processed_dates.txt')


@bp.route('/behavior_tracking')
@role_required('salesman')
def behavior_tracking_page():
    """行为轨迹处理页面"""
    user_dir = get_user_behavior_dir(current_user.id)

    # 获取已处理的日期
    processed_dates = []
    processed_file = get_processed_dates_file(current_user.id)
    if os.path.exists(processed_file):
        with open(processed_file, 'r', encoding='utf-8') as f:
            processed_dates = [line.strip() for line in f if line.strip()]

    # 扫描已上传的文件
    files = []
    has_base_file = False
    if os.path.exists(user_dir):
        files = [f for f in os.listdir(user_dir) if f.endswith('.xlsx') or f.endswith('.xls')]
        has_base_file = '行为轨迹表.xlsx' in files

    return render_template('behavior_tracking.html',
                           files=files,
                           has_base_file=has_base_file,
                           processed_dates=processed_dates,
                           unread_count=get_unread_count(current_user.id))


@bp.route('/behavior_tracking/upload', methods=['POST'])
@role_required('salesman')
def upload_behavior_files():
    """上传行为轨迹文件"""
    user_dir = get_user_behavior_dir(current_user.id)

    base_file = request.files.get('base_file')
    data_files = request.files.getlist('data_files')
    folder_files = request.files.getlist('folder_files')

    upload_count = 0

    # 上传基础表
    if base_file and base_file.filename:
        save_name = '行为轨迹表.xlsx'
        base_file.save(os.path.join(user_dir, save_name))
        upload_count += 1

    # 上传手动选择的数据文件
    for f in data_files:
        if f and f.filename:
            save_name = f.filename
            f.save(os.path.join(user_dir, save_name))
            upload_count += 1

    # 上传文件夹中选择的数据文件（只保留Excel）
    for f in folder_files:
        if f and f.filename:
            fname = f.filename
            # webkitdirectory会上传所有文件，只保留Excel
            if fname.lower().endswith('.xlsx') or fname.lower().endswith('.xls'):
                f.save(os.path.join(user_dir, fname))
                upload_count += 1

    if upload_count > 0:
        flash(f'上传成功！共 {upload_count} 个文件', 'success')
    else:
        flash('没有选择文件', 'warning')

    return redirect(url_for('behavior.behavior_tracking_page'))


@bp.route('/behavior_tracking/download')
@role_required('salesman')
def download_behavior_result():
    """下载处理后的行为轨迹表"""
    user_dir = get_user_behavior_dir(current_user.id)
    result_file = os.path.join(user_dir, '行为轨迹表.xlsx')

    if not os.path.exists(result_file):
        flash('没有可下载的结果文件', 'warning')
        return redirect(url_for('behavior.behavior_tracking_page'))

    return send_file(result_file, as_attachment=True,
                     download_name=f'行为轨迹表_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')


@bp.route('/behavior_tracking/clear_processed')
@role_required('salesman')
def clear_behavior_processed():
    """清空已处理记录"""
    processed_file = get_processed_dates_file(current_user.id)

    if os.path.exists(processed_file):
        os.remove(processed_file)
        flash('已清空处理记录，可以重新处理所有文件', 'success')
    else:
        flash('没有处理记录需要清空', 'info')

    return redirect(url_for('behavior.behavior_tracking_page'))


@bp.route('/behavior_tracking/process', methods=['POST'])
@role_required('salesman')
def process_behavior_tracking():
    """处理行为轨迹数据"""
    try:
        result = process_behavior_tracking_data(current_user.id)
        flash(result, 'success')
    except Exception as e:
        flash(f'处理失败：{str(e)}', 'danger')

    return redirect(url_for('behavior.behavior_tracking_page'))


def process_behavior_tracking_data(user_id):
    """核心处理逻辑"""
    user_dir = get_user_behavior_dir(user_id)

    DATA_START_ROW = 5
    TITLE_ROW = 4
    ORIGINAL_FILE = os.path.join(user_dir, "行为轨迹表.xlsx")
    PROCESSED_FILE = get_processed_dates_file(user_id)

    if not os.path.exists(ORIGINAL_FILE):
        raise Exception("找不到 行为轨迹表.xlsx，请先上传基础表")

    # 加载原文件
    wb = load_workbook(ORIGINAL_FILE)
    sheet = wb.active

    # 识别列结构
    nick_col = None
    col_map = {}
    for col_idx, cell_value in enumerate(sheet[TITLE_ROW], start=1):
        cell_str = str(cell_value.value or "").strip()
        if '昵称' in cell_str:
            nick_col = col_idx
        if cell_str.isdigit():
            col_map[int(cell_str)] = col_idx

    if nick_col is None:
        raise Exception(f"第{TITLE_ROW}行未找到'昵称'列")

    # 读取用户列表
    nick_row_map = {}
    empty_rows = []
    max_row = sheet.max_row
    max_col = sheet.max_column

    for row_idx in range(DATA_START_ROW, max_row + 1):
        nick_cell = sheet.cell(row=row_idx, column=nick_col)
        nick_value = str(nick_cell.value or "").strip()

        if nick_value == '':
            empty_rows.append(row_idx)
            continue

        clean_nick = clean_nickname(nick_value)

        if clean_nick in nick_row_map:
            for col_idx in range(1, max_col + 1):
                sheet.cell(row=row_idx, column=col_idx, value=None)
            empty_rows.append(row_idx)
        else:
            nick_row_map[clean_nick] = row_idx

    # 加载已处理日期
    processed_dates = set()
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
            processed_dates = set(line.strip() for line in f if line.strip())

    # 扫描完播文件
    all_user_data = {}
    new_processed_dates = []
    target_cols = []

    for f in os.listdir(user_dir):
        # 支持.xlsx和.xls格式，排除基础表
        if not (f.endswith('.xlsx') or f.endswith('.xls')) or f == '行为轨迹表.xlsx':
            continue

        date_tuple = extract_date_from_filename(f)
        if not date_tuple:
            continue

        month, day = date_tuple
        date_str = f"{month:02d}{day:02d}"
        if date_str in processed_dates:
            continue

        col_num = get_date_col_num(month, day)
        if col_num not in col_map:
            continue

        data_file_path = os.path.join(user_dir, f)
        try:
            users = read_user_list_from_file(data_file_path)
        except Exception as e:
            print(f"[WARNING] 读取文件 {f} 失败: {e}，尝试用另一种方式读取")
            # 如果openpyxl失败，尝试xlrd；反之亦然
            try:
                if data_file_path.endswith('.xlsx'):
                    import xlrd
                    wb = xlrd.open_workbook(data_file_path)
                    sheet = wb.sheet_by_index(0)
                    users = []
                    for row_idx in range(sheet.nrows):
                        cell_value = sheet.cell(row_idx, 0).value
                        if cell_value is not None and str(cell_value).strip() != '':
                            users.append(clean_nickname(cell_value))
                else:
                    wb = load_workbook(data_file_path, read_only=True, data_only=True)
                    sheet = wb.active
                    users = []
                    for row in sheet.iter_rows(min_row=1, max_col=1, values_only=True):
                        if row[0] is not None and str(row[0]).strip() != '':
                            users.append(clean_nickname(row[0]))
                    wb.close()
            except Exception as e2:
                print(f"[ERROR] 文件 {f} 两种方式都读取失败: {e2}")
                continue
        fill_value = 2 if '未完播' in f else 1

        for user in users:
            if user not in all_user_data:
                all_user_data[user] = {}
            all_user_data[user][col_num] = fill_value

        new_processed_dates.append(date_str)
        target_cols.append(col_num)

    if not target_cols:
        return "未找到新的有效数据文件"

    # 处理新增用户
    for new_user in all_user_data.keys():
        if new_user not in nick_row_map:
            if empty_rows:
                new_row = empty_rows.pop(0)
            else:
                max_row += 1
                new_row = max_row
            sheet.cell(row=new_row, column=nick_col, value=new_user)
            nick_row_map[new_user] = new_row

    # 填充数据
    for col_num in sorted(target_cols):
        col_idx = col_map[col_num]
        for nick, row_idx in nick_row_map.items():
            old_cell = sheet.cell(row=row_idx, column=col_idx)
            bracket_content = extract_bracket_content(old_cell.value)
            fill_value = all_user_data.get(nick, {}).get(col_num, 3)
            final_value = f"{fill_value} {bracket_content}".strip() if bracket_content else fill_value
            old_cell.value = final_value

    # 排序逻辑
    user_rows = []
    for nick, row_idx in nick_row_map.items():
        play_count = 0
        for col_num in col_map.keys():
            col_idx = col_map[col_num]
            cell_value = sheet.cell(row_idx, column=col_idx).value
            fill_num = extract_fill_value(cell_value)
            if fill_num == 1:
                play_count += 1
        row_data = []
        for col_idx in range(1, max_col + 1):
            row_data.append(sheet.cell(row_idx, column=col_idx).value)
        user_rows.append({
            'play_count': play_count,
            'nick': nick,
            'row_data': row_data
        })

    user_rows_sorted = sorted(user_rows, key=lambda x: (-x['play_count'], x['nick']))

    # 清空原用户行
    if max_row >= DATA_START_ROW:
        sheet.delete_rows(DATA_START_ROW, max_row - DATA_START_ROW + 1)

    # 写入排序后的行
    current_write_row = DATA_START_ROW
    for user in user_rows_sorted:
        for col_idx in range(1, max_col + 1):
            sheet.cell(row=current_write_row, column=col_idx, value=user['row_data'][col_idx - 1])
        current_write_row += 1

    # 保存已处理日期
    processed_dates.update(new_processed_dates)
    with open(PROCESSED_FILE, 'w', encoding='utf-8') as f:
        for d in sorted(processed_dates):
            f.write(f"{d}\n")

    # 保存文件
    wb.save(ORIGINAL_FILE)
    wb.close()

    return f"处理完成！填充了 {len(target_cols)} 个日期列，共 {len(user_rows_sorted)} 个用户，已按完播次数降序排序"


def clean_nickname(name):
    """昵称清洗"""
    if not isinstance(name, str):
        return str(name).strip()
    if '完' in name:
        name = name[name.index('完')+1:]
    name = re.sub(r'[0-9]{1,2}[./-月]?[0-9]{1,2}', '', name)
    prefixes = ['新-', '白-', 'SW-', 'AA-', '不要-', '白嫖-', 'SW', 'AA', '不要', '白嫖', '新', '白']
    for p in prefixes:
        if name.startswith(p):
            name = name[len(p):]
    name = re.sub(r'\(.*?\)', '', name)
    name = re.sub(r'（.*?）', '', name)
    return name.strip()


def extract_date_from_filename(filename):
    """从文件名提取日期"""
    try:
        if '未完播' in filename:
            prefix = filename.split('未完播')[0].strip()
        elif '完播' in filename:
            prefix = filename.split('完播')[0].strip()
        else:
            return None
        if prefix.isdigit():
            if len(prefix) == 3:
                return (int(prefix[0]), int(prefix[1:]))
            elif len(prefix) == 4:
                return (int(prefix[:2]), int(prefix[2:]))
        return None
    except:
        return None


def get_date_col_num(month, day):
    """计算日期对应的列号"""
    from datetime import datetime
    base_date = datetime(2025, 4, 14)
    return (datetime(2025, month, day) - base_date).days + 1


def read_user_list_from_file(file_path):
    """从文件读取用户列表（支持.xlsx和.xls）"""
    users = []

    if file_path.endswith('.xls') and not file_path.endswith('.xlsx'):
        # 使用xlrd读取.xls文件
        import xlrd
        wb = xlrd.open_workbook(file_path)
        sheet = wb.sheet_by_index(0)
        for row_idx in range(sheet.nrows):
            cell_value = sheet.cell(row_idx, 0).value
            if cell_value is not None and str(cell_value).strip() != '':
                users.append(clean_nickname(cell_value))
    else:
        # 使用openpyxl读取.xlsx文件
        wb = load_workbook(file_path, read_only=True, data_only=True)
        sheet = wb.active
        for row in sheet.iter_rows(min_row=1, max_col=1, values_only=True):
            if row[0] is not None and str(row[0]).strip() != '':
                users.append(clean_nickname(row[0]))
        wb.close()

    return users


def extract_bracket_content(text):
    """提取括号内容"""
    if not text:
        return ""
    text_str = str(text).strip()
    cn_bracket = re.search(r'（.*?）', text_str)
    if cn_bracket:
        return cn_bracket.group(0)
    en_bracket = re.search(r'\(.*?\)', text_str)
    if en_bracket:
        return en_bracket.group(0)
    return ""


def extract_fill_value(cell_value):
    """提取填充值"""
    if not cell_value:
        return None
    cell_str = str(cell_value).strip()
    num_match = re.match(r'^(\d+)', cell_str)
    if num_match:
        return int(num_match.group(1))
    return None
