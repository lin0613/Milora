@echo off
chcp 65001 >nul
setlocal
if /i "%~1"=="--elevated" goto run
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '--elevated' -Verb RunAs"
if errorlevel 1 pause
exit /b
:run
if not exist "%~dp0scripts\verify_installation.ps1" (
  echo Required PowerShell script is missing: scripts\verify_installation.ps1
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\verify_installation.ps1"
exit /b %errorlevel%
