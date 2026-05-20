# 桌面通知系统设计文档

## 1. 项目概述

### 1.1 项目背景
企业需要一个高效的内部通知系统，领导发布文字通知后自动生成图片，通过Windows客户端实时推送给员工，并展示在电脑屏幕右上角。

### 1.2 核心功能
- 通知发布与图片生成
- WebSocket实时推送
- Windows客户端通知展示
- 声音提醒与已读确认
- 确认状态统计与管理

### 1.3 目标用户
- **发布者**：领导、管理员
- **接收者**：全体员工（销售、发货员、管理员等）

---

## 2. 系统架构

### 2.1 整体架构
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   管理后台       │────▶│   Flask后端      │────▶│  Windows客户端   │
│   (Web界面)      │     │   (WebSocket)    │     │  (独立exe)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 2.2 技术栈
- **后端**：Python Flask + Flask-SocketIO
- **数据库**：SQLAlchemy（现有MySQL）
- **图片生成**：Pillow (PIL)
- **客户端**：PyQt5 / PyInstaller（桌面应用）
- **通信协议**：WebSocket

---

## 3. 数据库模型

### 3.1 BroadcastNotification 表（广播通知）
```python
class BroadcastNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))  # 通知标题
    content = db.Column(db.Text, nullable=False)  # 通知内容
    image_path = db.Column(db.String(500))  # 生成的图片路径
    priority = db.Column(db.String(20), default='normal')  # normal/important/urgent
    target_type = db.Column(db.String(20))  # all/department/role/user
    target_ids = db.Column(db.Text)  # 目标ID列表，逗号分隔
    scheduled_time = db.Column(db.DateTime)  # 定时发送时间
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='draft')  # draft/scheduled/sent
    create_time = db.Column(db.DateTime, default=_now_bj)
    sent_time = db.Column(db.DateTime)  # 实际发送时间
    
    sender = db.relationship('User', backref='sent_notifications')
```

### 3.2 NotificationReceipt 表（确认记录）
```python
class NotificationReceipt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer, db.ForeignKey('broadcast_notification.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    received_time = db.Column(db.DateTime)  # 客户端收到时间
    confirmed_time = db.Column(db.DateTime)  # 确认时间
    is_confirmed = db.Column(db.Boolean, default=False)
    
    notification = db.relationship('BroadcastNotification', 
                                   backref='receipts')
    user = db.relationship('User', backref='notification_receipts')
```

---

## 4. 后端功能设计

### 4.1 通知发布管理后台

#### 4.1.1 发布页面功能
- **标题输入**：最多200字符
- **内容编辑**：富文本编辑器，支持换行
- **优先级选择**：
  - 普通（蓝色）
  - 重要（黄色）
  - 紧急（红色）
- **目标选择**：
  - 全员发送
  - 按部门发送（多选）
  - 按角色发送（销售/发货员/管理员）
  - 指定人员发送
- **定时发送**：
  - 立即发送
  - 定时发送（选择日期时间）
- **预览**：发布前预览生成的图片效果
- **发布按钮**：生成图片并发送

#### 4.1.2 图片自动生成
- 使用Pillow库生成精美通知图片
- **图片规格**：
  - 宽度：600px（适配客户端显示）
  - 高度：根据内容自动调整（最大800px）
- **设计元素**：
  - 顶部颜色条（根据优先级）
  - 标题（大号字体，加粗）
  - 正文内容（中等字体）
  - 底部：公司名称 + 发布时间
  - 二维码或公司Logo（可选）
- **字体**：使用系统默认字体或嵌入字体
- **输出**：保存为PNG格式到 static/notifications/ 目录

#### 4.1.3 管理统计页面
- 查看已发送通知列表
- 每条通知的确认率统计
- 未确认员工名单
- 催读功能（一键提醒未确认者）
- 支持按日期范围筛选

### 4.2 WebSocket推送系统

#### 4.2.1 Flask-SocketIO集成
```python
from flask_socketio import SocketIO, emit

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

@socketio.on('connect')
def handle_connect():
    # 客户端连接，验证用户身份
    # 建立用户连接映射
    pass

@socketio.on('disconnect')
def handle_disconnect():
    # 清理连接映射
    pass
```

#### 4.2.2 推送机制
- **连接认证**：客户端连接时携带用户token，后端验证身份
- **用户映射**：维护user_id到session_id的映射
- **消息格式**：
```json
{
    "type": "notification",
    "data": {
        "id": 123,
        "title": "会议通知",
        "content": "今天下午2点召开部门会议",
        "image_url": "/static/notifications/abc123.png",
        "priority": "important",
        "timestamp": "2026-05-19 10:30:00"
    }
}
```

#### 4.2.3 确认机制
- 客户端收到消息后发送确认：
```json
{
    "type": "receipt",
    "notification_id": 123,
    "status": "received"
}
```
- 服务器记录received_time
- 用户点击确认后发送：
```json
{
    "type": "confirm",
    "notification_id": 123
}
```
- 服务器记录confirmed_time和is_confirmed

#### 4.2.4 心跳与重连
- 服务端每30秒向客户端发送ping
- 客户端超过60秒无响应则断开连接
- 客户端自动重连（指数退避：1s, 2s, 4s, 8s, 最大30s）

### 4.3 API接口设计

#### 4.3.1 管理端API
```
POST   /api/broadcast/notifications      - 创建通知
GET    /api/broadcast/notifications       - 获取通知列表
GET    /api/broadcast/notifications/<id>  - 获取通知详情
PUT    /api/broadcast/notifications/<id>  - 更新通知
DELETE /api/broadcast/notifications/<id>  - 删除通知
POST   /api/broadcast/notifications/<id>/send  - 发送通知
GET    /api/broadcast/notifications/<id>/receipts  - 获取确认状态
POST   /api/broadcast/notifications/<id>/remind  - 催读提醒
```

#### 4.3.2 客户端API
```
GET    /api/client/notifications          - 获取历史通知
POST   /api/client/notifications/<id>/confirm  - 确认通知
GET    /api/client/settings               - 获取客户端设置
PUT    /api/client/settings               - 更新客户端设置
```

---

## 5. Windows客户端设计

### 5.1 技术选型
- **框架**：PyQt5（现代化UI，跨平台）
- **打包**：PyInstaller（生成单个exe）
- **图片展示**：QLabel + QPixmap
- **系统托盘**：QSystemTrayIcon
- **网络**：websocket-client库

### 5.2 客户端功能模块

#### 5.2.1 系统托盘
- **托盘图标**：
  - 正常运行：绿色图标
  - 有新通知：蓝色图标
  - 紧急通知：红色闪烁图标
  - 离线状态：灰色图标
- **托盘菜单**：
  - 打开主界面
  - 查看历史通知
  - 设置
  - 退出
- **托盘气泡**：新通知时显示气泡提示

#### 5.2.2 通知窗口
- **显示位置**：屏幕右上角
- **窗口特性**：
  - 固定大小（600x400，可自适应内容）
  - 置顶显示（总在最前）
  - 无边框（仅显示图片）
  - 可拖动
- **优先级样式**：
  - 普通：蓝色边框，5秒后自动隐藏
  - 重要：黄色边框+轻微放大动画，10秒后自动隐藏
  - 紧急：红色边框+闪烁效果，不自动隐藏
- **自动隐藏**：
  - 普通/重要通知：无操作5秒后自动最小化到托盘
  - 紧急通知：必须手动确认
- **关闭按钮**：右上角X按钮，点击关闭

#### 5.2.3 声音提醒
- **音频文件**：wav格式（mp3需要额外库）
- **优先级声音**：
  - 普通：短提示音（1秒）
  - 重要：中等提示音（2秒）
  - 紧急：警报音（持续3秒或循环）
- **设置选项**：
  - 音量调节（0-100%）
  - 静音模式
  - 自定义声音（可选）

#### 5.2.4 确认机制
- **确认按钮**：
  - 大号绿色按钮："✓ 我已知晓"
  - 按钮位置：通知图片下方
  - 点击后：
    - 播放确认音效（可选）
    - 发送确认请求到服务器
    - 窗口自动关闭
    - 托盘图标恢复绿色
- **关闭按钮**：
  - 小号灰色按钮："✕"
  - 点击后仅关闭窗口，不发送确认
  - 用于暂时忽略通知

#### 5.2.5 历史通知
- **列表展示**：新窗口显示历史通知列表
- **列表项**：
  - 通知缩略图
  - 标题
  - 发布时间
  - 确认状态（已确认/未确认）
  - 确认时间
- **分页**：支持加载更多
- **搜索**：按标题/内容搜索

#### 5.2.6 设置界面
- **服务器配置**：
  - 服务器地址（IP:端口）
  - 用户认证信息（工号/密码）
  - 保存登录状态
- **通知设置**：
  - 音量大小
  - 声音开关
  - 自动启动（开机自启）
  - 启动时最小化
- **显示设置**：
  - 普通通知显示时长
  - 重要通知显示时长
  - 是否启用紧急通知闪烁

#### 5.2.7 连接管理
- **启动连接**：
  - 启动时连接WebSocket服务器
  - 验证用户身份
  - 同步未读通知
- **断线重连**：
  - 检测连接断开
  - 显示托盘气泡提示"连接已断开"
  - 自动重连（指数退避）
  - 重连成功后同步离线期间的通知
- **离线缓存**：
  - 断开期间的通知暂存服务器
  - 重连后一次性推送
  - 确保不丢失通知

### 5.3 客户端界面流程

```
启动程序
    ↓
连接服务器（显示连接中...）
    ↓
验证用户身份
    ↓
┌─ 成功 ─────────────────────┐
│ 接收未读通知                 │
│ 显示托盘图标（绿色）           │
│ 等待推送通知                 │
└────────────────────────────┘
    ↓
┌─ 失败 ─────────────────────┐
│ 显示错误提示                 │
│ 进入离线模式                │
│ 定时尝试重连                │
└────────────────────────────┘
```

### 5.4 通知推送流程

```
收到推送通知
    ↓
下载通知图片（首次，后续缓存）
    ↓
显示通知窗口（右上角弹出）
    ↓
播放对应优先级声音
    ↓
等待用户操作
    ↓
┌─ 点击"确认" ─────────────┐
│ 发送确认请求              │
│ 关闭窗口                  │
│ 更新托盘图标              │
└──────────────────────────┘
    ↓
┌─ 点击"关闭" ─────────────┐
│ 仅关闭窗口                │
│ 通知保持未确认状态         │
└──────────────────────────┘
    ↓
┌─ 超时自动隐藏 ────────────┐
│ 窗口最小化到托盘          │
│ 通知保持未确认状态         │
└──────────────────────────┘
```

---

## 6. 详细功能规格

### 6.1 图片生成规格

#### 6.1.1 图片尺寸
- 宽度：600px（固定）
- 高度：200-800px（根据内容自动调整）
- 边距：左右各30px，上下各40px

#### 6.1.2 颜色方案
```python
COLORS = {
    'normal': {
        'header': '#3498db',      # 蓝色
        'header_text': '#ffffff',
        'body_bg': '#ffffff',
        'title': '#2c3e50',
        'content': '#34495e',
        'footer': '#ecf0f1',
        'border': '#3498db'
    },
    'important': {
        'header': '#f39c12',      # 黄色
        'header_text': '#ffffff',
        'body_bg': '#fffef0',
        'title': '#2c3e50',
        'content': '#34495e',
        'footer': '#fef9e7',
        'border': '#f39c12'
    },
    'urgent': {
        'header': '#e74c3c',      # 红色
        'header_text': '#ffffff',
        'body_bg': '#fff5f5',
        'title': '#c0392b',
        'content': '#34495e',
        'footer': '#fdeaea',
        'border': '#e74c3c'
    }
}
```

#### 6.1.3 字体规格
- 标题：系统默认粗体，28px
- 内容：系统默认常规，18px，行高1.5
- 底部信息：系统默认，14px

### 6.2 通知窗口规格

#### 6.2.1 窗口属性
```python
WINDOW_CONFIG = {
    'width': 600,
    'height': 400,
    'position': 'top_right',  # 屏幕右上角
    'margin': 20,  # 距屏幕边缘距离
    'opacity': 1.0,
    'always_on_top': True,
    'frameless': True,
    'skip_taskbar': True
}
```

#### 6.2.2 动画效果
- 弹出动画：从右向左滑入（300ms，ease-out）
- 关闭动画：淡出（200ms）
- 紧急通知闪烁：透明度在0.3-1.0之间切换（500ms间隔）

### 6.3 声音提醒规格

#### 6.3.1 音频文件
- 普通通知：`normal.wav`（1秒，440Hz蜂鸣）
- 重要通知：`important.wav`（2秒，渐强蜂鸣）
- 紧急通知：`urgent.wav`（3秒，警报声）
- 确认音效：`confirm.wav`（0.5秒，轻柔提示）

#### 6.3.2 播放控制
- 使用QSound或pygame.mixer
- 支持音量调节
- 支持静音模式
- 支持系统通知音（Windows 10+）

---

## 7. 安全性设计

### 7.1 认证机制
- **客户端认证**：
  - 首次启动时输入工号和密码
  - 服务器验证后返回JWT token
  - 客户端存储token（加密本地文件）
  - WebSocket连接时携带token
- **Token刷新**：
  - Token有效期24小时
  - 客户端自动刷新token

### 7.2 权限控制
- 只有管理员（can_broadcast=True）可以发布通知
- 员工只能接收和确认通知
- 历史记录按权限显示

### 7.3 数据安全
- HTTPS传输（生产环境）
- 敏感信息加密存储
- 客户端不存储明文密码

---

## 8. 部署方案

### 8.1 服务器部署
- **环境**：Python 3.8+，Linux/Windows
- **依赖**：
  - Flask
  - Flask-SocketIO
  - Flask-Login
  - Pillow
  - eventlet（WebSocket服务）
- **进程管理**：
  - 使用Gunicorn + eventlet
  - 或直接使用 `python app.py`（开发环境）
- **端口**：5000（HTTP/WebSocket）

### 8.2 客户端部署
- **打包**：`pyinstaller --onefile --windowed client.spec`
- **安装**：
  - 提供exe安装包
  - 或绿色版（解压即用）
- **配置**：
  - 首次运行引导配置服务器地址
  - 自动创建桌面快捷方式
  - 可选开机自启动

### 8.3 文件结构
```
d:\fh\
├── app.py                          # Flask主应用
├── models.py                       # 数据模型（扩展）
├── routes_notifications.py          # 通知API（扩展）
├── routes_broadcast.py              # 新增：广播管理API
├── socket_events.py                 # 新增：WebSocket事件处理
├── notification_generator.py         # 新增：图片生成器
├── client/                          # 新增：客户端代码
│   ├── main.py                      # 客户端入口
│   ├── notification_window.py       # 通知窗口
│   ├── tray_icon.py                 # 系统托盘
│   ├── settings.py                  # 设置管理
│   ├── websocket_client.py          # WebSocket客户端
│   ├── sounds/                      # 声音文件
│   │   ├── normal.wav
│   │   ├── important.wav
│   │   ├── urgent.wav
│   │   └── confirm.wav
│   └── requirements.txt
├── static/
│   └── notifications/               # 生成的图片存储
│       ├── .gitkeep
│       └── *.png
└── docs/
    └── specs/
        └── 2026-05-19-notification-desktop-design.md
```

---

## 9. 实施计划

### 阶段1：后端核心（1-2天）
1. 扩展数据库模型
2. 实现图片生成器
3. 实现WebSocket基础功能
4. 实现广播管理API

### 阶段2：前端管理后台（1天）
1. 创建广播发布页面
2. 创建统计管理页面
3. 集成现有系统

### 阶段3：Windows客户端（2-3天）
1. 实现系统托盘功能
2. 实现通知窗口
3. 实现WebSocket客户端
4. 实现声音提醒
5. 实现设置界面

### 阶段4：测试与部署（1天）
1. 功能测试
2. 压力测试
3. 打包exe
4. 部署上线

---

## 10. 测试用例

### 10.1 后端测试
- [ ] 创建通知并生成图片
- [ ] WebSocket推送消息
- [ ] 客户端确认机制
- [ ] 定时发送功能
- [ ] 权限控制验证

### 10.2 客户端测试
- [ ] 启动连接服务器
- [ ] 接收并显示通知
- [ ] 声音播放正常
- [ ] 确认按钮功能
- [ ] 关闭按钮功能
- [ ] 断线重连
- [ ] 托盘菜单功能
- [ ] 设置保存

### 10.3 集成测试
- [ ] 完整流程：发布→推送→显示→确认
- [ ] 多客户端并发
- [ ] 高优先级通知优先级显示

---

## 11. 未来扩展

### 11.1 可选功能
- 通知模板管理
- 周期性通知
- 通知回复/评论
- 移动端客户端（Android/iOS）
- 企业微信/钉钉集成

### 11.2 性能优化
- 图片CDN加速
- WebSocket集群部署
- 消息队列（Redis）
- 通知历史数据库归档

---

## 12. 风险评估

### 12.1 技术风险
- **WebSocket稳定性**：需要充分测试断线重连
- **图片生成性能**：大批量通知时可能影响服务器
- **客户端兼容性**：需要支持Windows 7/10/11

### 12.2 运维风险
- **服务器负载**：大量客户端同时连接
- **网络问题**：内网/外网部署差异
- **数据备份**：通知记录持久化

### 12.3 缓解措施
- 使用WebSocket心跳检测连接健康
- 图片生成异步处理，不阻塞主线程
- 客户端实现本地缓存和重试机制
- 使用数据库连接池和缓存

---

**文档版本**：1.0  
**创建日期**：2026-05-19  
**状态**：待用户确认
