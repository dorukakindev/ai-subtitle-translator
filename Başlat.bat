@echo off
cd /d "%~dp0"
python -c "import tkinterdnd2" >nul 2>&1
if errorlevel 1 (
    echo Surukle-birak destegi kuruluyor...
    python -m pip install tkinterdnd2
    if errorlevel 1 (
        echo tkinterdnd2 kurulamadi. Surukle-birak kullanilamayacak.
        pause
    )
)
python subtitle_translator_gui.py
