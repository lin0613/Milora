param([switch]$NonInteractive)
$ErrorActionPreference = 'Stop'
$Utf8Console = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $Utf8Console
[Console]::OutputEncoding = $Utf8Console
$OutputEncoding = $Utf8Console
$Host.UI.RawUI.WindowTitle = '遊戲成就紀錄器｜後端檢查'
function Finish([int]$Code){Write-Host '';if(-not $NonInteractive){[void](Read-Host '按 Enter 關閉此視窗')};exit $Code}
function Header([string]$Subtitle){Clear-Host;Write-Host '------------------------------------------------------------' -ForegroundColor DarkCyan;Write-Host ' 遊戲成就紀錄器｜後端狀態檢查' -ForegroundColor Cyan;Write-Host (" {0}" -f $Subtitle) -ForegroundColor DarkGray;Write-Host '------------------------------------------------------------' -ForegroundColor DarkCyan}
try{
 Header '正在檢查本機服務'
 $Connection=Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue|Select-Object -First 1
 if(-not $Connection){throw '連接埠 8000 沒有監聽程序，後端目前未啟動。'}
 $Result=Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 5
 if(-not $Result.ok -or $Result.service -ne 'game-achievement-hub'){throw '健康檢查回應不是遊戲成就紀錄器後端。'}
 Header '服務狀態正常'
 Write-Host ' [OK] 後端正在執行' -ForegroundColor Green
 Write-Host ' [OK] API 健康檢查通過' -ForegroundColor Green
 Write-Host ''
 Write-Host (" 程序 ID：{0}" -f $Connection.OwningProcess) -ForegroundColor Gray
 Write-Host ' 服務位址：http://127.0.0.1:8000' -ForegroundColor Gray
 Write-Host (" 服務名稱：{0}" -f $Result.service) -ForegroundColor Gray
 Write-Host (" 檢查時間：{0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')) -ForegroundColor Gray
 Finish 0
}catch{
 Header '服務狀態異常'
 Write-Host (" [錯誤] {0}" -f $_.Exception.Message) -ForegroundColor Red
 Write-Host ''
 Write-Host ' 請使用「啟動後端.cmd」重新啟動，或查看 logs 資料夾。' -ForegroundColor Yellow
 Finish 1
}
