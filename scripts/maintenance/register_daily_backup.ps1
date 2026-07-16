param([switch]$NonInteractive)
$ErrorActionPreference='Stop'
function Finish([int]$Code){Write-Host '';if(-not $NonInteractive){[void](Read-Host '處理已完成，請查看上方結果。按 Enter 關閉此視窗')};exit $Code}
try{
 $Script=Join-Path $PSScriptRoot 'backup_database.ps1'
 $Arguments="-NoLogo -NoProfile -ExecutionPolicy Bypass -File `"$Script`" -NoPause"
 $Action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $Arguments
 $Trigger=New-ScheduledTaskTrigger -Daily -At 3:00AM
 $Principal=New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
 $Settings=New-ScheduledTaskSettingsSet -StartWhenAvailable
 Register-ScheduledTask -TaskName 'GameAchievementBackup' -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force|Out-Null
 Write-Host '已註冊每日 03:00 資料庫備份。此排程只執行備份，不會啟動後端。' -ForegroundColor Green
 Finish 0
}catch{Write-Host ("註冊每日備份失敗：{0}" -f $_.Exception.Message) -ForegroundColor Red;Finish 1}
