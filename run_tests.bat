@echo off
REM Script unificado para execução dos testes
SETLOCAL
CD /D %~dp0
IF NOT EXIST venv\Scripts\python.exe (
  echo Ambiente virtual nao encontrado em venv\Scripts\python.exe
  exit /b 1
)
venv\Scripts\python -m pytest %*
ENDLOCAL
