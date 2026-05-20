' 静默启动Flask服务器
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "python ""d:\fh\start_server.py""", 0, False
Set WshShell = Nothing