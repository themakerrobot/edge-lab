@echo off
REM ==========================================================================
REM  vapi-od : build portable bundle (Windows)
REM  output : dist\vapi-od-<VERSION>.zip   (extract -> run.bat, no python needed)
REM  usage  : make_bundle.bat [version]    e.g. make_bundle.bat 1.0.0
REM  needs  : this PC has python + completed models\ + internet
REM ==========================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

set VERSION=%1
if "%VERSION%"=="" set VERSION=1.0.0
set BUILD=build\vapi-od
set DIST=dist

echo.
echo === [1/7] preflight ===
if not exist models\vlm (echo [ERROR] models\ not found - run setup first & exit /b 1)
if not exist main.py  (echo [ERROR] run from project root & exit /b 1)
REM static assets - a bundle built without these ships a broken UI
for %%F in (
  view_project\index.html
  view_project\blocks.html
  view_project\fonts\fonts.css
  view_project\blockly\blockly_compressed.js
  view_project\blockly\blocks_compressed.js
  view_project\blockly\javascript_compressed.js
  view_project\blockly\msg\ko.js
  view_project\blockly\msg\en.js
  view_project\blockly\media\sprites.svg
  view_project\blockly\media\delete-icon.svg
) do (
  if not exist %%F (echo [ERROR] static asset missing: %%F & exit /b 1)
)
echo   static assets OK

for /f %%v in ('python -c "import sys;print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))"') do set PYVER=%%v
if "%PYVER%"=="3.10" set EMBED=3.10.11
if "%PYVER%"=="3.11" set EMBED=3.11.9
if "%PYVER%"=="3.12" set EMBED=3.12.10
if "%PYVER%"=="3.13" set EMBED=3.13.7
if "%EMBED%"=="" (echo [ERROR] unsupported python %PYVER% ^(need 3.10-3.13^) & exit /b 1)
set PYTAG=%PYVER:.=%
echo   python %PYVER% -^> embeddable %EMBED%

echo.
echo === [2/7] clean previous build ===
if exist %BUILD% rmdir /s /q %BUILD%
mkdir %BUILD%\python
mkdir %BUILD%\pylib
if not exist %DIST% mkdir %DIST%

echo.
echo === [3/7] download embeddable python ===
set EMBEDZIP=build\python-embed.zip
if not exist %EMBEDZIP% (
  curl -L -o %EMBEDZIP% https://www.python.org/ftp/python/%EMBED%/python-%EMBED%-embed-amd64.zip
  if errorlevel 1 (echo [ERROR] download failed & exit /b 1)
)
tar -xf %EMBEDZIP% -C %BUILD%\python
if errorlevel 1 (echo [ERROR] extract failed & exit /b 1)

REM rewrite ._pth so bundled pylib is on the module path
> %BUILD%\python\python%PYTAG%._pth (
  echo python%PYTAG%.zip
  echo .
  echo ..\pylib
  echo ..
  echo import site
)

echo.
echo === [4/7] install packages into pylib ===
python -m pip install --upgrade pip --quiet
python -m pip install --target %BUILD%\pylib ^
    openvino openvino-genai fastapi "uvicorn[standard]" ^
    ultralytics opencv-python pillow numpy easyocr python-multipart
if errorlevel 1 (echo [ERROR] package install failed & exit /b 1)
REM pyzbar is optional (QR works via OpenCV)
python -m pip install --target %BUILD%\pylib pyzbar >nul 2>&1

echo.
echo === [5/7] copy sources and models ===
for %%F in (main.py engines.py prompts.py check.py smoke_test.py README.md) do (
  copy /y %%F %BUILD%\ >nul
  if errorlevel 1 (echo [ERROR] copy failed: %%F & exit /b 1)
)
copy /y bundle_check.bat %BUILD%\ >nul
xcopy /e /i /q /y view_project %BUILD%\view_project >nul
echo   copying models\ (several GB, takes a few minutes) ...
xcopy /e /i /q /y models %BUILD%\models >nul
if errorlevel 1 (echo [ERROR] models copy failed & exit /b 1)

REM bundle launcher (ASCII only, CRLF via echo)
> %BUILD%\run.bat (
  echo @echo off
  echo cd /d "%%~dp0"
  echo set PYTHONPATH=%%~dp0pylib
  echo set HF_HUB_OFFLINE=1
  echo set TRANSFORMERS_OFFLINE=1
  echo set YOLO_OFFLINE=1
  echo set YOLO_CONFIG_DIR=%%~dp0.ultralytics
  echo if not exist "%%~dp0.ultralytics" mkdir "%%~dp0.ultralytics"
  echo echo Starting vapi-od ... browser opens automatically when ready ^(1-2 min^).
  echo python\python.exe main.py
  echo pause
)
> %BUILD%\VERSION.txt echo vapi-od %VERSION%

echo.
echo === [6/7] verify bundled python ===
for %%F in (main.py engines.py prompts.py check.py smoke_test.py run.bat bundle_check.bat) do (
  if not exist %BUILD%\%%F (echo [ERROR] missing in bundle: %%F & exit /b 1)
)
%BUILD%\python\python.exe -c "import openvino,cv2,numpy;print('  import OK  openvino',openvino.__version__.split('-')[0])"
if errorlevel 1 (echo [ERROR] import failed inside bundle & exit /b 1)

echo.
echo === [7/7] compress ===
set ZIP=%DIST%\vapi-od-%VERSION%.zip
if exist %ZIP% del %ZIP%
tar -a -c -f %ZIP% -C build vapi-od
if errorlevel 1 (echo [ERROR] compress failed & exit /b 1)

for %%A in (%ZIP%) do set SIZE=%%~zA
set /a SIZEMB=%SIZE%/1048576
echo.
echo DONE: %ZIP%  (%SIZEMB% MB)
echo   target PC: extract -^> run.bat      check: bundle_check.bat
endlocal