@echo off
REM Execução rápida de testes: sem cobertura, pulando testes marcados como slow.
REM Uso:
REM   run_fast.bat                      -> roda suite inteira (sem slow, sem cobertura)
REM   run_fast.bat -k twofa             -> filtra por substring
REM   run_fast.bat tests/core/...::TestClass::test_method
REM Forçar incluir slow: set RUN_SLOW=1 antes de chamar ou passar --runslow manualmente.

set NO_COV=1
if not defined RUN_SLOW (
  set PYTEST_ARGS=%*
) else (
  set PYTEST_ARGS=--runslow %*
)

REM Garante que saída seja curta, mas preserva falhas
pytest %PYTEST_ARGS%

REM Limpa variáveis temporárias desta janela (opcional)
set NO_COV=
