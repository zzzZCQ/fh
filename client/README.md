# Notification Client README

## 新功能

### 1. 静默运行
- 程序启动时不显示任何窗口
- 只在系统托盘显示图标
- 占用资源少，适合后台运行

### 2. 关闭按钮行为
- 点击窗口关闭按钮时，最小化到系统托盘而不是退出
- 需要从托盘菜单选择"退出"才能完全关闭程序

### 3. 开机自启动
- 在设置中提供开关选项
- 使用Windows注册表实现开机自启动
- 无需手动配置，简单易用

### 4. 自动检测和重启
- 如果程序意外关闭，会自动重启
- 有两个实现方式：
  - `start_with_watchdog.bat` - 批处理版本
  - `watchdog.py` - Python版本，功能更丰富

### 5. 自动重连
- 与服务器断开连接后，自动尝试重连
- 每5秒尝试一次
- 重连成功后会显示通知

## 使用方法

### 方式一：直接运行
```bash
cd d:\fh\client
dist\NotificationClient.exe
```

### 方式二：使用批处理监控器
```bash
cd d:\fh\client
start_with_watchdog.bat
```
- 自动检测程序是否运行
- 关闭后3秒自动重启
- 最多重启100次

### 方式三：使用Python监控器
```bash
cd d:\fh\client
python watchdog.py
```
- 显示详细的启动/重启信息
- 可以看到客户端状态
- 按 Ctrl+C 安全退出

### 设置开机自启动
1. 双击运行客户端
2. 右键点击托盘图标
3. 选择"设置"
4. 点击"设置开机自启动"按钮
5. 保存设置

## 托盘菜单

- **打开** - 打开历史通知窗口
- **历史** - 查看历史通知
- **设置** - 打开设置对话框
- **退出** - 完全退出程序

## 配置文件

配置文件位置：`%APPDATA%\notification_client\settings.json`

可以手动修改以下配置：
```json
{
    "server_url": "http://192.168.100.22:5000",
    "username": "your_username",
    "password": "your_password",
    "sound_enabled": true,
    "volume": 80
}
```

## 故障排除

### 程序启动后没有反应
1. 检查系统托盘是否有图标
2. 查看是否被杀毒软件拦截
3. 检查网络连接

### 收不到通知
1. 检查用户名和密码是否正确
2. 检查服务器是否运行
3. 查看控制台输出错误信息

### 开机自启动不生效
1. 确认在设置中已开启
2. 检查Windows自启动注册表
3. 尝试手动添加到启动文件夹

### 监控脚本不工作
1. 确保已用build.bat重新打包
2. 检查EXE文件是否存在
3. 尝试用管理员权限运行

## 编译打包

```bash
cd d:\fh\client
build.bat
```

打包后会生成：
- `dist\NotificationClient.exe` - 主程序
- `start_with_watchdog.bat` - 批处理监控器
- `watchdog.py` - Python监控脚本

## 注意事项

1. **首次运行**：可能被Windows SmartScreen拦截，参考SIGNING_GUIDE.md进行签名
2. **杀毒软件**：可能被误报，需要添加白名单
3. **网络**：需要稳定的网络连接才能正常工作
4. **权限**：不需要管理员权限即可运行

## 技术支持

如有问题，请查看：
- 控制台输出错误信息
- Windows事件查看器
- 联系开发人员
