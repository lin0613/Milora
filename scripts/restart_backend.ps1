param([switch]$NonInteractive)
$ErrorActionPreference = 'Stop'
$Utf8Console = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $Utf8Console
[Console]::OutputEncoding = $Utf8Console
$OutputEncoding = $Utf8Console
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
$Host.UI.RawUI.WindowTitle = '遊戲成就紀錄器｜重啟後端'

function Finish([int]$Code) {
    Write-Host ''
    if (-not $NonInteractive) { [void](Read-Host '按 Enter 關閉此視窗') }
    exit $Code
}
function Header([string]$Subtitle) {
    Clear-Host
    Write-Host '------------------------------------------------------------' -ForegroundColor DarkCyan
    Write-Host ' 遊戲成就紀錄器｜後端服務管理' -ForegroundColor Cyan
    Write-Host (" {0}" -f $Subtitle) -ForegroundColor DarkGray
    Write-Host '------------------------------------------------------------' -ForegroundColor DarkCyan
}
function Step([string]$State, [string]$Text, [ConsoleColor]$Color = [ConsoleColor]::Gray) {
    Write-Host (" [{0,-4}] {1}" -f $State, $Text) -ForegroundColor $Color
}

try {
    $StopScript = Join-Path $Root 'scripts\stop_backend.ps1'
    $StartScript = Join-Path $Root 'scripts\start_backend.ps1'
    Header '準備重啟'
    if (-not (Test-Path -LiteralPath $StopScript)) { throw '缺少 scripts\stop_backend.ps1。' }
    if (-not (Test-Path -LiteralPath $StartScript)) { throw '缺少 scripts\start_backend.ps1。' }
    Step '....' '先關閉目前的後端服務'
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $StopScript -NonInteractive -ProjectRoot $Root
    if ($LASTEXITCODE -ne 0) { throw '後端停止流程失敗，已中止重啟。' }
    Step 'OK' '後端停止流程完成' Green
    Step '....' '重新啟動後端服務'
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $StartScript
    exit $LASTEXITCODE
} catch {
    Header '重啟失敗'
    Write-Host (" [錯誤] {0}" -f $_.Exception.Message) -ForegroundColor Red
    Write-Host ''
    Write-Host ' 建議：執行「檢查後端.cmd」或查看 logs 資料夾中的最新日誌。' -ForegroundColor Yellow
    Finish 1
}
