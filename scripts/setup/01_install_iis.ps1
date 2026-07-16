param([switch]$NonInteractive)
$ErrorActionPreference='Stop'
function Finish([int]$Code){Write-Host '';if(-not $NonInteractive){[void](Read-Host '處理已完成，請查看上方結果。按 Enter 關閉此視窗')};exit $Code}
try{
 $features=@('IIS-WebServerRole','IIS-WebServer','IIS-CommonHttpFeatures','IIS-StaticContent','IIS-DefaultDocument','IIS-HttpErrors','IIS-HttpLogging','IIS-RequestFiltering','IIS-ManagementConsole')
 foreach($feature in $features){Enable-WindowsOptionalFeature -Online -FeatureName $feature -All -NoRestart | Out-Null}
 Write-Host 'IIS 已啟用。接著請安裝 IIS URL Rewrite 2 與 Application Request Routing 3。' -ForegroundColor Green
 Finish 0
}catch{Write-Host ("IIS 安裝失敗：{0}" -f $_.Exception.Message) -ForegroundColor Red;Finish 1}
