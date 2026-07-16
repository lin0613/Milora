@echo off
chcp 65001 >nul
cls
setlocal EnableExtensions
set "ROOT=%~dp0"
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
if not exist "%ROOT%scripts\stop_backend.ps1" (
  echo Required PowerShell script is missing: scripts\stop_backend.ps1
  echo.
  pause
  exit /b 1
)
if not exist "%ROOT%scripts\start_backend.ps1" (
  echo Required PowerShell script is missing: scripts\start_backend.ps1
  echo.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\stop_backend.ps1" -NonInteractive
if errorlevel 1 (
  echo.
  echo Backend stop failed. Restart aborted.
  echo.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\start_backend.ps1"
exit /b %errorlevel%
