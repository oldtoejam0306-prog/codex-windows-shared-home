@echo off
setlocal
set "CSH_PWSH=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe"
if not exist "%CSH_PWSH%" (
  echo Bundled PowerShell 7 unavailable. Use an installed PowerShell 7 to run Launch-Shared.ps1.
  pause
  exit /b 2
)
"%CSH_PWSH%" -NoLogo -NoProfile -File "%~dp0Launch-Shared.ps1" -Settings "%~dp0..\local.settings.json"
if errorlevel 1 pause
endlocal
