@echo off
cd /d "%~dp0"
set "APP_PYTHON=python"
if exist "%~dp0.venv\Scripts\python.exe" set "APP_PYTHON=%~dp0.venv\Scripts\python.exe"
"%APP_PYTHON%" -c "import tkinterdnd2" >nul 2>&1
if errorlevel 1 (
    echo Surukle-birak destegi kuruluyor...
    "%APP_PYTHON%" -m pip install tkinterdnd2
    if errorlevel 1 (
        echo tkinterdnd2 kurulamadi. Surukle-birak kullanilamayacak.
        pause
    )
)
"%APP_PYTHON%" subtitle_translator_gui.py
if errorlevel 1 pause
