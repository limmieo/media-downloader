@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"

echo ===========================================
echo   Media Downloader - Electron Launcher
echo ===========================================
echo Working directory: %CD%
echo.

where node >nul 2>&1
if errorlevel 1 (
  echo [Error] Node.js is not available in PATH.
  echo Please install Node.js 20 or later and try again.
  goto :END
)

if not exist node_modules (
  echo npm dependencies not detected. Installing with npm install ...
  call npm install
  if errorlevel 1 (
    echo.
    echo [Error] Failed to install npm dependencies.
    goto :END
  )
)

echo Starting Electron app...
echo (close the Electron window to return here)
echo.
call npm run dev

if errorlevel 1 (
  echo.
  echo [Error] Electron app exited with code %ERRORLEVEL%.
) else (
  echo.
  echo Electron app closed normally.
)

:END
echo.
echo Press any key to close this window.
pause >nul

popd
endlocal
