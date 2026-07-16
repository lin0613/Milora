param([switch]$NoPause)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Python = Join-Path $Root '.venv\Scripts\python.exe'

try {
    if (-not (Test-Path -LiteralPath $Python)) {
        throw '找不到 .venv，請先執行 scripts\setup\02_install_backend.ps1。'
    }
    Set-Location $Root
    & $Python -m backend.backup_db
    if ($LASTEXITCODE -ne 0) {
        throw "資料庫備份程序結束代碼：$LASTEXITCODE"
    }
    Write-Host '資料庫備份完成。' -ForegroundColor Green
    $ExitCode = 0
} catch {
    Write-Host ("資料庫備份失敗：{0}" -f $_.Exception.Message) -ForegroundColor Red
    $ExitCode = 1
}

if (-not $NoPause) {
    [void](Read-Host '按 Enter 關閉此視窗')
}
exit $ExitCode
