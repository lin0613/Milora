param([switch]$NonInteractive)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
$LogFile=$null
function Finish([int]$Code){Write-Host '';if(-not $NonInteractive){[void](Read-Host '處理已完成，請查看上方結果。按 Enter 關閉此視窗')};exit $Code}
function Write-Log([string]$Message,[string]$Level='INFO'){
 $stamp=Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
 $line="[$stamp][$Level] $Message"
 $color=if($Level -eq 'ERROR'){'Red'}elseif($Level -eq 'OK'){'Green'}elseif($Level -eq 'WARN'){'Yellow'}else{'Cyan'}
 Write-Host $line -ForegroundColor $color
 if($LogFile){$line|Out-File -LiteralPath $LogFile -Encoding utf8 -Append}
}
try{
 $logDir=Join-Path $Root 'logs\verify';New-Item -ItemType Directory -Path $logDir -Force|Out-Null
 $LogFile=Join-Path $logDir ("verify-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
 Write-Log '步驟 1/6：正在確認專案位置與必要檔案。'
 if(-not(Test-Path -LiteralPath (Join-Path $Root '.achievement-hub-root'))){throw '找不到專案根目錄標記 .achievement-hub-root。'}
 if(-not(Test-Path -LiteralPath (Join-Path $Root 'data\app.db'))){throw '找不到正式資料庫 data\app.db。'}
 Write-Log ("已確認專案位置：{0}" -f $Root) 'OK'

 Write-Log '步驟 2/6：正在尋找可用的 Python。'
 $Python=Join-Path $Root '.venv\Scripts\python.exe'
 if(-not(Test-Path -LiteralPath $Python)){$command=Get-Command python.exe -ErrorAction SilentlyContinue;if(-not $command){throw '找不到 Python 或 .venv。'};$Python=$command.Source}
 Write-Log ("使用 Python：{0}" -f $Python) 'OK'

 $env:PYTHONUTF8='1';$env:PYTHONDONTWRITEBYTECODE='1';$env:PYTHONPATH=$Root;$env:DATABASE_PATH=Join-Path $Root 'data\app.db'
 Set-Location -LiteralPath $Root
 Write-Log '步驟 3/6：正在驗證專案結構、檔名、執行腳本及四遊資料。'
 Write-Log '已允許安裝後正常存在的 .venv、執行日誌與 SQLite 暫存檔，不會再把它們誤判為正式包垃圾檔。'

 Write-Log '步驟 4/6：正在驗證檔案雜湊與 SQLite 完整性。'
 Write-Log '步驟 5/6：正在載入後端並檢查必要 API 路由。'
 $output=& $Python 'tools\verify\run_full_release_check.py' '--root' '.' '--allow-runtime-files' '--deep' '--write-report' 2>&1
 $exitCode=$LASTEXITCODE
 foreach($line in @($output)){if($null -ne $line){[string]$line|Out-File -LiteralPath $LogFile -Encoding utf8 -Append;Write-Host ([string]$line)}}
 if($exitCode -ne 0){throw ("完整驗證未通過，Python 結束代碼：{0}。完整輸出已寫入：{1}" -f $exitCode,$LogFile)}

 Write-Log '步驟 6/6：完整驗證通過。' 'OK'
 Write-Log ("驗證日誌：{0}" -f $LogFile) 'OK'
 Finish 0
}catch{
 Write-Log ("完整驗證失敗：{0}" -f $_.Exception.Message) 'ERROR'
 if($LogFile){Write-Host ("請查看完整日誌：{0}" -f $LogFile) -ForegroundColor Yellow}
 Finish 1
}
