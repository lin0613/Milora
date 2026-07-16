param([Parameter(Mandatory=$true)][string]$To,[switch]$NonInteractive)
$ErrorActionPreference='Stop'
function Finish([int]$Code){Write-Host '';if(-not $NonInteractive){[void](Read-Host '處理已完成，請查看上方結果。按 Enter 關閉此視窗')};exit $Code}
try{
 $Root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
 $Python=Join-Path $Root '.venv\Scripts\python.exe'
 if(-not(Test-Path -LiteralPath $Python)){throw '找不到 .venv，請先執行 scripts\setup\02_install_backend.ps1。'}
 Set-Location -LiteralPath $Root
 & $Python -m backend.test_mail $To
 if($LASTEXITCODE -ne 0){throw "寄信測試結束代碼：$LASTEXITCODE"}
 Write-Host '寄信測試完成。' -ForegroundColor Green
 Finish 0
}catch{Write-Host ("寄信測試失敗：{0}" -f $_.Exception.Message) -ForegroundColor Red;Finish 1}
