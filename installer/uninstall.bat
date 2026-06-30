@echo off
REM ===========================================================================
REM  femrep uninstaller for Windows
REM  Removes the femrep environment and the desktop shortcut.
REM  Does NOT remove Python or Ansys.
REM ===========================================================================
setlocal
title femrep uninstaller

set "FEMREP_HOME=%LOCALAPPDATA%\femrep"
set "SHORTCUT=%USERPROFILE%\Desktop\femrep.lnk"

echo.
echo  This will remove femrep from:
echo    %FEMREP_HOME%
echo  and delete the Desktop shortcut.
echo.
echo  Your Python and Ansys installations are NOT affected.
echo.
choice /c YN /m "Remove femrep now"
if errorlevel 2 goto :cancel

if exist "%SHORTCUT%" del /q "%SHORTCUT%"
if exist "%FEMREP_HOME%" rmdir /s /q "%FEMREP_HOME%"

echo.
echo  femrep has been removed.
echo.
pause
exit /b 0

:cancel
echo.
echo  Cancelled. Nothing was changed.
echo.
pause
exit /b 0
