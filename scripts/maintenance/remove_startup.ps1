param([switch]$NonInteractive,[string]$ProjectRoot='')
$ErrorActionPreference='Stop'
$Root=if($ProjectRoot){[IO.Path]::GetFullPath($ProjectRoot)}else{Split-Path -Parent (Split-Path -Parent $PSScriptRoot)}
function Finish([int]$Code){Write-Host '';if(-not $NonInteractive){[void](Read-Host '處理已完成，請查看上方結果。按 Enter 關閉此視窗')};exit $Code}
try{
 Write-Host '正在檢查並移除本專案的 Windows 自動啟動設定……' -ForegroundColor Cyan
 $removed=New-Object 'System.Collections.Generic.List[string]'
 foreach($name in @('GameAchievementBackend','WuwaAchievementBackend','AchievementHubBackend')){if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue;Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction Stop;$removed.Add("工作排程：$name")}}
 $startupDirs=@([Environment]::GetFolderPath('Startup'),[Environment]::GetFolderPath('CommonStartup'))|Where-Object{$_}
 foreach($dir in $startupDirs){foreach($file in Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue){$name=$file.Name.ToLowerInvariant();if($name -match 'achievement|wuwa|gameachievement'){try{$content='';if($file.Extension -in '.cmd','.bat','.ps1','.url'){$content=Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue};if($content -match [regex]::Escape($Root) -or $name -match 'gameachievement|wuwaachievement|achievementhub'){Remove-Item -LiteralPath $file.FullName -Force;$removed.Add("啟動資料夾：$($file.FullName)")}}catch{}}}}
 foreach($scope in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\Run','HKLM:\Software\Microsoft\Windows\CurrentVersion\Run')){if(Test-Path $scope){$props=(Get-ItemProperty -Path $scope).PSObject.Properties|Where-Object{$_.Name -notmatch '^PS'};foreach($prop in $props){$value=[string]$prop.Value;if($prop.Name -match 'GameAchievement|WuwaAchievement|AchievementHub' -or $value -match [regex]::Escape($Root)){Remove-ItemProperty -Path $scope -Name $prop.Name -Force -ErrorAction SilentlyContinue;$removed.Add("登錄自啟動：$scope\$($prop.Name)")}}}}
 foreach($name in @('GameAchievementBackend','WuwaAchievementBackend','AchievementHubBackend')){$service=Get-Service -Name $name -ErrorAction SilentlyContinue;if($service){if($service.Status -ne 'Stopped'){Stop-Service -Name $name -Force -ErrorAction SilentlyContinue};& sc.exe delete $name|Out-Null;$removed.Add("Windows 服務：$name")}}
 if($removed.Count){Write-Host '已移除下列本專案自動啟動設定：' -ForegroundColor Green;$removed|ForEach-Object{Write-Host (" - {0}" -f $_)}}else{Write-Host '未發現本專案的自動啟動設定；目前已符合手動啟動規則。' -ForegroundColor Green}
 Finish 0
}catch{Write-Host ("移除自動啟動設定失敗：{0}" -f $_.Exception.Message) -ForegroundColor Red;Finish 1}
