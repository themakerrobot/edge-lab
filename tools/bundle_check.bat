@echo off
chcp 65001 >nul
REM ==========================================================================
REM  전체 점검 — 배포 번들에서도, 개발 설치(tools\ 안)에서도 돈다.
REM   1) python/packages  2) model load  3) start server  4) call all services
REM ==========================================================================
setlocal
rem 이 파일이 tools\ 안에 있으면 프로젝트 루트로 올라간다 (번들에서는 이미 루트)
cd /d "%~dp0"
if not exist main.py if exist "..\main.py" cd ..
set "ROOT=%CD%\"
if not exist main.py (echo [FAIL] main.py 를 찾을 수 없습니다 & (if not defined CI pause) & exit /b 1)

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
set VAPI_NO_BROWSER=1
rem 서버 출력을 파일로 돌리면 파이썬이 PC 기본 인코딩으로 쓴다 — 한글 · 기호에서 멈추지 않게 UTF-8 로
set PYTHONUTF8=1

echo.
echo === [1/4] python / packages ===
%PY% -c "import sys;print('  python', sys.version.split()[0])" || goto :fail
%PY% -c "import openvino,cv2,numpy,fastapi,easydetect,easyocr,openvino_genai,mediapipe;print('  import OK')" || goto :fail

echo.
echo === [2/4] model load ===
if exist check.py (%PY% check.py) else (%PY% tools\check.py)
if errorlevel 1 goto :fail

echo.
echo === [3/4] start server (model loading takes 1-2 min) ===
rem 서버가 찍는 것은 bundle_check_server.log 에 남긴다 — 실패하면 아래에서 마지막 줄들을 보여 준다
start "bundle-check" /min cmd /c "%PY% main.py > bundle_check_server.log 2>&1"

rem 서버를 기다리는 최대 시간(초). GPU 없는 PC(CPU 로만 모델을 올림)는 BC_WAIT 를 늘린다
if not defined BC_WAIT set BC_WAIT=300
set /a WAIT=0
:waitloop
rem timeout 은 입력 창이 없는 곳(자동 시험 · 리다이렉트)에서 바로 끝나 버린다 — ping 으로 5초를 쉰다
ping -n 6 127.0.0.1 >nul
set /a WAIT+=5
curl -s -m 3 http://localhost:57711/ready | findstr /c:"\"ready\":true" >nul && goto :ready
if %WAIT% geq %BC_WAIT% (echo [FAIL] server did not start within %BC_WAIT%s & goto :fail)
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

taskkill /fi "windowtitle eq bundle-check*" /t /f >nul 2>&1

echo.
if "%RESULT%"=="0" (
  echo ==========================================
  echo   CHECK PASSED - ready to use
  echo ==========================================
) else (
  echo ==========================================
  echo   FAILURES FOUND - see the list above
  echo ==========================================
  call :serverlog
)
if not defined CI pause
exit /b %RESULT%

:fail
taskkill /fi "windowtitle eq bundle-check*" /t /f >nul 2>&1
echo.
echo CHECK FAILED - see messages above.
call :serverlog
if not defined CI pause
exit /b 1

:serverlog
if not exist bundle_check_server.log exit /b 0
echo.
echo --- server log (last 60 lines: bundle_check_server.log) ---
powershell -NoProfile -Command "Get-Content -Encoding UTF8 -Tail 60 bundle_check_server.log"
exit /b 0
