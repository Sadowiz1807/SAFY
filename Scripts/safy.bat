@echo off
setlocal

set "SAFY_HOME=%~dp0.."
for %%I in ("%SAFY_HOME%") do set "SAFY_HOME=%%~fI"

if exist "C:\Program Files\Python312\python.exe" (
  set "SAFY_PYTHON=C:\Program Files\Python312\python.exe"
) else (
  set "SAFY_PYTHON=python"
)

set "PYTHONNOUSERSITE=1"
set "VIRTUAL_ENV="
set "PYTHONPATH=%SAFY_HOME%"

cd /d "%SAFY_HOME%"
"%SAFY_PYTHON%" -m Apps.Api.safy_api.cli %*
set "SAFY_EXIT=%ERRORLEVEL%"
endlocal & exit /b %SAFY_EXIT%
