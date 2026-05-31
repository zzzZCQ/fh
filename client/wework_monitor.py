# -*- coding: utf-8 -*-
"""企业微信通话监控模块 - 使用简化的OCR方案"""
import threading
import time
import requests
import datetime
import win32gui
import win32con
import win32ui
import win32api
import getpass
import re
import os
import json
import subprocess
import base64
import socket
import uuid
import ctypes
from io import BytesIO
from packaging import version as version_parser

from PIL import Image, ImageEnhance, ImageGrab
from settings import Settings

# 版本号
CLIENT_VERSION = "1.0.1"


class WeworkCallMonitor:
    """企业微信通话监控类"""
    
    def __init__(self):
        self.settings = Settings()
        self.running = False
        self.thread = None
        self.current_call = None
        self.call_history = []
        self.local_user = getpass.getuser()
        self.computer_name = socket.gethostname()
        self.client_id = str(uuid.uuid4())
        self.last_heartbeat_time = 0
        self.last_config_check_time = 0
        self.config_check_interval = 30  # 每30秒检查一次配置变更
        self.heartbeat_interval = 1800  # 每30分钟发送一次心跳
        self.user_id = self.settings.get('user_id')
        self.user_name = self.settings.get('username', self.local_user)
        self.log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wework_monitor.log')
        self.call_recording_enabled = True  # 服务端配置的通话读取功能状态
        self.config_change_time = None  # 上次的配置变更时间戳
    
    def _log(self, message, level='INFO'):
        """记录日志到文件"""
        try:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_line = f'[{timestamp}] [{level}] {message}\n'
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line)
        except Exception:
            pass
    
    def send_heartbeat(self):
        """发送心跳到服务器，并接收服务端配置"""
        try:
            server_url = self.settings.get('server_url', 'http://192.168.100.22:5000')
            heartbeat_url = f"{server_url}/wework/api/heartbeat"
            
            data = {
                'client_id': self.client_id,
                'user_id': self.user_id,
                'user_name': self.user_name,
                'computer_name': self.computer_name,
                'client_version': CLIENT_VERSION
            }
            
            self._log(f'发送心跳到 {heartbeat_url}')
            response = requests.post(heartbeat_url, json=data, timeout=5)
            
            # 检查版本是否过旧（403状态码）
            if response.status_code == 403:
                result = response.json()
                error_msg = result.get('error', '')
                if '版本过旧' in error_msg:
                    server_version = result.get('server_version', '1.0.0')
                    min_version = result.get('min_supported_version', '1.0.0')
                    release_date = result.get('release_date', '')
                    
                    # 显示错误并退出
                    from PyQt5.QtWidgets import QMessageBox, QApplication
                    import sys
                    import os
                    
                    app = QApplication.instance()
                    if not app:
                        app = QApplication(sys.argv)
                    
                    QMessageBox.critical(
                        None, 
                        "版本过旧", 
                        f"客户端版本 v{CLIENT_VERSION} 过旧！\n"
                        f"最低支持版本: v{min_version}\n"
                        f"服务器版本: v{server_version}\n"
                        f"发布日期: {release_date}\n\n"
                        f"请联系管理员获取新版本！"
                    )
                    
                    # 强制退出
                    os._exit(1)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    # 读取服务端配置的通话读取功能状态
                    if 'call_recording_enabled' in result:
                        new_enabled = result['call_recording_enabled']
                        if new_enabled != self.call_recording_enabled:
                            self.call_recording_enabled = new_enabled
                            status_text = '启用' if self.call_recording_enabled else '停用'
                            print(f'🔧 服务端通知：通话读取功能已{status_text}')
                            self._log(f'服务端配置更新：通话读取功能已{status_text}')
                    
                    # 更新配置变更时间戳
                    if 'config_change_time' in result:
                        self.config_change_time = result['config_change_time']
                    
                    self._log(f'心跳发送成功')
                    return True
                else:
                    self._log(f'心跳发送失败: {result.get("error")}', 'ERROR')
            else:
                self._log(f'心跳请求失败，状态码: {response.status_code}', 'ERROR')
            return False
        except Exception as e:
            self._log(f'心跳发送异常: {e}', 'ERROR')
            print(f'心跳发送失败: {e}')
            return False
    
    def check_config_change(self):
        """快速检查配置变更（轻量级接口）"""
        try:
            server_url = self.settings.get('server_url', 'http://192.168.100.22:5000')
            config_check_url = f"{server_url}/wework/api/config_check"
            
            data = {
                'client_id': self.client_id
            }
            
            response = requests.post(config_check_url, json=data, timeout=5)
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    # 检查配置变更时间戳
                    new_change_time = result.get('config_change_time')
                    if new_change_time != self.config_change_time:
                        # 配置已变更
                        self.config_change_time = new_change_time
                        new_enabled = result.get('call_recording_enabled', False)
                        if new_enabled != self.call_recording_enabled:
                            self.call_recording_enabled = new_enabled
                            status_text = '启用' if self.call_recording_enabled else '停用'
                            print(f'🔧 配置已变更：通话读取功能已{status_text}')
                            self._log(f'快速配置检查：通话读取功能已{status_text}')
                    return True
            return False
        except Exception as e:
            # 配置检查失败不影响主流程，静默处理
            return False
    
    def capture_window(self, hwnd):
        """使用多种方式截取指定窗口，自动尝试不同方法"""
        try:
            # 确保窗口可见
            if not win32gui.IsWindowVisible(hwnd):
                print('⚠️ 窗口不可见')
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                time.sleep(0.3)
            
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top
            
            print(f'📐 窗口区域: {width}x{height}')
            
            img = None
            
            # 方法1: 优先使用 MSS 快速截图（对硬件加速窗口更兼容）
            print('🔧 尝试方法1: MSS 快速截图')
            try:
                import mss
                import mss.tools
                
                # 先让窗口置顶
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.5)
                
                with mss.mss() as sct:
                    # 定义区域
                    monitor = {"top": top, "left": left, "width": width, "height": height}
                    
                    # 截图
                    sct_img = sct.grab(monitor)
                    
                    # 转换为 PIL Image
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    print('✅ 方法1: MSS 成功')
            except ImportError:
                print('⚠️ MSS 库未安装，跳过方法1')
                img = None
            except Exception as e:
                print(f'❌ 方法1: MSS 失败: {e}')
                img = None
            
            # 检查图片是否是黑屏
            if img is not None:
                non_black_pixels = 0
                total_pixels = img.width * img.height
                pixels = img.load()
                for x in range(min(100, img.width)):
                    for y in range(min(100, img.height)):
                        r, g, b = pixels[x, y]
                        if r > 10 or g > 10 or b > 10:
                            non_black_pixels += 1
                
                non_black_ratio = non_black_pixels / 10000
                print(f'📊 非黑色像素比例: {non_black_ratio:.2%}')
                
                if non_black_ratio < 0.01:
                    print('⚠️ 检测到黑屏')
                    img = None
            
            # 方法2: 如果方法1失败，尝试 PrintWindow API
            if img is None:
                print('🔧 尝试方法2: PrintWindow')
                try:
                    hwndDC = win32gui.GetWindowDC(hwnd)
                    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
                    saveDC = mfcDC.CreateCompatibleDC()
                    
                    saveBitMap = win32ui.CreateBitmap()
                    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
                    saveDC.SelectObject(saveBitMap)
                    
                    # 使用 PrintWindow 拷贝窗口内容
                    result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 0x01)
                    
                    if result == 1:
                        bmpinfo = saveBitMap.GetInfo()
                        bmpstr = saveBitMap.GetBitmapBits(True)
                        img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)
                        print('✅ 方法2: PrintWindow 成功')
                    
                    win32gui.DeleteObject(saveBitMap.GetHandle())
                    saveDC.DeleteDC()
                    mfcDC.DeleteDC()
                    win32gui.ReleaseDC(hwnd, hwndDC)
                except Exception as e:
                    print(f'❌ 方法2: PrintWindow 失败: {e}')
                    img = None
            
            # 检查图片是否是黑屏
            if img is not None:
                non_black_pixels = 0
                pixels = img.load()
                for x in range(min(100, img.width)):
                    for y in range(min(100, img.height)):
                        r, g, b = pixels[x, y]
                        if r > 10 or g > 10 or b > 10:
                            non_black_pixels += 1
                
                non_black_ratio = non_black_pixels / 10000
                print(f'📊 非黑色像素比例: {non_black_ratio:.2%}')
                
                if non_black_ratio < 0.01:
                    print('⚠️ 检测到黑屏')
                    img = None
            
            # 方法3: 如果方法2失败，使用传统的 BitBlt
            if img is None:
                print('🔧 尝试方法3: BitBlt')
                try:
                    hwndDC = win32gui.GetWindowDC(hwnd)
                    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
                    saveDC = mfcDC.CreateCompatibleDC()
                    
                    saveBitMap = win32ui.CreateBitmap()
                    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
                    saveDC.SelectObject(saveBitMap)
                    
                    # 使用 BitBlt 拷贝窗口内容
                    saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)
                    
                    bmpinfo = saveBitMap.GetInfo()
                    bmpstr = saveBitMap.GetBitmapBits(True)
                    img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)
                    print('✅ 方法3: BitBlt 成功')
                    
                    win32gui.DeleteObject(saveBitMap.GetHandle())
                    saveDC.DeleteDC()
                    mfcDC.DeleteDC()
                    win32gui.ReleaseDC(hwnd, hwndDC)
                except Exception as e:
                    print(f'❌ 方法3: BitBlt 失败: {e}')
                    img = None
            
            # 检查图片是否是黑屏
            if img is not None:
                non_black_pixels = 0
                pixels = img.load()
                for x in range(min(100, img.width)):
                    for y in range(min(100, img.height)):
                        r, g, b = pixels[x, y]
                        if r > 10 or g > 10 or b > 10:
                            non_black_pixels += 1
                
                non_black_ratio = non_black_pixels / 10000
                print(f'📊 非黑色像素比例: {non_black_ratio:.2%}')
                
                if non_black_ratio < 0.01:
                    print('⚠️ 检测到黑屏')
                    img = None
            
            # 方法4: 如果黑屏，尝试全屏截图方式
            if img is None:
                print('🔧 尝试方法4: ImageGrab 全屏')
                try:
                    try:
                        from PIL import ImageGrab
                    except ImportError:
                        import ImageGrab
                    
                    # 先让窗口置顶
                    win32gui.SetForegroundWindow(hwnd)
                    time.sleep(0.5)
                    
                    # 全屏截图然后裁剪
                    img_full = ImageGrab.grab()
                    img = img_full.crop((left, top, right, bottom))
                    print('✅ 方法4: ImageGrab 成功')
                except Exception as e:
                    print(f'❌ 方法4: ImageGrab 失败: {e}')
                    img = None
            
            if img is None:
                print('❌ 所有截图方法都失败了')
                self._log('所有截图方法都失败', 'ERROR')
                return None
            
            # 不再裁剪，保留完整窗口内容，确保能截取到用户名
            print(f'📐 保留完整截图: {img.width}x{img.height}')
            
            # 适度放大，提高识别率
            scale_factor = 2.0
            new_width = int(img.width * scale_factor)
            new_height = int(img.height * scale_factor)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 适度增强对比度
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)
            
            # 增强锐度
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.3)
            
            # 不保存到磁盘，直接返回图片对象
            return img
            
        except Exception as e:
            print(f'截图失败: {e}')
            import traceback
            print(f'错误详情: {traceback.format_exc()}')
            self._log(f'截图失败: {e}', 'ERROR')
            return None
    
    def windows_ocr(self, img):
        """上传图片到服务器进行OCR识别，返回提取的联系人名称"""
        try:
            if img is None:
                self._log(f'OCR失败: 图片为空', 'ERROR')
                return None
            
            server_url = self.settings.get('server_url', 'http://192.168.100.22:5000')
            ocr_url = f"{server_url}/wework/api/ocr"
            
            # 将PIL Image直接转为base64，不保存到磁盘
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=80)
            img_data = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            self._log(f'发送OCR请求到 {ocr_url}')
            # 发送请求
            result = requests.post(
                ocr_url,
                json={'image': img_data},
                timeout=30
            )
            
            if result.status_code == 200:
                data = result.json()
                if data.get('success'):
                    text = data.get('text', '')
                    contact_name = data.get('contact_name')
                    self._log(f'OCR识别成功，提取文本: {repr(text[:200])}')
                    print(f'📝 服务器OCR输出: {repr(text[:500])}')
                    if contact_name:
                        self._log(f'提取到联系人: {contact_name}')
                        print(f'🎯 服务器提取联系人: {contact_name}')
                        return contact_name
                    else:
                        self._log('OCR未提取到联系人')
                        print('⚠️ 服务器未提取到联系人')
                        return None
                else:
                    error_msg = data.get('error', '未知错误')
                    self._log(f'OCR识别失败: {error_msg}', 'ERROR')
                    print(f'⚠️ 服务器OCR失败: {error_msg}')
            else:
                self._log(f'OCR请求失败，状态码: {result.status_code}', 'ERROR')
                print(f'⚠️ 服务器OCR请求失败，状态码: {result.status_code}')
            
        except Exception as e:
            self._log(f'OCR异常: {e}', 'ERROR')
            print(f'OCR失败: {e}')
        
        return None
    
    def extract_contact_name(self, text):
        """从OCR结果中提取联系人名称"""
        if not text:
            return None
        
        exclude_words = ['语音通话', '视频通话', '正在呼叫', '企业微信', '微信', '通话', '接通', 
                       '等待', '结束', '取消', '的', '和', '与', '添加', '成员', '搜索', 
                       '通讯录', '聊天', '发现', '我', '工作台']
        
        patterns = [
            (r'([^@\s]+)@(?:微信|企业微信)', 1),
            (r'(?:正在)?呼叫\s*([^@\s，。,，]+)', 1),
            (r'(?:正在)?拨打\s*([^@\s，。,，]+)', 1),
            (r'(?:与|和)\s*([^\s，。,，]+?)(?:的)?(?:通话|视频)', 1),
            (r'^([^\n\r]{2,8})$', 1),
        ]
        
        # 尝试正则表达式匹配
        for pattern, group in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(group).strip()
                name = re.sub(r'[^\w\u4e00-\u9fa5]', '', name)
                if name and len(name) >= 2 and name not in exclude_words:
                    print(f'🎯 正则提取到联系人: {name}')
                    return name
        
        # 提取所有可能的中文词
        matches = re.findall(r'[\u4e00-\u9fa5]{2,10}', text)
        for m in matches:
            if m not in exclude_words:
                print(f'🎯 中文词提取到联系人: {m}')
                return m
        
        # 提取所有字母数字组合
        matches = re.findall(r'[a-zA-Z0-9\u4e00-\u9fa5]{2,20}', text)
        for m in matches:
            if m not in exclude_words:
                print(f'🎯 通用提取到联系人: {m}')
                return m
        
        return None
    
    def get_all_windows(self):
        """获取所有可见窗口"""
        windows = []
        try:
            def callback(hwnd, extra):
                if win32gui.IsWindowVisible(hwnd):
                    try:
                        window_text = win32gui.GetWindowText(hwnd)
                        class_name = win32gui.GetClassName(hwnd)
                        windows.append({'hwnd': hwnd, 'text': window_text, 'class': class_name})
                    except:
                        pass
                return True
            win32gui.EnumWindows(callback, None)
        except:
            pass
        return windows
    
    def detect_call(self):
        """检测通话"""
        try:
            windows = self.get_all_windows()
            
            call_window = None
            for w in windows:
                window_text = w['text']
                class_name = w.get('class', '')
                
                # 排除纯粹的企业微信主窗口
                if window_text in ['企业微信', 'WeChat']:
                    continue
                
                # 只检测明确包含通话相关关键词的窗口
                has_call_keyword = any(keyword in window_text for keyword in [
                    '语音通话', 
                    '视频通话', 
                    '正在呼叫',
                    '正在拨打',
                    '通话中'
                ])
                
                if has_call_keyword:
                    call_window = w
                    break
            
            if call_window:
                # 不尝试从窗口标题提取，只返回检测到有通话
                return {'has_call': True, 'contact_name': None}
            
        except Exception as e:
            print(f'检测通话失败: {e}')
        
        return {'has_call': False, 'contact_name': None}
    
    def upload_call_record(self, record):
        """上传通话记录到服务器"""
        try:
            server_url = self.settings.get('server_url', 'http://192.168.100.22:5000')
            url = f"{server_url}/wework/api/record"
            
            user_id = self.settings.get('user_id')
            print(f'📤 当前配置的user_id: {user_id}')
            
            data = {
                'user_name': record.get('user_name', '未知用户'),
                'call_start_time': record['start_time'].isoformat(),
                'uploader_id': user_id
            }
            
            if 'end_time' in record:
                data['call_end_time'] = record['end_time'].isoformat()
            
            self._log(f'上传通话记录: {data}')
            print(f'📤 上传通话记录: {data}')
            
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self._log(f'通话记录上传成功')
                    print(f'✅ 上传成功')
                    return True
                else:
                    error_msg = result.get('error', '未知错误')
                    self._log(f'通话记录上传失败: {error_msg}', 'ERROR')
                    print(f'❌ 上传失败: {error_msg}')
            else:
                self._log(f'通话记录上传失败，状态码: {response.status_code}', 'ERROR')
                print(f'❌ 上传失败，状态码: {response.status_code}')
        except Exception as e:
            self._log(f'通话记录上传异常: {e}', 'ERROR')
            print(f'❌ 上传通话记录出错: {str(e)}')
        
        return False
    
    def _run(self):
        """运行监控（在线程中）"""
        self._log(f'企微通话监控已启动')
        self._log(f'本机用户: {self.local_user}')
        self._log(f'计算机名: {self.computer_name}')
        self._log(f'客户端ID: {self.client_id}')
        self._log(f'配置的user_id: {self.user_id}')
        self._log(f'配置的user_name: {self.user_name}')
        
        print(f'🚀 企微通话监控已启动')
        print(f'👤 本机用户: {self.local_user}')
        print(f'🖥️ 计算机名: {self.computer_name}')
        print(f'🔑 客户端ID: {self.client_id[:8]}...')
        print(f'📋 配置用户ID: {self.user_id}')
        print(f'👤 配置用户名: {self.user_name}')
        print('💡 提示：新通话开始时会进行截图OCR识别')
        
        # 启动时立即发送一次心跳
        self.send_heartbeat()
        
        while self.running:
            try:
                # 检查是否需要发送心跳
                current_time = time.time()
                if current_time - self.last_heartbeat_time >= self.heartbeat_interval:
                    self.send_heartbeat()
                    self.last_heartbeat_time = current_time
                
                # 检查是否需要快速检查配置变更
                if current_time - self.last_config_check_time >= self.config_check_interval:
                    self.check_config_change()
                    self.last_config_check_time = current_time
                
                # 根据服务端配置决定是否检测通话
                if not self.call_recording_enabled:
                    # 服务端已停用通话读取功能
                    time.sleep(2)
                    continue
                
                result = self.detect_call()
                has_call = result['has_call']
                contact_name = result['contact_name']
                
                self._log(f'检测通话状态: has_call={has_call}, contact_name={contact_name}')
                
                if has_call:
                    if self.current_call is None:
                        # 新通话开始，截图OCR识别并保存信息（不上传）
                        final_contact_name = None
                        try:
                            # 获取通话窗口进行截图
                            windows = self.get_all_windows()
                            call_window = None
                            for w in windows:
                                window_text = w['text']
                                class_name = w.get('class', '')
                                
                                if window_text in ['企业微信', 'WeChat']:
                                    continue
                                
                                has_call_keyword = any(keyword in window_text for keyword in [
                                    '语音通话', '视频通话', '正在呼叫', '正在拨打', '通话中'
                                ])
                                
                                if has_call_keyword:
                                    call_window = w
                                    break
                            
                            if call_window:
                                print(f'📸 检测到新通话窗口: {repr(call_window["text"])}')
                                print('📸 正在截图...')
                                img = self.capture_window(call_window['hwnd'])
                                
                                if img:
                                    print('🔍 正在发送OCR请求到服务器...')
                                    ocr_contact_name = self.windows_ocr(img)
                                    if ocr_contact_name:
                                        final_contact_name = ocr_contact_name
                                        print(f'🎯 从OCR识别到联系人: {final_contact_name}')
                                    else:
                                        print('⚠️ OCR未识别到联系人')
                                else:
                                    print('⚠️ 截图失败')
                        except Exception as e:
                            print(f'⚠️ 截图OCR时出错: {e}')
                            import traceback
                            print(f'⚠️ 错误详情: {traceback.format_exc()}')
                        
                        # 如果OCR没有识别到联系人，使用一个友好的默认值
                        if not final_contact_name:
                            final_contact_name = '未知联系人'
                        
                        # 保存通话信息（不上传）
                        self.current_call = {
                            'user_name': final_contact_name,
                            'start_time': datetime.datetime.now()
                        }
                        self._log(f'新通话开始: {final_contact_name}')
                        print(f'🔔 检测到新通话开始: {final_contact_name}')
                else:
                    if self.current_call is not None:
                        # 通话结束，上传完整记录一次
                        self.current_call['end_time'] = datetime.datetime.now()
                        duration = (self.current_call['end_time'] - self.current_call['start_time']).seconds
                        self._log(f'通话结束: {self.current_call["user_name"]}, 时长: {duration}秒')
                        print(f'📞 通话结束，时长: {duration}秒')
                        
                        # 上传完整记录（包含开始和结束时间）
                        self.upload_call_record(self.current_call)
                        self.call_history.append(self.current_call)
                        self.current_call = None
                
            except Exception as e:
                print(f'监控出错: {str(e)}')
            
            time.sleep(2)
    
    def start(self):
        """启动监控"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
    
    def send_disconnect(self):
        """发送断开连接通知到服务器"""
        try:
            server_url = self.settings.get('server_url', 'http://192.168.100.22:5000')
            disconnect_url = f"{server_url}/wework/api/disconnect"
            
            data = {
                'client_id': self.client_id
            }
            
            self._log(f'发送断开连接通知到 {disconnect_url}')
            response = requests.post(disconnect_url, json=data, timeout=5)
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self._log('断开连接通知发送成功')
                    return True
            self._log('断开连接通知发送失败', 'ERROR')
        except Exception as e:
            self._log(f'发送断开连接通知异常: {e}', 'ERROR')
        return False
    
    def stop(self):
        """停止监控"""
        self.running = False
        
        # 发送断开连接通知
        self.send_disconnect()
        
        if self.thread:
            self.thread.join(timeout=3)
        print('🛑 企微通话监控已停止')
    
    def get_recent_calls(self):
        """获取最近通话记录"""
        return self.call_history[-10:]
