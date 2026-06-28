@echo off
setlocal

set "SAFY_HOME=%~dp0.."
for %%I in ("%SAFY_HOME%") do set "SAFY_HOME=%%~fI"

if not exist "%SAFY_HOME%\Apps\Api\safy_api\cli.py" (
  echo [SAFY LAUNCHER ERROR]
  echo SAFY_HOME resolved to:
  echo   %SAFY_HOME%
  echo But cli.py was not found:
  echo   %SAFY_HOME%\Apps\Api\safy_api\cli.py
  exit /b 1
)

if exist "C:\Program Files\Python312\python.exe" (
  set "SAFY_PYTHON=C:\Program Files\Python312\python.exe"
) else (
  set "SAFY_PYTHON=python"
)

set "PYTHONNOUSERSITE=1"
set "VIRTUAL_ENV="
set "PYTHONPATH=%SAFY_HOME%;%PYTHONPATH%"

cd /d "%SAFY_HOME%"

echo [SAFY] Project root: %SAFY_HOME%
echo [SAFY] Python: %SAFY_PYTHON%

"%SAFY_PYTHON%" -m Apps.Api.safy_api.cli %*

set "SAFY_EXIT=%ERRORLEVEL%"
endlocal & exit /b %SAFY_EXIT%