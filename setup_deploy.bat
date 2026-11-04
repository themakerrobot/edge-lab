@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 더블클릭용 - setup_deploy.ps1 을 실행 정책 우회(Bypass)로 돌린다. .ps1 을 직접 더블클릭하면 메모장으로 열린다.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_deploy.ps1" %*
echo.
pause
