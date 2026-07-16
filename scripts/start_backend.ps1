param([switch]$NonInteractive)
$ErrorActionPreference = 'Stop'
$Utf8Console = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $Utf8Console
[Console]::OutputEncoding = $Utf8Console
$OutputEncoding = $Utf8Console
$env:PYTHONUTF8 = '1'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
$Host.UI.RawUI.WindowTitle = '遊戲成就紀錄器｜後端服務'

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
function Stop-BackendChild($Process) {
    if ($null -eq $Process -or $Process.HasExited) { return }
    try {
        Start-Process -FilePath "$env:SystemRoot\System32\taskkill.exe" -ArgumentList @('/PID',[string]$Process.Id,'/T','/F') -Wait -WindowStyle Hidden | Out-Null
    } catch {
        try { Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue } catch {}
    }
}

$LogDirectory = Join-Path $Root 'logs'
$PidFile = Join-Path $LogDirectory 'backend-host.pid'
$Process = $null
$ExitCode = 1
try {
    Header '啟動前檢查'
    Step '....' '確認專案位置與必要檔案'
    if (-not (Test-Path -LiteralPath (Join-Path $Root 'backend\main.py'))) { throw '找不到 backend\main.py，請確認工具位於專案根目錄。' }
    New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
    Step 'OK' ("專案位置：{0}" -f $Root) Green

    Step '....' '檢查連接埠 8000'
    $Existing = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($Existing) {
        $OwnedService = $false
        try {
            $Health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 3
            $OwnedService = [bool]($Health.ok -and $Health.service -eq 'game-achievement-hub')
        } catch {}
        if ($OwnedService) {
            Step '....' '偵測到既有後端，正在強制重新載入替換檔' Yellow
            try {
                Start-Process -FilePath "$env:SystemRoot\System32\taskkill.exe" -ArgumentList @('/PID',[string]$Existing.OwningProcess,'/T','/F') -Wait -WindowStyle Hidden | Out-Null
            } catch {
                try { Stop-Process -Id ([int]$Existing.OwningProcess) -Force -ErrorAction SilentlyContinue } catch {}
            }
            for ($Wait = 0; $Wait -lt 20; $Wait++) {
                Start-Sleep -Milliseconds 250
                if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) { break }
            }
            if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
                throw '舊後端仍占用連接埠 8000，無法載入替換檔。請先在工作管理員結束該 Python 程序。'
            }
            Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
            Step 'OK' '既有後端已關閉，將以新檔案重新啟動' Green
        } else {
            throw ("連接埠 8000 已被其他程序占用，程序 ID：{0}。" -f $Existing.OwningProcess)
        }
    }
    Step 'OK' '連接埠 8000 可用' Green

    $Python = Join-Path $Root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $Python)) { throw '找不到 .venv\Scripts\python.exe，請先安裝後端環境。' }
    Step '....' '檢查 Python、Uvicorn、FastAPI 與後端模組'
    $env:PYTHONPATH = $Root
    $env:DATABASE_PATH = Join-Path $Root 'data\app.db'
    & $Python -c "import uvicorn, fastapi; import backend.main" *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Python 套件或後端模組載入失敗。' }
    Step 'OK' '後端執行環境正常' Green

    Get-ChildItem -LiteralPath $LogDirectory -Filter 'backend-*.log' -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 | Remove-Item -Force -ErrorAction SilentlyContinue
    $LogFile = Join-Path $LogDirectory ("backend-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    $Runner = Join-Path $Root 'scripts\run_backend_host.py'
    if (-not (Test-Path -LiteralPath $Runner)) { throw '找不到 scripts\run_backend_host.py。' }
    $ArgumentLine = ('"{0}" --log "{1}"' -f $Runner.Replace('"','""'), $LogFile.Replace('"','""'))

    Step '....' '啟動後端服務並等待健康檢查'
    $Process = Start-Process -FilePath $Python -ArgumentList $ArgumentLine -WorkingDirectory $Root -PassThru -WindowStyle Hidden
    Set-Content -LiteralPath $PidFile -Value ([string]$Process.Id) -Encoding ASCII
    $Healthy = $false
    for ($Attempt = 0; $Attempt -lt 40; $Attempt++) {
        if ($Process.HasExited) { break }
        Start-Sleep -Milliseconds 500
        try {
            $Health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
            if ($Health.ok -and $Health.service -eq 'game-achievement-hub') { $Healthy = $true; break }
        } catch {}
    }
    if (-not $Healthy) {
        $Tail = if (Test-Path -LiteralPath $LogFile) { (Get-Content -LiteralPath $LogFile -Tail 12 -ErrorAction SilentlyContinue) -join [Environment]::NewLine } else { '' }
        if ($Process.HasExited) { throw ("後端啟動後立即停止。`n{0}" -f $Tail) }
        throw ("後端在等待時間內未通過健康檢查。`n{0}" -f $Tail)
    }

    Header '服務執行中'
    Write-Host ' [OK] 後端服務已成功啟動' -ForegroundColor Green
    Write-Host ' [OK] 資料庫連線與 API 健康檢查通過' -ForegroundColor Green
    Write-Host ''
    Write-Host (" 專案位置：{0}" -f $Root) -ForegroundColor Gray
    Write-Host ' 服務位址：http://127.0.0.1:8000' -ForegroundColor Gray
    Write-Host ' 健康檢查：http://127.0.0.1:8000/api/health' -ForegroundColor Gray
    Write-Host (" 執行日誌：{0}" -f $LogFile) -ForegroundColor Gray
    Write-Host ''
    Write-Host ' 請保持此視窗開啟。按 Ctrl+C 可停止後端服務。' -ForegroundColor Yellow
    Write-Host ' 一般網頁請求只會寫入日誌，不再刷滿此視窗。' -ForegroundColor DarkGray
    Write-Host '------------------------------------------------------------' -ForegroundColor DarkCyan

    try {
        while (-not $Process.HasExited) { Start-Sleep -Seconds 1 }
        $ExitCode = [int]$Process.ExitCode
    } catch [System.Management.Automation.PipelineStoppedException] {
        $ExitCode = 0
    } finally {
        Stop-BackendChild $Process
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    }
    Write-Host ''
    if ($ExitCode -eq 0) { Write-Host '後端服務已停止。' -ForegroundColor Yellow }
    else { Write-Host ("後端異常停止，結束代碼：{0}。請查看日誌。" -f $ExitCode) -ForegroundColor Red }
    Finish $ExitCode
} catch {
    Stop-BackendChild $Process
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Header '啟動失敗'
    Write-Host (" [錯誤] {0}" -f $_.Exception.Message) -ForegroundColor Red
    Write-Host ''
    Write-Host ' 建議：執行「檢查後端.cmd」或查看 logs 資料夾中的最新日誌。' -ForegroundColor Yellow
    Finish 1
}
