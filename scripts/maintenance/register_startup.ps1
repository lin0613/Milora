param([switch]$NonInteractive,[string]$ProjectRoot='',[string]$UserId='')
$ErrorActionPreference='Stop'
$TaskName='GameAchievementBackend'
$Root=if($ProjectRoot){[IO.Path]::GetFullPath($ProjectRoot)}else{Split-Path -Parent (Split-Path -Parent $PSScriptRoot)}
$DiagnosticLog=Join-Path $Root 'logs\register-startup.log'
function Finish([int]$Code){Write-Host '';if(-not $NonInteractive){[void](Read-Host '處理已完成，請查看上方結果。按 Enter 關閉此視窗')};exit $Code}
function Write-Diagnostic([string]$Level,[string]$Message){
 $logDirectory=Split-Path -Parent $DiagnosticLog
 New-Item -ItemType Directory -Path $logDirectory -Force|Out-Null
 Add-Content -LiteralPath $DiagnosticLog -Encoding UTF8 -Value ("[{0}] [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'),$Level,$Message)
}
function Assert-Admin(){
 $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
 $principal=New-Object Security.Principal.WindowsPrincipal($identity)
 if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw '註冊自動啟動工作排程需要系統管理員權限。'}
}
try{
 Write-Diagnostic 'INFO' '開始註冊登入自動啟動工作排程。'
 Assert-Admin
 $StartScript=Join-Path $Root 'scripts\start_backend.ps1'
 if(-not (Test-Path -LiteralPath $StartScript -PathType Leaf)){throw ("找不到後端啟動腳本：{0}" -f $StartScript)}
 $ResolvedUser=if($UserId){$UserId.Trim()}else{[Security.Principal.WindowsIdentity]::GetCurrent().Name}
 if(-not $ResolvedUser){throw '無法判斷要在登入時啟動後端的 Windows 使用者。'}
 $PowerShell=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
 if(-not (Test-Path -LiteralPath $PowerShell -PathType Leaf)){throw ("找不到 Windows PowerShell：{0}" -f $PowerShell)}
 $Arguments='-NoLogo -NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $StartScript.Replace('"','""')
 $Action=New-ScheduledTaskAction -Execute $PowerShell -Argument $Arguments -WorkingDirectory $Root
 $Trigger=New-ScheduledTaskTrigger -AtLogOn -User $ResolvedUser
 $Principal=New-ScheduledTaskPrincipal -UserId $ResolvedUser -LogonType Interactive -RunLevel Highest
 $Settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
 Register-ScheduledTask -TaskName $TaskName -Description '登入 Windows 後，以最高權限顯示並維持遊戲成就紀錄器後端服務視窗。' -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force|Out-Null
 $Task=Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
 $TaskAction=@($Task.Actions)[0]
 $TaskTrigger=@($Task.Triggers)[0]
 if([string]$Task.Principal.UserId -ne $ResolvedUser){throw '工作排程的登入使用者與要求不一致。'}
 if([string]$Task.Principal.RunLevel -ne 'Highest'){throw '工作排程未設定為最高權限。'}
 if([string]$Task.Principal.LogonType -ne 'Interactive'){throw '工作排程未設定為互動式登入；後端視窗將無法顯示。'}
 if([string]$TaskAction.Arguments -notlike "*$StartScript*"){throw '工作排程沒有指向目前專案的後端啟動腳本。'}
 if([string]$TaskAction.Arguments -match '(?i)WindowStyle\s+Hidden'){throw '工作排程錯誤地隱藏了後端視窗。'}
 if([string]$TaskTrigger.UserId -ne $ResolvedUser){throw '工作排程的登入觸發使用者與要求不一致。'}
 Write-Host ("已註冊工作排程 {0}。" -f $TaskName) -ForegroundColor Green
 Write-Host ("觸發方式：{0} 登入 Windows 後自動啟動。" -f $ResolvedUser) -ForegroundColor Green
 Write-Host '執行方式：最高權限、顯示後端視窗；註冊完成後不會立即啟動或重啟後端。' -ForegroundColor Green
 Write-Diagnostic 'OK' ("已註冊 {0}；使用者={1}；最高權限；互動式登入；動作={2}" -f $TaskName,$ResolvedUser,$TaskAction.Arguments)
 Finish 0
}catch{$message="註冊登入自動啟動失敗：{0}" -f $_.Exception.Message;Write-Diagnostic 'ERROR' $message;Write-Host $message -ForegroundColor Red;Finish 1}
