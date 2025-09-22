# Criação e Edição de Serviço Clínico

Este adendo documenta o fluxo de validação introduzido após a unificação de `Servico` e `ServicoClinico`.

## Resumo
Ao marcar a opção *"É um Serviço Clínico?"* no formulário de criação/edição:
- Um sub-form separado (`ServicoClinicoForm`, prefixo `clinico`) é renderizado.
- Todos os campos clínicos são validados **antes** de persistir o `Servico`.
- Em caso de erro no sub-form, o serviço **não é salvo** e o usuário recebe mensagem de erro.

## Motivação
Evitar estado inconsistente onde o serviço está marcado como clínico (`is_clinical=True`) mas não possui perfil associado (`perfil_clinico`).

## Implementação
Arquivo: `servicos/views.py`
- `BaseServicoCreateView.form_valid` valida sub-form e envolve criação em `transaction.atomic()`.
- `BaseServicoUpdateView.form_valid`:
  - Se `is_clinical=True` e sub-form válido: salva/atualiza perfil.
  - Se `is_clinical=False` e perfil existir: deleta perfil (desassociação limpa).

## Regras de Negócio Preservadas
Nenhuma regra do domínio clínico (`ServicoClinico`) foi alterada; apenas o mecanismo de persistência e validação transacional.

## Mensagens
- Erros no perfil: `messages.error(... 'Erros no perfil clínico.')`
- Sucesso criação/edição utiliza mensagens padrão de serviço já existentes.

## Testes Cobertos
Arquivo: `tests/servicos/test_servico_clinico_form.py`
- `test_criar_servico_clinico` – criação completa com perfil.
- `test_remover_perfil_clinico_na_edicao` – remoção limpa ao desmarcar.
- `test_validacao_duracao_invalida` – sub-form inválido impede persistência.

## Próximos Passos Sugeridos
- (Concluído) Exibir erros de campo específicos inline no template (agora renderizados em `partials/servico_form_tab_dados_principais.html`).
- Converter parsing JS de duração (client-side) em validação auxiliar opcional.
- Adicionar auditoria de criação/alteração do perfil clínico.
