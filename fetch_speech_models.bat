@echo off
REM ==========================================================================
REM  fetch_speech_models.bat
REM  STT(Whisper)/TTS(Supertonic) 모델을 받아서 leeyunjai/vapi-od 에 올린다.
REM  실행 위치 : 프로젝트 루트 (venv 가 있는 곳)
REM  필요 : hf auth login 완료(또는 아래에서 토큰 입력), 인터넷
REM ==========================================================================
setlocal
cd /d "%~dp0"

set HF=venv\Scripts\hf.exe
if not exist %HF% (echo [ERROR] venv not found - run setup first & exit /b 1)

echo.
echo === [1/4] download STT : whisper-small INT8 (OpenVINO, Apache-2.0) ===
%HF% download OpenVINO/whisper-small-int8-ov --local-dir models\stt
if errorlevel 1 (echo [ERROR] STT download failed & exit /b 1)

echo.
echo === [2/4] download TTS : Supertonic (ONNX) ===
%HF% download Supertone/supertonic --local-dir models\tts
if errorlevel 1 (echo [ERROR] TTS download failed & exit /b 1)

echo.
echo === [3/4] upload STT -> leeyunjai/vapi-od : stt/ ===
%HF% upload leeyunjai/vapi-od models\stt stt --commit-message "add whisper-small-int8 STT"
if errorlevel 1 (echo [ERROR] STT upload failed - check write token & exit /b 1)

echo.
echo === [4/4] upload TTS -> leeyunjai/vapi-od : tts/ ===
%HF% upload leeyunjai/vapi-od models\tts tts --commit-message "add supertonic TTS"
if errorlevel 1 (echo [ERROR] TTS upload failed - check write token & exit /b 1)

echo.
echo [DONE] HF repo 에 stt/, tts/ 폴더가 생겼는지 확인하세요.
echo        이후 다른 기기는 setup_deploy.ps1 만으로 함께 받아진다.
pause
