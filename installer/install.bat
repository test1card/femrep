@echo off
REM ===========================================================================
REM  femrep installer for Windows
REM  Double-click this file to install femrep and create a desktop shortcut.
REM  No git or command-line knowledge required.
REM ===========================================================================
setlocal enabledelayedexpansion
title femrep installer

echo.
echo  ============================================================
echo    femrep installer
echo    FEM report generator (Ansys / Nastran)
echo  ============================================================
echo.

REM --- Where femrep will live ------------------------------------------------
set "FEMREP_HOME=%LOCALAPPDATA%\femrep"
set "VENV=%FEMREP_HOME%\venv"

REM --- 1. Find a usable Python ------------------------------------------------
REM Prefer the "py" launcher, fall back to "python".
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)

if not defined PY (
    echo  [X] Python was not found on this machine.
    echo.
    echo      femrep needs Python 3.10 - 3.12 ^(3.12 recommended^).
    echo.
    echo      Please install it first, then run this installer again:
    echo        1. Open the Microsoft Store and install "Python 3.12"
    echo           - OR download from  https://www.python.org/downloads/
    echo        2. On the python.org installer, TICK the box
    echo           "Add python.exe to PATH" before clicking Install.
    echo.
    pause
    exit /b 1
)

echo  [1/4] Found Python:
%PY% --version
echo.

REM --- 2. Create an isolated environment -------------------------------------
echo  [2/4] Creating femrep environment in:
echo        %VENV%
if exist "%VENV%" (
    echo        ^(existing install found - it will be upgraded^)
) else (
    %PY% -m venv "%VENV%"
    if errorlevel 1 (
        echo  [X] Could not create the Python environment.
        echo      Make sure Python 3.10 - 3.12 is installed correctly.
        pause
        exit /b 1
    )
)
echo.

REM --- 3. Install femrep (with the desktop GUI) ------------------------------
echo  [3/4] Installing femrep and its dependencies...
echo        ^(this downloads packages and may take a few minutes^)
set "WHEEL="
for %%f in ("%~dp0femrep-*.whl") do set "WHEEL=%%f"

REM Old Ansys (2021 R1/R2, 2022 R1) ships DPF server v4.0, which only works with
REM ansys-dpf-core 0.3-0.9 over LegacyGrpc. Detect it and pin the compatible DPF.
set "DPF_PIN="
if defined AWP_ROOT212 set "DPF_PIN=ansys-dpf-core==0.9.0"
if defined AWP_ROOT211 set "DPF_PIN=ansys-dpf-core==0.9.0"
if defined AWP_ROOT221 set "DPF_PIN=ansys-dpf-core==0.9.0"
if defined DPF_PIN (
    echo        Detected Ansys 2021-2022R1 - pinning %DPF_PIN% for DPF v4.0 ^(LegacyGrpc^).
    echo        NOTE: this DPF needs Python 3.10 or 3.11 ^(not 3.12+^).
)

"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
REM setuptools provides pkg_resources, which some ansys-dpf-core versions import
REM but do not declare; modern venvs (Python 3.12+) omit it by default.
if defined WHEEL (
    "%VENV%\Scripts\python.exe" -m pip install "%WHEEL%[gui]" %DPF_PIN% setuptools
) else (
    echo        ^(no bundled wheel found - installing from PyPI^)
    "%VENV%\Scripts\python.exe" -m pip install "femrep[gui]" %DPF_PIN% setuptools
)
if errorlevel 1 (
    echo.
    echo  [X] Installation failed. Common causes: no internet connection, or a
    echo      Python version too new for your Ansys. For Ansys 2021/2022R1 use
    echo      Python 3.10 or 3.11; for newer Ansys, Python 3.10 - 3.12.
    pause
    exit /b 1
)
echo.

REM --- 4. Create a desktop shortcut to the GUI -------------------------------
echo  [4/4] Creating a desktop shortcut...
set "TARGET=%VENV%\Scripts\femrep-gui.exe"
set "SHORTCUT=%USERPROFILE%\Desktop\femrep.lnk"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$s = $ws.CreateShortcut('%SHORTCUT%');" ^
  "$s.TargetPath = '%TARGET%';" ^
  "$s.WorkingDirectory = '%USERPROFILE%';" ^
  "$s.Description = 'femrep - FEM report generator';" ^
  "$s.Save()"

echo.
echo  ============================================================
echo    Done!  femrep is installed.
echo.
echo    Start it from the "femrep" icon on your Desktop,
echo    or run "femrep-gui" from:
echo      %VENV%\Scripts\
echo  ============================================================
echo.
pause
endlocal
