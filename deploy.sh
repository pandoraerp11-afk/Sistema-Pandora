#!/bin/bash

echo "========================================"
echo "    PANDORA ERP - SCRIPT DE DEPLOY"
echo "========================================"
echo

echo "[1/6] Verificando status do Git..."
if ! git status --porcelain &>/dev/null; then
    echo "❌ Erro: Problemas no repositorio Git"
    exit 1
fi

echo
echo "[2/6] Adicionando arquivos modificados..."
git add -A

echo
echo "[3/6] Verificando se ha mudancas para commit..."
if git diff --cached --quiet; then
    echo "ℹ️  Nenhuma mudanca para fazer commit."
else
    read -p "💬 Digite a mensagem do commit: " commit_msg
    git commit -m "$commit_msg"
fi

echo
echo "[4/6] Verificando se existe repositorio remoto..."
if ! git remote -v | grep -q "origin"; then
    echo
    echo "⚠️  ATENCAO: Nenhum repositorio remoto configurado!"
    echo
    echo "Para configurar, execute:"
    echo "git remote add origin https://github.com/SEU_USUARIO/Pandora-ERP.git"
    echo
    exit 1
fi

echo
echo "[5/6] Enviando mudancas para o repositorio remoto..."
if ! git push origin master; then
    echo
    echo "❌ Erro ao fazer push. Verifique:"
    echo "- Se voce tem permissao no repositorio"
    echo "- Se sua autenticacao esta correta"
    echo "- Se o repositorio remoto existe"
    echo
    exit 1
fi

echo
echo "[6/6] Deploy concluido com sucesso! ✅"
echo
echo "🎉 O codigo foi atualizado no repositorio remoto."
echo "Agora voce pode acessar de qualquer computador com:"
echo "git clone https://github.com/SEU_USUARIO/Pandora-ERP.git"
echo
