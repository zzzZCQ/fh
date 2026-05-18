# Git自动提交设置指南

## 前置要求

1. **安装Git**
   - 下载地址：https://git-scm.com/download/win
   - 安装时确保勾选 "Add Git to PATH"

2. **(可选) 配置远程仓库**
   - 如果需要推送到GitHub/GitLab等，请先创建仓库
   - 然后运行：`git remote add origin <你的仓库地址>`

## 初始化步骤

### 1. 初始化Git仓库

双击运行 `init_git.py` 或在命令行中执行：
```bash
python init_git.py
```

按提示输入用户名和邮箱。

### 2. 设置定时任务

**以管理员身份** 运行 `setup_scheduled_task.bat`

这将创建一个每天晚上23:00自动执行的定时任务。

## 文件说明

| 文件 | 说明 |
|------|------|
| `.gitignore` | Git忽略文件配置 |
| `git_auto_commit.bat` | 自动提交脚本 |
| `init_git.py` | Git仓库初始化脚本 |
| `setup_scheduled_task.bat` | 设置Windows定时任务脚本 |

## 常用命令

```cmd
# 查看任务状态
schtasks /query /tn "GitAutoCommit_FHScript"

# 手动运行任务
schtasks /run /tn "GitAutoCommit_FHScript"

# 删除任务
schtasks /delete /tn "GitAutoCommit_FHScript" /f

# 查看Git历史
git log --oneline

# 手动提交
git add .
git commit -m "提交说明"
git push
```

## 自定义提交时间

编辑 `setup_scheduled_task.bat`，修改 `START_TIME` 变量：
```batch
set START_TIME=23:00  # 改为你想要的时间，例如 02:00
```

然后重新运行 `setup_scheduled_task.bat`。

## 故障排除

### Git命令找不到
确保Git已安装并添加到系统PATH中。重启命令行或电脑后重试。

### 定时任务不执行
1. 打开"任务计划程序"
2. 找到 "GitAutoCommit_FHScript"
3. 检查历史记录和设置

### 推送失败
确保已正确配置远程仓库，并且有推送权限。
