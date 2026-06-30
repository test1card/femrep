@echo off
REM ===========================================================================
REM  femrep debug launcher — run this if the desktop icon does nothing / closes.
REM  It launches femrep in a console so the error is visible, and saves it to a
REM  log file you can send for support.
REM ===========================================================================
title femrep debug
set "VENV=%LOCALAPPDATA%\femrep\venv"
set "LOG=%LOCALAPPDATA%\femrep\femrep-debug.log"

if not exist "%VENV%\Scripts\python.exe" (
    echo femrep is not installed in %VENV%
    echo Run install.bat / install-ansys2021.bat first.
    pause
    exit /b 1
)

echo Launching femrep with console output...
echo Any error appears below and is saved to:
echo   %LOG%
echo (close the femrep window to return here)
echo.

"%VENV%\Scripts\python.exe" -m femrep.gui > "%LOG%" 2>&1

echo.
echo =============== femrep output (also saved to the log) ===============
type "%LOG%"
echo =====================================================================
echo.
echo Send the text above (or the file %LOG%) for support.
pause
