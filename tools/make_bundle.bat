@echo off
chcp 65001 >nul
REM ==========================================================================
REM  edge-lab : build portable bundle (Windows)
REM  output : dist\edge-lab-<VERSION>.zip   (extract -> run.bat, no python needed)
REM  usage  : make_bundle.bat [version]    e.g. make_bundle.bat 1.0.0
REM  needs  : this PC has python + completed models\ + internet
REM ==========================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0.."
set "ROOT=%CD%\"
set "TOOLS=%~dp0"

set VERSION=%1
if exist "%ROOT%venv\Scripts\python.exe" (set "PY_LOCAL=%ROOT%venv\Scripts\python.exe") else (set "PY_LOCAL=python")
if "%VERSION%"=="" set VERSION=1.0.0
set BUILD=build\edge-lab
set DIST=dist

echo.
echo === [1/8] preflight ===
if not exist models\vlm (echo [ERROR] models\ not found - run setup first & exit /b 1)
if not exist main.py  (echo [ERROR] run from project root & exit /b 1)

for /f %%v in ('python -c "import sys;print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))"') do set PYVER=%%v
if "%PYVER%"=="3.10" set EMBED=3.10.11
if "%PYVER%"=="3.11" set EMBED=3.11.9
if "%PYVER%"=="3.12" set EMBED=3.12.10
if "%PYVER%"=="3.13" set EMBED=3.13.7
if "%EMBED%"=="" (echo [ERROR] unsupported python %PYVER% ^(need 3.10-3.13^) & exit /b 1)
set PYTAG=%PYVER:.=%
echo   python %PYVER% -^> embeddable %EMBED%

echo.
echo === [2/8] clean previous build ===
if exist %BUILD% rmdir /s /q %BUILD%
mkdir %BUILD%\python
mkdir %BUILD%\pylib
if not exist %DIST% mkdir %DIST%

echo.
echo === [3/8] download embeddable python ===
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
echo === [4/8] install packages into pylib ===
python -m pip install --upgrade pip --quiet
rem 루트의 requirements 로 설치한다 — 개발 PC 와 같은 버전이 번들에 들어가게
if exist "%ROOT%requirements.lock.txt" (
  python -m pip install --target %BUILD%\pylib -r "%ROOT%requirements.lock.txt"
) else (
  python -m pip install --target %BUILD%\pylib -r "%ROOT%requirements.txt"
)
if errorlevel 1 (echo [ERROR] package install failed & exit /b 1)

REM 번들에 들어간 패키지 버전을 남긴다 (문제 생겼을 때 비교용)
> %BUILD%\installed-packages.txt echo # bundled by make_bundle.bat %DATE% %TIME%
>> %BUILD%\installed-packages.txt echo # embeddable python %EMBED%
python -m pip list --path %BUILD%\pylib >> %BUILD%\installed-packages.txt 2>nul

echo.
echo === [5/8] build launcher exe ===
if exist "%TOOLS%launcher.py" if exist edge-lab.ico (
  "%PY_LOCAL%" -m pip install --quiet pyinstaller
  if errorlevel 1 (echo [WARN] pyinstaller install failed - skipping exe) else (
    "%PY_LOCAL%" -m PyInstaller --onefile --clean --noconfirm ^
      --name edge-lab --icon "%ROOT%edge-lab.ico" ^
      --distpath "%ROOT%." --workpath "%ROOT%build\exe" --specpath "%ROOT%build\exe" ^
      "%TOOLS%launcher.py"
    if errorlevel 1 (echo [WARN] exe build failed - continuing without exe)
  )
) else (
  echo   tools\launcher.py / edge-lab.ico not found - skipping exe
)

echo.
echo === [6/8] copy sources and models ===
for %%F in (main.py engines.py prompts.py paths.py hub.py mp_routes.py train_routes.py stats_routes.py code_routes.py speech_routes.py db_routes.py folderpick.py sysinfo.py themaker.py README.md) do (
  copy /y %%F %BUILD%\ >nul
  if errorlevel 1 (echo [ERROR] copy failed: %%F & exit /b 1)
)
rem 점검 도구는 tools\ 에 있고, 배포본에서는 루트에 두어 바로 실행되게 한다
for %%F in (check.py smoke_test.py bundle_check.bat) do (
  copy /y "%TOOLS%%%F" %BUILD%\ >nul
)
if exist edge-lab.exe copy /y edge-lab.exe %BUILD%\ >nul
REM edge-lab.ico 는 빌드 때 exe 에 심는 용도라 배포본에는 넣지 않는다 -
REM 확장자 숨김 상태에서 themaker(ico)와 themaker(exe)가 똑같이 보여 헷갈린다
xcopy /e /i /q /y view_project %BUILD%\view_project >nul
echo   copying models\ (several GB, takes a few minutes) ...
xcopy /e /i /q /y models %BUILD%\models >nul
if errorlevel 1 (echo [ERROR] models copy failed & exit /b 1)
REM 작업 파일은 프로그램 폴더 밖에 생긴다 (paths.py: 작업폴더=문서\Edge Lab,
REM 앱데이터=%%LOCALAPPDATA%%\EdgeLab). 번들에 data\ 를 만들지 않는다 -
REM USB 휴대용으로 쓸 때만 압축 푼 곳에 portable.txt 를 만들면 옆에 data\ 가 생긴다.
if exist %BUILD%\models\user rmdir /s /q %BUILD%\models\user
if exist %BUILD%\models\project rmdir /s /q %BUILD%\models\project
if exist %BUILD%\models\stats rmdir /s /q %BUILD%\models\stats
if exist %BUILD%\models\pycode rmdir /s /q %BUILD%\models\pycode
if exist %BUILD%\models\blocks rmdir /s /q %BUILD%\models\blocks
if exist %BUILD%\models\.appwin rmdir /s /q %BUILD%\models\.appwin

REM bundle launcher (ASCII only, CRLF via echo)
> %BUILD%\run.bat (
  echo @echo off
  echo chcp 65001 ^>nul
  echo cd /d "%%~dp0"
  echo set PYTHONPATH=%%~dp0pylib
  echo set HF_HUB_OFFLINE=1
  echo set TRANSFORMERS_OFFLINE=1
  echo set YOLO_OFFLINE=1
  echo set YOLO_CONFIG_DIR=%%~dp0.ultralytics
  echo if not exist "%%~dp0.ultralytics" mkdir "%%~dp0.ultralytics"
  echo echo Starting edge-lab ... browser opens automatically when ready ^(1-2 min^).
  echo python\python.exe main.py
  echo pause
)
> %BUILD%\VERSION.txt echo edge-lab %VERSION%

echo.
echo === [7/8] verify bundled python ===
for %%F in (main.py engines.py prompts.py paths.py hub.py mp_routes.py train_routes.py stats_routes.py code_routes.py speech_routes.py db_routes.py folderpick.py sysinfo.py themaker.py check.py smoke_test.py run.bat bundle_check.bat) do (
  if not exist %BUILD%\%%F (echo [ERROR] missing in bundle: %%F & exit /b 1)
)
REM 화면 일곱 — home.html 이 런처(/)다. 빠지면 첫 화면부터 안 뜬다.
for %%F in (view_project\home.html view_project\index.html view_project\blocks.html view_project\train.html view_project\options.html view_project\code.html view_project\talk.html) do (
  if not exist %BUILD%\%%F (echo [ERROR] missing in bundle: %%F & exit /b 1)
)
REM 일곱 화면이 함께 쓰는 공용 파일. tokens.css 는 색·치수에 화면 전환까지 갖고 있고,
REM shell 은 타이틀바와 [닫기], boot 는 모델 로딩 화면이다 — 하나만 빠져도 화면이 망가진다.
for %%F in (tokens.css ui.css shell.css shell.js apps.js icons.js boot.js tour.js sysbar.js split.js usage.js) do (
  if not exist %BUILD%\view_project\lib\%%F (echo [ERROR] missing in bundle: view_project\lib\%%F & exit /b 1)
)
REM 같이 넣어 나가는 외부 라이브러리 — 이게 빠지면 그 화면만 통째로 죽는다
for %%F in (lib\tf.min-3.11.0.js lib\jszip.min.js lib\cm\codemirror.js lib\cm\python.js lib\cm\show-hint.js blockly\blockly_compressed.js blockly\blocks_compressed.js blockly\javascript_compressed.js blockly\msg\ko.js blockly\msg\en.js) do (
  if not exist %BUILD%\view_project\%%F (echo [ERROR] missing in bundle: view_project\%%F & exit /b 1)
)
REM /docs 가 쓰는 Swagger UI — 없으면 [API Docs] 가 흰 화면이 된다.
REM FastAPI 기본값은 이것을 CDN 에서 받아 오므로 인터넷 없는 교실 PC 에서 안 나왔다.
for %%F in (swagger-ui-bundle.js swagger-ui.css LICENSE) do (
  if not exist %BUILD%\view_project\lib\swagger\%%F (echo [ERROR] missing in bundle: view_project\lib\swagger\%%F & exit /b 1)
)
REM 글꼴과 그림 — 폴더가 통째로 빠지면 화면이 기본 글꼴로 떨어진다
for %%D in (fonts assets) do (
  if not exist %BUILD%\view_project\%%D\ (echo [ERROR] missing in bundle: view_project\%%D\ & exit /b 1)
)
if not exist %BUILD%\view_project\fonts\fonts.css (echo [ERROR] missing in bundle: view_project\fonts\fonts.css & exit /b 1)
for %%F in (mobilenetv2_feat.xml mobilenetv2_feat.bin mobilenetv2_feat.json) do (
  if not exist %BUILD%\models\backbone\%%F (echo [ERROR] missing in bundle: models\backbone\%%F & exit /b 1)
)
%BUILD%\python\python.exe -c "import openvino,cv2,numpy;print('  import OK  openvino',openvino.__version__.split('-')[0])"
if errorlevel 1 (echo [ERROR] import failed inside bundle & exit /b 1)

echo.
echo === [8/8] compress ===
set ZIP=%DIST%\edge-lab-%VERSION%.zip
if exist %ZIP% del %ZIP%
tar -a -c -f %ZIP% -C build edge-lab
if errorlevel 1 (echo [ERROR] compress failed & exit /b 1)

REM cmd set /a is 32-bit; use PowerShell for multi-GB sizes
for /f %%S in ('powershell -NoProfile -Command "[math]::Round((Get-Item ''%ZIP%'').Length/1MB)"') do set SIZEMB=%%S
echo.
echo DONE: %ZIP%  (%SIZEMB% MB)
echo   target PC: extract -^> run.bat (double-click)   check: bundle_check.bat
endlocal