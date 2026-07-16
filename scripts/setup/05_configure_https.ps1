param(
 [Parameter(Mandatory=$true)][string]$CertificateThumbprint,
 [string]$SiteName='GameAchievementHub',
 [Parameter(Mandatory=$true)][string]$HostName,
 [int]$Port=817,
 [switch]$NonInteractive
)
$ErrorActionPreference='Stop'
function Finish([int]$Code){Write-Host '';if(-not $NonInteractive){[void](Read-Host '處理已完成，請查看上方結果。按 Enter 關閉此視窗')};exit $Code}
try{
 Import-Module WebAdministration
 $Thumbprint=$CertificateThumbprint.Replace(' ','').ToUpper()
 $null=Get-Item "Cert:\LocalMachine\My\$Thumbprint" -ErrorAction Stop
 Get-WebBinding -Name $SiteName -Protocol http -Port $Port -ErrorAction SilentlyContinue|Remove-WebBinding
 $Binding=Get-WebBinding -Name $SiteName -Protocol https -Port $Port -HostHeader $HostName -ErrorAction SilentlyContinue
 if(-not $Binding){New-WebBinding -Name $SiteName -Protocol https -Port $Port -IPAddress '*' -HostHeader $HostName -SslFlags 1}
 (Get-WebBinding -Name $SiteName -Protocol https -Port $Port -HostHeader $HostName).AddSslCertificate($Thumbprint,'My')
 Write-Host ("HTTPS 已綁定：https://{0}:{1}" -f $HostName,$Port) -ForegroundColor Green
 Finish 0
}catch{Write-Host ("HTTPS 設定失敗：{0}" -f $_.Exception.Message) -ForegroundColor Red;Finish 1}
