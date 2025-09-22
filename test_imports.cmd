@echo off
setlocal
set "PYTHONPATH=%~dp0"
set "DJANGO_SETTINGS_MODULE=pandora_erp.settings"

set "PY=python"
if exist "%~dp0venv\Scripts\python.exe" set "PY=%~dp0venv\Scripts\python.exe"

"%PY%" -c "import sys, importlib, os; print('Python:', sys.executable); print('Version:', sys.version); print('PYTHONPATH:', os.environ.get('PYTHONPATH')); import django; django.setup(); importlib.import_module('core'); importlib.import_module('core.wizard_views'); print('OK imports')"

if errorlevel 1 (
  echo FALHOU
  exit /b 1
) else (
  echo SUCESSO
)
