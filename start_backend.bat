@echo off
setlocal
cd /d "%~dp0backend_updated"

if not exist ".venv\Scripts\python.exe" (
    echo Creating backend virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create the backend virtual environment.
        exit /b 1
    )
)

if not exist ".venv\Scripts\uvicorn.exe" (
    echo Installing backend dependencies...
    call .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install backend dependencies.
        exit /b 1
    )
)

call .venv\Scripts\python.exe -c "import en_core_web_sm" >nul 2>&1
if errorlevel 1 (
    echo Downloading spaCy English model...
    call .venv\Scripts\python.exe -m spacy download en_core_web_sm
    if errorlevel 1 (
        echo Failed to download the spaCy English model.
        exit /b 1
    )
)

call .venv\Scripts\python.exe -m uvicorn app.main:app --reload
endlocal
