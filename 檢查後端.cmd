@echo off
chcp 65001 >nul
cls
setlocal EnableExtensions
if /i "%~1"=="--elevated" goto run
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '--elevated' -Verb RunAs"
if errorlevel 1 (
  echo.
  echo Unable to request administrator privileges.
  pause
)
exit /b
:run
cls
if not exist "%~dp0scripts\check_backend.ps1" (
  echo Required PowerShell script is missing: scripts\check_backend.ps1
  echo.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\check_backend.ps1"
exit /b %errorlevel%
