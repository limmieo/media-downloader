@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================
REM Media Downloader - FastAPI Web Server Launcher
REM ============================================

REM Determine script directory and switch to project root
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"

echo ===========================================
echo   Media Downloader - Web Server Launcher
echo ===========================================
echo Working directory: %CD%
echo.

REM Activate Python virtual environment if available
set "VENV_ACTIVATE=%SCRIPT_DIR%venv\Scripts\activate.bat"
if exist "%VENV_ACTIVATE%" (
  echo Activating virtual environment...
  call "%VENV_ACTIVATE%"
) else (
  echo [Warning] Virtual environment not found at:
  echo          "%VENV_ACTIVATE%"
  echo Using system Python.
)

echo.
echo Will open default browser when the server is ready at http://localhost:8000 ...
start "OpenBrowserWhenReady" powershell -NoLogo -NoProfile -Command "while(-not (Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet)) { Start-Sleep -Milliseconds 300 }; Start-Process 'http://localhost:8000'"

echo.
echo Starting FastAPI server on http://127.0.0.1:8000 ...

REM Prefer uvicorn CLI (with auto-reload). Fallback to python main.py
where uvicorn >nul 2>&1
if %ERRORLEVEL%==0 (
  uvicorn main:app --host 127.0.0.1 --port 8000 --reload
) else (
  echo Uvicorn CLI not found. Falling back to: python main.py
  python "%SCRIPT_DIR%main.py"
)

echo.
echo Server has stopped (or crashed). Press any key to close this window.
pause >nul

popd
endlocal
