param(
    [switch]$Fix = $false,
    [switch]$Unsafe = $false,
    [switch]$GitCommit = $false,
    [string]$Path = '.'
)

# Script de automação de lint seguro (não altera regras de negócio)
# - Gera relatórios do Ruff (sumário e completo)
# - Opcionalmente aplica apenas correções consideradas seguras e semânticamente neutras
# - (formatação, simplificações triviais e chain de exceptions)
# - Não tenta mover imports, alterar estrutura de funções, ou mexer em validações

$ErrorActionPreference = 'Stop'

# Ir para raiz do projeto
Set-Location (Join-Path $PSScriptRoot '..')

# Normalizar path alvo e sufixo dos relatórios
$TargetPath = (Resolve-Path -LiteralPath $Path).Path
$Suffix = (Split-Path -Leaf $TargetPath)
if ($Suffix -eq '' -or $null -eq $Suffix) { $Suffix = 'root' }

# 1) Sumário estatístico
Write-Host "Gerando sumário do Ruff em erro_$Suffix.txt..."
ruff check $TargetPath --statistics --exit-zero | Out-File -Encoding utf8 "erro_$Suffix.txt"

# 2) Relatório completo
Write-Host "Gerando relatório completo do Ruff em ruff_full_$Suffix.txt..."
ruff check $TargetPath --exit-zero | Out-File -Encoding utf8 "ruff_full_$Suffix.txt"

# 3) Correções seguras (opcional)
if ($Fix) {
    Write-Host 'Aplicando correções seguras...'
    # Formatação (linhas longas, espaços etc.)
    ruff format $TargetPath

    # Seleção conservadora de regras com auto-fix seguro
    # - SIM102: if colapsável
    # - SIM108: if-else -> expressão condicional simples
    # - B904: adicionar exception chaining (raise ... from e)
    # - B007: variáveis de controle de loop não usadas -> _
    ruff check $TargetPath --select SIM102, SIM108, B904, B007 --fix

    # Salvar diff, se git estiver disponível
    if (Get-Command git -ErrorAction SilentlyContinue) {
        Write-Host "Salvando diff das alterações em scripts/lint_fix_$Suffix.diff..."
        git diff > "scripts/lint_fix_$Suffix.diff"
        if ($GitCommit) {
            $branch = 'chore/lint-auto-fix-' + (Get-Date -Format 'yyyyMMddHHmmss')
            Write-Host "Criando branch $branch e commitando..."
            git checkout -b $branch 2>$null
            git add -A
            git commit -m 'chore(lint): safe auto-fixes (format, SIM102/SIM108/SIM115, B904, UP038)'
        }
    }
}

# 4) Itens para revisão manual (opcional, sem fix automatizado)
if ($Unsafe) {
    Write-Host 'Coletando itens que exigem revisão manual em scripts/lint_manual_review.txt...'
    # Import no nível errado, star-imports, magic values e complexidade
    ruff check $TargetPath --select E402, PLC0415, F405, PLR2004, PLR0912, PLR0915, PLR0913, PLR0911, SIM105, F821, F811, F401 --exit-zero |
    Out-File -Encoding utf8 "scripts/lint_manual_review_$Suffix.txt"
}

Write-Host "Concluído. Veja erro_$Suffix.txt, ruff_full_$Suffix.txt e (se selecionado) scripts/lint_fix_$Suffix.diff / scripts/lint_manual_review_$Suffix.txt."

# 5) Relatório de usos genéricos de # noqa (PGH004) para ajuste fino
Write-Host "Coletando usos genéricos de # noqa em scripts/noqa_generic_$Suffix.txt..."
Get-ChildItem -Recurse -Path $TargetPath -Include *.py -File | ForEach-Object {
    $foundMatches = Select-String -Path $_.FullName -Pattern "# noqa(?!:)" -SimpleMatch
    if ($foundMatches) { $foundMatches | ForEach-Object { $_.FileName + ':' + $_.LineNumber + '  ' + $_.Line } }
} | Out-File -Encoding utf8 "scripts/noqa_generic_$Suffix.txt"
