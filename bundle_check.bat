@echo off
REM ==========================================================================
REM  vapi-od : deployment check (run inside the extracted bundle folder)
REM   1) python/packages  2) model load  3) start server  4) call all services
REM ==========================================================================
setlocal
cd /d "%~dp0"

if exist "python\python.exe" (
  set PY=python\python.exe
  set PYTHONPATH=%~dp0pylib
) else if exist "venv\Scripts\python.exe" (
  set PY=venv\Scripts\python.exe
) else (
  set PY=python
)
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set YOLO_OFFLINE=1
set YOLO_CONFIG_DIR=%~dp0.ultralytics
if not exist "%~dp0.ultralytics" mkdir "%~dp0.ultralytics"
set VAPI_NO_BROWSER=1

echo.
echo === [1/4] python / packages ===
%PY% -c "import sys;print('  python', sys.version.split()[0])" || goto :fail
%PY% -c "import openvino,cv2,numpy,fastapi,ultralytics,easyocr,openvino_genai,mediapipe;print('  import OK')" || goto :fail

echo.
echo === [2/4] model load ===
%PY% check.py || goto :fail

echo.
echo === [3/4] start server (model loading takes 1-2 min) ===
start "vapi-od-check" /min cmd /c "%PY% main.py"

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
%PY% smoke_test.py http://localhost:57711
set RESULT=%ERRORLEVEL%

taskkill /fi "windowtitle eq vapi-od-check*" /t /f >nul 2>&1

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
