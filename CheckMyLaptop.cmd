@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 -m checkmylaptop %*
) else (
    python -m checkmylaptop %*
)
if errorlevel 1 pause
