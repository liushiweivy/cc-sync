@echo off
rem Serve a folder over LAN so the other machine can download the zip via browser.
rem Pure ASCII content by convention; Chinese only in file names.
rem CCS_SHARE_DIR env overrides the shared folder (default: sibling dir E:\cc-sync).
cd /d %~dp0
set PY=python
if exist "%~dp0python-path.txt" set /p PY=<"%~dp0python-path.txt"
if not defined CCS_SHARE_DIR set CCS_SHARE_DIR=E:\cc-sync
title cc-sync LAN share :8899
echo.
echo  Serving %CCS_SHARE_DIR% on port 8899 ...
for /f %%a in ('powershell -NoProfile -c "(Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object {$_.IPAddress -match '^(192\.168\.|10\.|172\.)'}).IPAddress"') do (
  echo    On the other machine open:  http://%%a:8899/
)
echo.
echo  Download the newest cc-env-*.zip. Ctrl+C to stop.
echo.
"%PY%" -m http.server 8899 --directory "%CCS_SHARE_DIR%" --bind 0.0.0.0
pause
