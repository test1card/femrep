@echo off
REM ===========================================================================
REM  femrep installer for Ansys 2021 R1/R2 and 2022 R1 (legacy DPF v4.0)
REM
REM  Fully automatic. These Ansys versions need ansys-dpf-core 0.9 on Python
REM  3.10/3.11. This script gets a Python 3.11 JUST FOR femrep's environment
REM  (via uv — your system Python is not touched), pins the compatible DPF,
REM  installs femrep, and makes a desktop shortcut. No git, no command line.
REM ===========================================================================
setlocal
title femrep installer (Ansys 2021/2022R1)

echo.
echo  ============================================================
echo    femrep installer - Ansys 2021 R1/R2 and 2022 R1
echo    (DPF v4.0 / LegacyGrpc - Python 3.11 inside femrep only)
echo  ============================================================
echo.

set "FEMREP_HOME=%LOCALAPPDATA%\femrep"
set "VENV=%FEMREP_HOME%\venv"
set "UVDIR=%FEMREP_HOME%\uv"

REM --- 1. Get a Python 3.11/3.10 environment --------------------------------
echo  [1/4] Preparing a Python 3.11 environment for femrep...
if exist "%VENV%" rmdir /s /q "%VENV%"

REM 1a. Use an already-installed 3.11 or 3.10 via the py launcher, if present.
py -3.11 -m venv "%VENV%" >nul 2>&1 && goto have_venv
py -3.10 -m venv "%VENV%" >nul 2>&1 && goto have_venv

REM 1b. Otherwise fetch a standalone Python 3.11 with uv (no admin, isolated).
echo        No suitable Python found - downloading an isolated Python 3.11 (uv)...
if not exist "%UVDIR%\uv.exe" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:UV_INSTALL_DIR='%UVDIR%'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; irm https://astral.sh/uv/install.ps1 | iex"
)
if not exist "%UVDIR%\uv.exe" (
    echo  [X] Could not install uv. Check your internet connection, or install
    echo      Python 3.11 manually from the Microsoft Store and re-run this file.
    pause
    exit /b 1
)
"%UVDIR%\uv.exe" python install 3.11
"%UVDIR%\uv.exe" venv --seed --python 3.11 "%VENV%"
if not exist "%VENV%\Scripts\python.exe" (
    echo  [X] Could not create the Python 3.11 environment.
    pause
    exit /b 1
)

:have_venv
echo        Environment ready.
echo.

REM --- 2. Install femrep + the legacy-compatible DPF ------------------------
echo  [2/4] Installing femrep and ansys-dpf-core 0.9 (this may take minutes)...
set "WHEEL="
for %%f in ("%~dp0femrep-*.whl") do set "WHEEL=%%f"
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
REM setuptools provides pkg_resources, which ansys-dpf-core 0.9 imports but does
REM not declare; modern (uv / 3.12+) venvs do not include it by default.
if defined WHEEL (
    "%VENV%\Scripts\python.exe" -m pip install "%WHEEL%[gui]" "ansys-dpf-core==0.9.0" setuptools
) else (
    "%VENV%\Scripts\python.exe" -m pip install "femrep[gui]" "ansys-dpf-core==0.9.0" setuptools
)
if errorlevel 1 (
    echo.
    echo  [X] Installation failed - usually no internet connection.
    pause
    exit /b 1
)
echo.

REM --- 3. Desktop shortcut --------------------------------------------------
echo  [3/4] Creating a desktop shortcut...
set "TARGET=%VENV%\Scripts\femrep-gui.exe"
set "SHORTCUT=%USERPROFILE%\Desktop\femrep.lnk"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%SHORTCUT%'); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%USERPROFILE%'; $s.Description='femrep - FEM report generator'; $s.Save()"

echo.
echo  [4/4] Done.
echo  ============================================================
echo    femrep is installed for Ansys 2021/2022R1.
echo    Python 3.11 + ansys-dpf-core 0.9 live inside femrep only;
echo    your system Python and Ansys are untouched.
echo    Start it from the "femrep" icon on your Desktop.
echo  ============================================================
echo.
pause
endlocal
