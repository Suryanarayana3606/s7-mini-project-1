@echo off
setlocal
cd /d "%~dp0"

echo Starting backend and frontend...
start "Backend" cmd /k call "%~dp0start_backend.bat"
start "Frontend" cmd /k call "%~dp0start_frontend.bat"

endlocal
