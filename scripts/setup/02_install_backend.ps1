param([switch]$NonInteractive)
$ErrorActionPreference='Stop'
function Finish([int]$Code){Write-Host '';if(-not $NonInteractive){[void](Read-Host '處理已完成，請查看上方結果。按 Enter 關閉此視窗')};exit $Code}
try{
 $Root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
 Set-Location -LiteralPath $Root
 if(-not(Get-Command py -ErrorAction SilentlyContinue)){throw '找不到 Python Launcher。請先安裝 Python 3.12 或更新版本。'}
 py -3 -m venv .venv;if($LASTEXITCODE -ne 0){throw '建立 Python 虛擬環境失敗。'}
 & "$Root\.venv\Scripts\python.exe" -m pip install --upgrade pip;if($LASTEXITCODE -ne 0){throw '更新 pip 失敗。'}
 & "$Root\.venv\Scripts\python.exe" -m pip install -r "$Root\requirements.txt";if($LASTEXITCODE -ne 0){throw '安裝後端套件失敗。'}
 if(-not(Test-Path -LiteralPath "$Root\.env")){Copy-Item "$Root\.env.example" "$Root\.env";Write-Host '已建立 .env，請檢查郵件與資料庫設定。' -ForegroundColor Yellow}
 $env:PYTHONUTF8='1';$env:PYTHONPATH=$Root;$env:DATABASE_PATH=(Join-Path $Root 'data\app.db')
 & "$Root\.venv\Scripts\python.exe" -c "from backend.main import init_db; init_db(); print('database initialization ok')";if($LASTEXITCODE -ne 0){throw '資料庫初始化失敗。'}
 Write-Host '後端安裝完成。' -ForegroundColor Green
 Finish 0
}catch{Write-Host ("後端安裝失敗：{0}" -f $_.Exception.Message) -ForegroundColor Red;Finish 1}
