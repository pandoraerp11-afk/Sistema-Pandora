@echo off
echo ========================================
echo    PANDORA ERP - SCRIPT DE DEPLOY
echo ========================================
echo.

echo [1/6] Verificando status do Git...
git status --porcelain
if %ERRORLEVEL% neq 0 (
    echo Erro: Problemas no repositorio Git
    pause
    exit /b 1
)

echo.
echo [2/6] Adicionando arquivos modificados...
git add -A

echo.
echo [3/6] Verificando se ha mudancas para commit...
git diff --cached --quiet
if %ERRORLEVEL% equ 0 (
    echo Nenhuma mudanca para fazer commit.
) else (
    set /p commit_msg="Digite a mensagem do commit: "
    git commit -m "%commit_msg%"
)

echo.
echo [4/6] Verificando se existe repositorio remoto...
git remote -v | find "origin" >nul
if %ERRORLEVEL% neq 0 (
    echo.
    echo ATENCAO: Nenhum repositorio remoto configurado!
    echo.
    echo Para configurar, execute:
    echo git remote add origin https://github.com/SEU_USUARIO/Pandora-ERP.git
    echo.
    pause
    exit /b 1
)

echo.
echo [5/6] Enviando mudancas para o repositorio remoto...
git push origin master
if %ERRORLEVEL% neq 0 (
    echo.
    echo Erro ao fazer push. Verifique:
    echo - Se voce tem permissao no repositorio
    echo - Se sua autenticacao esta correta
    echo - Se o repositorio remoto existe
    echo.
    pause
    exit /b 1
)

echo.
echo [6/6] Deploy concluido com sucesso! ✅
echo.
echo O codigo foi atualizado no repositorio remoto.
echo Agora voce pode acessar de qualquer computador com:
echo git clone https://github.com/SEU_USUARIO/Pandora-ERP.git
echo.
pause
