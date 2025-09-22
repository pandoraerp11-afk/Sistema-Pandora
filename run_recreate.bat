@echo off
REM =============================================================
REM  PANDORA ERP - SCRIPT AUTOMATICO DE PREPARACAO DO AMBIENTE
REM  Uso: run_recreate.bat [opcoes]
REM -------------------------------------------------------------
REM  Opcoes:
REM    --skip-tests        Pula execucao de testes rapidos
REM    --skip-static       Nao roda collectstatic
REM    --no-upgrade        Nao atualiza pip/setuptools/wheel
REM    --recreate-venv     Apaga e recria o venv
REM    --docker            (Re)constroi e sobe os containers docker compose
REM    --docker-only       Apenas docker (nao mexe em venv local)
REM    --tests-full        Roda pytest completo em vez de smoke
REM    --no-migrate        Nao roda migrate
REM    --superuser         Cria superusuario interativo apos migracoes
REM =============================================================

setlocal ENABLEDELAYEDEXPANSION

pushd %~dp0
echo [INIT] Diretorio do script: %CD%

REM ------------------ PARSE ARGUMENTOS -------------------------
set SKIP_TESTS=0
set SKIP_STATIC=0
set NO_UPGRADE=0
set RECREATE_VENV=0
set DOCKER=0
set DOCKER_ONLY=0
set TESTS_FULL=0
set NO_MIGRATE=0
set CREATE_SUPERUSER=0

:parse_args
if "%~1"=="" goto end_parse
if /I "%~1"=="--skip-tests" set SKIP_TESTS=1& shift & goto parse_args
if /I "%~1"=="--skip-static" set SKIP_STATIC=1& shift & goto parse_args
if /I "%~1"=="--no-upgrade" set NO_UPGRADE=1& shift & goto parse_args
if /I "%~1"=="--recreate-venv" set RECREATE_VENV=1& shift & goto parse_args
if /I "%~1"=="--docker" set DOCKER=1& shift & goto parse_args
if /I "%~1"=="--docker-only" set DOCKER_ONLY=1& set DOCKER=1& shift & goto parse_args
if /I "%~1"=="--tests-full" set TESTS_FULL=1& shift & goto parse_args
if /I "%~1"=="--no-migrate" set NO_MIGRATE=1& shift & goto parse_args
if /I "%~1"=="--superuser" set CREATE_SUPERUSER=1& shift & goto parse_args
echo [WARN] Argumento desconhecido: %~1
shift
goto parse_args
:end_parse

REM ------------------ DOCKER APENAS ----------------------------
if %DOCKER_ONLY%==1 goto docker_section

REM ------------------ VENV -------------------------------------
REM Usar apenas 'venv' como ambiente oficial
set VENV_DIR=venv
set PYTHON_EXE=
for /f "delims=" %%i in ('where python.exe 2^>nul') do if not defined PYTHON_EXE set PYTHON_EXE=%%i
if not defined PYTHON_EXE (
	echo [ERRO] python.exe nao encontrado no PATH.
	goto end_fail
)
echo [PYTHON] Usando: %PYTHON_EXE%
if %RECREATE_VENV%==1 if exist %VENV_DIR% (
	echo [VENV] Removendo venv existente...
	rmdir /S /Q %VENV_DIR%
)

if not exist %VENV_DIR% (
	echo [VENV] Criando ambiente virtual 'venv'...
	"%PYTHON_EXE%" -m venv %VENV_DIR%
	if %ERRORLEVEL% neq 0 (
		echo [ERRO] Falha ao criar venv.
		goto end_fail
	)
)

call %VENV_DIR%\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
	echo [ERRO] Nao foi possivel ativar o venv.
	exit /b 1
)
echo [VENV] Ativado: %VENV_DIR%

REM Verificar se python interno do venv funciona
set PYTHON_VENV=%VENV_DIR%\Scripts\python.exe
"%PYTHON_VENV%" -c "import sys" 1>nul 2>nul
if %ERRORLEVEL% neq 0 (
	if %RECREATE_VENV%==0 (
		echo [VENV] Ambiente 'venv' parece corrompido. Recriando automaticamente...
		rmdir /S /Q %VENV_DIR%
		"%PYTHON_EXE%" -m venv %VENV_DIR%
		if %ERRORLEVEL% neq 0 (
			echo [ERRO] Falha ao recriar venv.
			goto end_fail
		)
		call %VENV_DIR%\Scripts\activate.bat
		set PYTHON_VENV=%VENV_DIR%\Scripts\python.exe
	)
)
"%PYTHON_VENV%" -V
if %ERRORLEVEL% neq 0 (
	echo [ERRO] Python do venv continua inacessivel.
	goto end_fail
)

REM ------------------ UPGRADE PIP ------------------------------
if %NO_UPGRADE%==0 (
	echo [PIP] Atualizando pip / setuptools / wheel...
	"%PYTHON_VENV%" -m pip install --upgrade pip setuptools wheel >nul
	if %ERRORLEVEL% neq 0 echo [WARN] Nao foi possivel atualizar pip.
)

REM ------------------ INSTALAR DEPENDENCIAS --------------------
echo [REQ] Instalando dependencias do requirements.txt (isto pode demorar)...
"%PYTHON_VENV%" -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
	echo [ERRO] Falha ao instalar dependencias.
	goto end_fail
)

REM ------------------ MIGRACOES --------------------------------
if %NO_MIGRATE%==0 (
	echo [DB] Aplicando migracoes...
		"%PYTHON_VENV%" manage.py migrate
	if %ERRORLEVEL% neq 0 (
		echo [ERRO] Migracoes falharam.
		goto end_fail
	)
) else (
	echo [DB] Migracoes puladas (--no-migrate)
)

REM ------------------ COLETAR ESTATICOS ------------------------
if %SKIP_STATIC%==0 (
	if exist pandora_erp\settings.py (
		echo [STATIC] Coletando arquivos estaticos...
	"%PYTHON_VENV%" manage.py collectstatic --noinput >nul
		if %ERRORLEVEL% neq 0 echo [WARN] Falha em collectstatic (prosseguindo).
	)
) else (
	echo [STATIC] collectstatic pulado (--skip-static)
)

REM ------------------ SUPERUSER --------------------------------
if %CREATE_SUPERUSER%==1 (
	echo [ADMIN] Criar superusuario...
		"%PYTHON_VENV%" manage.py createsuperuser
)

REM ------------------ TESTES -----------------------------------
if %SKIP_TESTS%==0 (
	echo [TEST] Executando testes (%TESTS_FULL%==1 -> full)...
	if %TESTS_FULL%==1 (
	"%PYTHON_VENV%" -m pytest -q
	) else (
	"%PYTHON_VENV%" -m pytest -k test_urls -q
	)
	if %ERRORLEVEL% neq 0 echo [WARN] Alguns testes falharam.
) else (
	echo [TEST] Testes pulados (--skip-tests)
)

REM ------------------ DOCKER (Opcional) ------------------------
if %DOCKER%==1 goto docker_section
goto end_ok

:docker_section
echo [DOCKER] Preparando ambiente Docker Compose...
where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
	echo [ERRO] Docker nao encontrado no PATH.
	if %DOCKER_ONLY%==1 goto end_fail else goto end_ok
)
echo [DOCKER] Subindo servicos (build + up -d)...
docker compose up -d --build
if %ERRORLEVEL% neq 0 (
	echo [ERRO] Falha no docker compose.
	if %DOCKER_ONLY%==1 goto end_fail
)

echo [DOCKER] Logs iniciais (10s)...
docker compose logs --since 10s

if %DOCKER_ONLY%==1 goto end_ok
goto end_ok

:end_ok
echo.
echo =============================================================
echo  ✅ Ambiente pronto.
echo  Opcoes usadas: DOCKER=%DOCKER% TESTS_FULL=%TESTS_FULL% SKIP_TESTS=%SKIP_TESTS%
echo  Para iniciar servidor local:
echo      venv\Scripts\activate && python manage.py runserver
echo  Para subir docker:
echo      docker compose up -d
echo =============================================================
popd
exit /b 0

:end_fail
echo.
echo =============================================================
echo  ❌ Erros ocorreram durante o setup.
echo  Reveja as mensagens acima.
echo =============================================================
popd
exit /b 1

