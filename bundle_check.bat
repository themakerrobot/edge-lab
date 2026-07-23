@echo off
REM ===========================================================================
REM  vapi-od : 배포 점검 (번들을 푼 폴더에서 실행)
REM   1) 번들 파이썬/패키지 확인   2) 모델 로드 검증
REM   3) 서버 기동 후 전 서비스 실제 호출   4) 결과 요약
REM  사용법: bundle_check.bat
REM ===========================================================================
setlocal
cd /d %~dp0

if exist python\python.exe (
  set PY=python\python.exe
  set PYTHONPATH=%~dp0pylib
) else (
  set PY=python
)
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set YOLO_OFFLINE=1
set YOLO_CONFIG_DIR=%~dp0.ultralytics
set VAPI_NO_BROWSER=1

echo.
echo === [1/4] 파이썬 / 패키지 ===
%PY% -c "import sys;print('  python', sys.version.split()[0])" || (echo [FAIL] 파이썬 실행 불가 & goto :fail)
%PY% -c "import openvino,cv2,numpy,fastapi,ultralytics,easyocr,openvino_genai;print('  import OK')" || (echo [FAIL] 패키지 import 실패 & goto :fail)

echo.
echo === [2/4] 모델 로드 검증 ===
%PY% check.py || (echo [FAIL] 모델 검증 실패 & goto :fail)

echo.
echo === [3/4] 서버 기동 (모델 로딩 1~2분) ===
tasklist /fi "windowtitle eq vapi-od-check" 2>nul | find /i "cmd.exe" >nul
start "vapi-od-check" /min cmd /c "%PY% main.py"

set /a WAIT=0
:waitloop
timeout /t 5 /nobreak >nul
set /a WAIT+=5
curl -s -o nul -m 3 http://localhost:57711/system && goto :ready
if %WAIT% geq 300 (echo [FAIL] 서버가 300초 안에 뜨지 않았습니다 & goto :fail)
echo   대기 중... %WAIT%s
goto :waitloop

:ready
echo   서버 준비 완료 (%WAIT%s)

echo.
echo === [4/4] 서비스 점검 ===
%PY% smoke_test.py http://localhost:57711
set RESULT=%ERRORLEVEL%

taskkill /fi "windowtitle eq vapi-od-check*" /t /f >nul 2>&1

echo.
if "%RESULT%"=="0" (
  echo ============================================
  echo   점검 통과 - 이 기기에서 사용할 수 있습니다
  echo ============================================
) else (
  echo ============================================
  echo   FAIL 항목이 있습니다. 위 목록을 확인하세요
  echo ============================================
)
pause
exit /b %RESULT%

:fail
echo.
echo 점검 실패 - 위 메시지를 확인하세요.
pause
exit /b 1