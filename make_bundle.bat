@echo off
REM ===========================================================================
REM  vapi-od : 포터블 번들 생성 (Windows)
REM  결과물 : dist\vapi-od-<VERSION>.zip  (압축 풀고 run.bat 실행하면 끝)
REM  전제   : 이 PC에 Python + 설치 완료된 models\ 가 있고, 인터넷이 된다.
REM  사용법 : make_bundle.bat [버전]      예) make_bundle.bat 1.0.0
REM ===========================================================================
setlocal enabledelayedexpansion
cd /d %~dp0

set VERSION=%1
if "%VERSION%"=="" set VERSION=1.0.0
set BUILD=build\vapi-od
set DIST=dist

echo.
echo === [1/7] 사전 점검 ===
if not exist models\vlm (echo [ERROR] models\ 가 없습니다. setup 을 먼저 실행하세요. & exit /b 1)
if not exist main.py  (echo [ERROR] 프로젝트 루트에서 실행하세요. & exit /b 1)

for /f %%v in ('python -c "import sys;print(f\"{sys.version_info.major}.{sys.version_info.minor}\")"') do set PYVER=%%v
if "%PYVER%"=="3.10" set EMBED=3.10.11
if "%PYVER%"=="3.11" set EMBED=3.11.9
if "%PYVER%"=="3.12" set EMBED=3.12.10
if "%PYVER%"=="3.13" set EMBED=3.13.7
if "%EMBED%"=="" (echo [ERROR] 지원하지 않는 파이썬 %PYVER% ^(3.10~3.13 필요^) & exit /b 1)
set PYTAG=%PYVER:.=%
echo   python %PYVER% -^> embeddable %EMBED%

echo.
echo === [2/7] 이전 빌드 정리 ===
if exist %BUILD% rmdir /s /q %BUILD%
mkdir %BUILD%\python
mkdir %BUILD%\pylib
if not exist %DIST% mkdir %DIST%

echo.
echo === [3/7] embeddable python 내려받기 ===
set EMBEDZIP=build\python-embed.zip
if not exist %EMBEDZIP% (
  curl -L -o %EMBEDZIP% https://www.python.org/ftp/python/%EMBED%/python-%EMBED%-embed-amd64.zip
  if errorlevel 1 (echo [ERROR] 다운로드 실패 & exit /b 1)
)
tar -xf %EMBEDZIP% -C %BUILD%\python
if errorlevel 1 (echo [ERROR] 압축 해제 실패 & exit /b 1)

REM ._pth 재작성: 번들 pylib 를 모듈 경로에 추가
> %BUILD%\python\python%PYTAG%._pth (
  echo python%PYTAG%.zip
  echo .
  echo ..\pylib
  echo ..
  echo import site
)

echo.
echo === [4/7] 패키지 설치 (pylib) ===
python -m pip install --upgrade pip --quiet
python -m pip install --target %BUILD%\pylib ^
    openvino openvino-genai fastapi "uvicorn[standard]" ^
    ultralytics opencv-python pillow numpy easyocr python-multipart
if errorlevel 1 (echo [ERROR] 패키지 설치 실패 & exit /b 1)
REM pyzbar 는 선택 (QR 은 OpenCV 로 동작)
python -m pip install --target %BUILD%\pylib pyzbar >nul 2>&1

echo.
echo === [5/7] 소스/모델 복사 ===
copy /y main.py engines.py prompts.py check.py smoke_test.py README.md %BUILD%\ >nul
xcopy /e /i /q /y view_project %BUILD%\view_project >nul
echo   models\ 복사 중 (수 GB, 몇 분 걸립니다)...
xcopy /e /i /q /y models %BUILD%\models >nul
if errorlevel 1 (echo [ERROR] models 복사 실패 & exit /b 1)

REM 번들 실행기
> %BUILD%\run.bat (
  echo @echo off
  echo cd /d %%~dp0
  echo set PYTHONPATH=%%~dp0pylib
  echo set HF_HUB_OFFLINE=1
  echo set TRANSFORMERS_OFFLINE=1
  echo set YOLO_OFFLINE=1
  echo set YOLO_CONFIG_DIR=%%~dp0.ultralytics
  echo echo vapi-od 시작 중... 모델 로딩이 끝나면 브라우저가 자동으로 열립니다 ^^^(1~2분^^^).
  echo python\python.exe main.py
  echo pause
)
> %BUILD%\VERSION.txt echo vapi-od %VERSION%

echo.
echo === [6/7] 번들 자체 점검 ===
copy /y bundle_check.bat %BUILD%\ >nul 2>&1
%BUILD%\python\python.exe -c "import sys; sys.path.insert(0,r'%CD%\%BUILD%\pylib'); import openvino, cv2, numpy; print('  import OK  openvino', openvino.__version__.split('-')[0])"
if errorlevel 1 (echo [ERROR] 번들 파이썬에서 import 실패 & exit /b 1)

echo.
echo === [7/7] 압축 ===
set ZIP=%DIST%\vapi-od-%VERSION%.zip
if exist %ZIP% del %ZIP%
tar -a -c -f %ZIP% -C build vapi-od
if errorlevel 1 (echo [ERROR] 압축 실패 & exit /b 1)

for %%A in (%ZIP%) do set SIZE=%%~zA
set /a SIZEMB=%SIZE%/1048576
echo.
echo 완료: %ZIP%  (%SIZEMB% MB)
echo   배포 기기에서: 압축 해제 -^> run.bat 실행 (파이썬 설치 불필요)
echo   점검하려면   : bundle_check.bat
endlocal