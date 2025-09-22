@echo off
setlocal
rem Abre um cmd com PYTHONPATH apontando para este backend
set "PYTHONPATH=%~dp0"
set "DJANGO_SETTINGS_MODULE=pandora_erp.settings"

rem Prefira o Python do venv se existir, senão use o do PATH
set "PY=python"
if exist "%~dp0venv\Scripts\python.exe" set "PY=%~dp0venv\Scripts\python.exe"

echo PYTHONPATH=%PYTHONPATH%
echo DJANGO_SETTINGS_MODULE=%DJANGO_SETTINGS_MODULE%
"%PY%" -c "import sys; print('Python:', sys.executable); print('Version:', sys.version)"

cmd.exe
