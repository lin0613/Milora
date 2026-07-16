param([switch]$NonInteractive,[string]$ProjectRoot='')
$ErrorActionPreference='Stop'
$Utf8Console=New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding=$Utf8Console
[Console]::OutputEncoding=$Utf8Console
$OutputEncoding=$Utf8Console
$Root=if($ProjectRoot){(Resolve-Path -LiteralPath $ProjectRoot).Path}else{Split-Path -Parent $PSScriptRoot}
$PidFile=Join-Path $Root 'logs\backend-host.pid'
$Targets=New-Object 'System.Collections.Generic.List[int]'
$Host.UI.RawUI.WindowTitle='遊戲成就紀錄器｜關閉後端'
function Finish([int]$Code){Write-Host '';if(-not $NonInteractive){[void](Read-Host '按 Enter 關閉此視窗')};exit $Code}
function Header([string]$Subtitle){Clear-Host;Write-Host '------------------------------------------------------------' -ForegroundColor DarkCyan;Write-Host ' 遊戲成就紀錄器｜後端服務管理' -ForegroundColor Cyan;Write-Host (" {0}" -f $Subtitle) -ForegroundColor DarkGray;Write-Host '------------------------------------------------------------' -ForegroundColor DarkCyan}
function AddTarget([int]$Id){if($Id -gt 0 -and -not $Targets.Contains($Id)){$Targets.Add($Id)}}
function ProcessInfo([int]$Id){Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f $Id) -ErrorAction SilentlyContinue}
function IsOwned($Info){if($null -eq $Info){return $false};$cmd=[string]$Info.CommandLine;$exe=[string]$Info.ExecutablePath;$rootPattern=[regex]::Escape($Root);return (($cmd -match 'start_backend\.ps1' -and $cmd -match $rootPattern) -or ($cmd -match 'run_backend_host\.py' -and $cmd -match $rootPattern) -or ($cmd -match 'uvicorn\s+backend\.main:app' -and (($exe -and $exe.StartsWith($Root,[StringComparison]::OrdinalIgnoreCase)) -or $cmd -match $rootPattern)))}
function StopTarget([int]$Id){$Before=ProcessInfo $Id;if($null -eq $Before){Write-Host ("程序 {0} 已先行結束，略過重複關閉。" -f $Id) -ForegroundColor DarkGray;return};try{Start-Process -FilePath "$env:SystemRoot\System32\taskkill.exe" -ArgumentList @('/PID',[string]$Id,'/T','/F') -Wait -WindowStyle Hidden|Out-Null}catch{try{Stop-Process -Id $Id -Force -ErrorAction SilentlyContinue}catch{}};Start-Sleep -Milliseconds 350;if($null -ne (ProcessInfo $Id)){throw ("程序 {0} 仍在執行，無法安全關閉。" -f $Id)}}
try{
 Header '正在尋找本專案後端程序'
 if(Test-Path -LiteralPath $PidFile){$Value=0;$Raw=(Get-Content -LiteralPath $PidFile -Raw -ErrorAction SilentlyContinue).Trim();if([int]::TryParse($Raw,[ref]$Value)){if(IsOwned (ProcessInfo $Value)){AddTarget $Value}}}
 Get-CimInstance Win32_Process -ErrorAction SilentlyContinue|Where-Object{$_.CommandLine -and ($_.CommandLine -match 'start_backend\.ps1|run_backend_host\.py|uvicorn\s+backend\.main:app') -and $_.CommandLine -match [regex]::Escape($Root)}|ForEach-Object{AddTarget ([int]$_.ProcessId)}
 $Foreign=$null
 Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue|ForEach-Object{$Info=ProcessInfo ([int]$_.OwningProcess);if(IsOwned $Info){AddTarget ([int]$_.OwningProcess)}else{$Foreign=[int]$_.OwningProcess}}
 if($Targets.Count -eq 0){Header '沒有需要關閉的服務';if($Foreign){Write-Host (" [提醒] 本專案未執行；連接埠 8000 由其他程序占用（程序 ID：{0}）。" -f $Foreign) -ForegroundColor Yellow}else{Write-Host ' [OK] 目前沒有執行中的本專案後端。' -ForegroundColor Green};Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue;Finish 0}
 Write-Host (" 找到 {0} 個相關程序，正在安全關閉……" -f $Targets.Count) -ForegroundColor Gray
 foreach($Id in @($Targets|Sort-Object)){StopTarget $Id}
 $Remaining=@(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue|Where-Object{IsOwned (ProcessInfo ([int]$_.OwningProcess))})
 if($Remaining.Count -gt 0){throw '連接埠 8000 仍由本專案後端占用。'}
 Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
 Header '服務已停止'
 Write-Host ' [OK] 後端及其子程序已全部關閉' -ForegroundColor Green
 Write-Host ' [OK] 連接埠 8000 已釋放' -ForegroundColor Green
 Finish 0
}catch{
 Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
 Header '關閉失敗'
 Write-Host (" [錯誤] {0}" -f $_.Exception.Message) -ForegroundColor Red
 Write-Host ''
 Write-Host ' 請查看工作管理員或 logs 資料夾後再重試。' -ForegroundColor Yellow
 Finish 1
}
