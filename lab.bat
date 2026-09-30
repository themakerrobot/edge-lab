@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 코딩 실습 — JupyterLab 을 전용 창으로 연다. 창을 닫으면 JupyterLab 도 꺼진다 (lab.py)
rem 노트북 원본은 notebooks\ , 실제로 쓰는 곳은 작업폴더(문서\Edge Lab\notebooks)
rem 바탕화면 바로가기 만들기:  lab.bat /shortcut

rem venv python 을 바로 쓴다 (run.bat 과 같은 순서 — 배포 번들은 python\ + pylib\)
if exist "%~dp0venv\Scripts\python.exe" (
  set "PY=%~dp0venv\Scripts\python.exe"
) else if exist "%~dp0python\python.exe" (
  set "PY=%~dp0python\python.exe"
  set "PYTHONPATH=%~dp0pylib"
) else (
  echo [WARN] venv not found - using system python
  set "PY=python"
)

if /i "%~1"=="/shortcut" goto shortcut

rem 인터넷 없이 — 모델을 받으러 나가지 않게
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set YOLO_OFFLINE=1
set "YOLO_CONFIG_DIR=%~dp0.ultralytics"
if not exist "%~dp0.ultralytics" mkdir "%~dp0.ultralytics"

"%PY%" "%~dp0lab.py" %*
if errorlevel 1 pause
exit /b

:shortcut
rem 바탕화면에 "AI 코딩 실습" 바로가기 — 아이콘은 edge-lab.ico, 번들에서는 edge-lab.exe 의 것 (둘 다 없으면 기본)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\AI 코딩 실습.lnk');" ^
  "$s.TargetPath='%~dp0lab.bat'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7;" ^
  "if(Test-Path '%~dp0edge-lab.ico'){$s.IconLocation='%~dp0edge-lab.ico'}elseif(Test-Path '%~dp0edge-lab.exe'){$s.IconLocation='%~dp0edge-lab.exe,0'}; $s.Save()"
echo 바탕화면에 "AI 코딩 실습" 바로가기를 만들었어요.
pause
