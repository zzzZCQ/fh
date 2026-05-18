# WeWork Double Open Tool
$ErrorActionPreference = "Continue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "         WeWork Double Open" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Requesting admin rights..." -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoExit", "-ExecutionPolicy Bypass", "-File `"$PSCommandPath`""
    exit
}

Write-Host "[OK] Admin rights obtained" -ForegroundColor Green
Write-Host ""

# Find WXWork process
Write-Host "[1/2] Finding WXWork process..." -ForegroundColor Yellow
$processes = Get-Process WXWork -ErrorAction SilentlyContinue

if (-not $processes) {
    Write-Host ""
    Write-Host "[ERROR] WXWork not found!" -ForegroundColor Red
    Write-Host "Please open WeWork first, then run this tool" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit
}

Write-Host "[OK] Found $($processes.Count) WXWork process(es)" -ForegroundColor Green
$processes | ForEach-Object { Write-Host "     PID: $($_.Id)  Name: $($_.ProcessName)" -ForegroundColor Gray }
Write-Host ""

# Load Windows API
Write-Host "[2/2] Scanning and closing exclusive objects..." -ForegroundColor Yellow
Write-Host ""

$signature = @"
[DllImport("kernel32.dll", SetLastError = true)]
public static extern IntPtr OpenProcess(uint dwDesiredAccess, bool bInheritHandle, int dwProcessId);

[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool CloseHandle(IntPtr hObject);

[DllImport("kernel32.dll", SetLastError = true)]
public static extern IntPtr GetCurrentProcess();

[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool DuplicateHandle(IntPtr hSourceProcessHandle, IntPtr hSourceHandle, IntPtr hTargetProcessHandle, out IntPtr lpTargetHandle, uint dwDesiredAccess, bool bInheritHandle, uint dwOptions);

[DllImport("ntdll.dll", SetLastError = true)]
public static extern int NtQueryObject(IntPtr Handle, int ObjectInformationClass, IntPtr ObjectInformation, int ObjectInformationLength, out int returnLength);
"@

Add-Type -MemberDefinition $signature -Namespace WinAPI -Name Native

$closedTotal = 0
$DUPLICATE_CLOSE_SOURCE = 0x00000001
$DUPLICATE_SAME_ACCESS = 0x00000002
$PROCESS_ALL_ACCESS = 0x001F0FFF

foreach ($proc in $processes) {
    Write-Host "  Scanning PID $($proc.Id)..." -ForegroundColor White
    
    $hProcess = [WinAPI.Native]::OpenProcess($PROCESS_ALL_ACCESS, $false, $proc.Id)
    
    if ($hProcess -eq [IntPtr]::Zero) {
        Write-Host "    [ERROR] Cannot open process" -ForegroundColor Red
        continue
    }
    
    $buffer = [System.Runtime.InteropServices.Marshal]::AllocHGlobal(65536)
    $foundCount = 0
    $done = $false
    
    for ($h = 4; $h -lt 0x1000000 -and -not $done; $h += 4) {
        $dupHandle = [IntPtr]::Zero
        
        $result = [WinAPI.Native]::DuplicateHandle(
            $hProcess, 
            [IntPtr]$h, 
            [WinAPI.Native]::GetCurrentProcess(), 
            [ref]$dupHandle, 
            0, 
            $false, 
            $DUPLICATE_SAME_ACCESS
        )
        
        if ($result -and $dupHandle -ne [IntPtr]::Zero) {
            try {
                $retLen = 0
                $status = [WinAPI.Native]::NtQueryObject($dupHandle, 1, $buffer, 65536, [ref]$retLen)
                
                if ($status -eq 0) {
                    $nameLen = [System.Runtime.InteropServices.Marshal]::ReadInt16($buffer, 0)
                    if ($nameLen -gt 0 -and $nameLen -lt 2000) {
                        $ptr = [System.Runtime.InteropServices.Marshal]::ReadIntPtr($buffer, 8)
                        if ($ptr -ne [IntPtr]::Zero) {
                            $name = [System.Runtime.InteropServices.Marshal]::PtrToStringUni($ptr, $nameLen / 2)
                            
                            if ($name -like "*Tencent.WeWork.ExclusiveObject" -or $name -like "*Tencent.WeWork.ExclusiveObjectInstance1") {
                                $foundCount++
                                Write-Host "    [$h] [FOUND] $name" -ForegroundColor Yellow
                                
                                [WinAPI.Native]::CloseHandle($dupHandle) | Out-Null
                                
                                $dummy = [IntPtr]::Zero
                                $closeResult = [WinAPI.Native]::DuplicateHandle(
                                    $hProcess, 
                                    [IntPtr]$h, 
                                    [IntPtr]::Zero, 
                                    [ref]$dummy, 
                                    0, 
                                    $false, 
                                    $DUPLICATE_CLOSE_SOURCE
                                )
                                
                                if ($closeResult) {
                                    Write-Host "    [$h] [CLOSED]" -ForegroundColor Green
                                    $closedTotal++
                                } else {
                                    $err = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
                                    Write-Host "    [$h] [FAILED] Error: $err" -ForegroundColor Red
                                }
                                
                                # Stop scanning this process once both are found
                                if ($foundCount -ge 2) {
                                    $done = $true
                                }
                                
                                continue
                            }
                        }
                    }
                }
            }
            finally {
                [WinAPI.Native]::CloseHandle($dupHandle) | Out-Null
            }
        }
    }
    
    [System.Runtime.InteropServices.Marshal]::FreeHGlobal($buffer) | Out-Null
    [WinAPI.Native]::CloseHandle($hProcess) | Out-Null
    
    Write-Host "    Closed $foundCount handles in PID $($proc.Id)" -ForegroundColor Gray
    
    # Stop scanning other processes if we've found what we need
    if ($closedTotal -ge 2) {
        Write-Host ""
        Write-Host "  Found all target handles, stopping early." -ForegroundColor Cyan
        break
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan

if ($closedTotal -gt 0) {
    Write-Host "[SUCCESS] Closed $closedTotal mutex(es)" -ForegroundColor Green
    Write-Host "You can now open a second WeWork!" -ForegroundColor Green
} else {
    Write-Host "[INFO] No Tencent.WeWork mutex found" -ForegroundColor Yellow
    Write-Host "Maybe already can double-open, or try restart WeWork" -ForegroundColor Yellow
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
