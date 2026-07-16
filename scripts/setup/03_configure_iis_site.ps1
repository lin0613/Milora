param(
 [string]$SiteName='GameAchievementHub',
 [int]$Port=817,
 [switch]$NonInteractive
)
$ErrorActionPreference='Stop'
function Finish([int]$Code){Write-Host '';if(-not $NonInteractive){[void](Read-Host '處理已完成，請查看上方結果。按 Enter 關閉此視窗')};exit $Code}
try{
 Import-Module WebAdministration
 $Root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
 $SitePath=Join-Path $Root 'site'
 try{Set-WebConfigurationProperty -PSPath 'MACHINE/WEBROOT/APPHOST' -Filter 'system.webServer/proxy' -Name 'enabled' -Value 'True'}catch{throw '找不到 ARR Proxy 設定。請先安裝 IIS Application Request Routing 3。'}
 if(Test-Path "IIS:\Sites\$SiteName"){Set-ItemProperty "IIS:\Sites\$SiteName" -Name physicalPath -Value $SitePath}else{New-Website -Name $SiteName -PhysicalPath $SitePath -Port $Port -IPAddress '*'|Out-Null}
 $FirewallName="遊戲成就紀錄器 TCP $Port"
 if(-not(Get-NetFirewallRule -DisplayName $FirewallName -ErrorAction SilentlyContinue)){New-NetFirewallRule -DisplayName $FirewallName -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow|Out-Null}
 Start-Website -Name $SiteName
 Write-Host ("IIS 測試網站已建立：http://127.0.0.1:{0}" -f $Port) -ForegroundColor Green
 Finish 0
}catch{Write-Host ("IIS 網站設定失敗：{0}" -f $_.Exception.Message) -ForegroundColor Red;Finish 1}
