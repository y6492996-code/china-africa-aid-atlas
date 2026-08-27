@echo off
title China-Africa Aid Database
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-background.ps1"
echo.
if errorlevel 1 (
  echo The website could not start. Press any key to close this window.
  pause >nul
) else (
  echo You may close this window. The website will continue running in the background.
  timeout /t 4 /nobreak >nul
)
