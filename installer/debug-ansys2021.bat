@echo off
REM ===========================================================================
REM  femrep — Ansys 2021/2022R1 diagnostics
REM  Run this if reading an Ansys .rst/.rth fails. It reports the Python and DPF
REM  versions, the installed Ansys, and whether a DPF server actually starts —
REM  with the real error if it does not. Saves everything to a log you can send.
REM
REM  Optional: drag a .rst/.rth file onto this .bat to also test reading it.
REM ===========================================================================
title femrep - Ansys 2021 diagnostics
set "VENV=%LOCALAPPDATA%\femrep\venv"
set "LOG=%LOCALAPPDATA%\femrep\femrep-ansys2021.log"

if not exist "%VENV%\Scripts\python.exe" (
    echo femrep is not installed in %VENV%
    echo Run install-ansys2021.bat first.
    pause
    exit /b 1
)

echo Installed Ansys versions (AWP_ROOT*):
set AWP_ROOT
echo.
echo Running DPF diagnostics (this can take up to a minute)...
echo Saving to: %LOG%
echo.

"%VENV%\Scripts\python.exe" -m femrep.diagnose %1 > "%LOG%" 2>&1

echo =====================================================================
type "%LOG%"
echo =====================================================================
echo.
echo Saved to %LOG% — send this file (or the text above) for support.
pause
