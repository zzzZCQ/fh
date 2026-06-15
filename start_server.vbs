' 静默启动发货通知系统服务
' 使用 pythonw 无窗口模式运行

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "d:\fh"
WshShell.Run "pythonw ""d:\fh\start_server.py""", 0, False
Set WshShell = Nothing