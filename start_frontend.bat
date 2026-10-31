@echo off
setlocal
cd /d "%~dp0frontend_updated"

if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install
    if errorlevel 1 (
        echo Failed to install frontend dependencies.
        exit /b 1
    )
)

call npm run dev
endlocal
