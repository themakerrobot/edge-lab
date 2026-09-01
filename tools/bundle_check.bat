@echo off
chcp 65001 >nul
REM ==========================================================================
REM  엣지 랩 : 전체 점검 — 배포 번들에서도, 개발 설치(tools\ 안)에서도 돈다.
REM   1) python/packages  2) model load  3) start server  4) call all services
REM ==========================================================================
setlocal
rem 이 파일이 tools\ 안에 있으면 프로젝트 루트로 올라간다 (번들에서는 이미 루트)
cd /d "%~dp0"
if not exist main.py if exist "..\main.py" cd ..
set "ROOT=%CD%\"
if not exist main.py (echo [FAIL] main.py 를 찾을 수 없습니다 & pause & exit /b 1)

if exist "python\python.exe" (
  rem 배포 번들 — 동봉된 파이썬
  set "PY=python\python.exe"
  set "PYTHONPATH=%ROOT%pylib"
) else if exist "venv\Scripts\python.exe" (
  rem 개발 설치 — setup_deploy.ps1 이 만든 venv
  set "PY=venv\Scripts\python.exe"
) else (
  set "PY=python"
)
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set YOLO_OFFLINE=1
set "YOLO_CONFIG_DIR=%ROOT%.ultralytics"
if not exist "%ROOT%.ultralytics" mkdir "%ROOT%.ultralytics"
set VAPI_NO_BROWSER=1

echo.
echo === [1/4] python / packages ===
%PY% -c "import sys;print('  python', sys.version.split()[0])" || goto :fail
%PY% -c "import openvino,cv2,numpy,fastapi,ultralytics,easyocr,openvino_genai,mediapipe;print('  import OK')" || goto :fail

echo.
echo === [2/4] model load ===
if exist check.py (%PY% check.py) else (%PY% tools\check.py)
if errorlevel 1 goto :fail

echo.
echo === [3/4] start server (model loading takes 1-2 min) ===
start "edge-lab-check" /min cmd /c "%PY% main.py"

set /a WAIT=0
:waitloop
timeout /t 5 /nobreak >nul
set /a WAIT+=5
curl -s -m 3 http://localhost:57711/ready | findstr /c:"\"ready\":true" >nul && goto :ready
if %WAIT% geq 300 (echo [FAIL] server did not start within 300s & goto :fail)
echo   loading models ... %WAIT%s
goto :waitloop

:ready
echo   server ready (%WAIT%s)

echo.
echo === [4/4] service check ===
if exist smoke_test.py (
  %PY% smoke_test.py http://localhost:57711
) else (
  %PY% tools\smoke_test.py http://localhost:57711
)
set RESULT=%ERRORLEVEL%

taskkill /fi "windowtitle eq edge-lab-check*" /t /f >nul 2>&1

echo.
if "%RESULT%"=="0" (
  echo ==========================================
  echo   CHECK PASSED - ready to use
  echo ==========================================
) else (
  echo ==========================================
  echo   FAILURES FOUND - see the list above
  echo ==========================================
)
pause
exit /b %RESULT%

:fail
echo.
echo CHECK FAILED - see messages above.
pause
exit /b 1
