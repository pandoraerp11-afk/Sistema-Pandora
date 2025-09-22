# Módulo Prontuários

## Objetivo
Gerenciar ciclo clínico/estético: catálogo de serviços clínicos, registro de atendimentos, evolução fotográfica, anamnese e perfil clínico.

## Entidades

| Entidade | Papel | Observações |
|--------|-----------|-------|
| `Servico`/`ServicoClinico` (app `servicos`) | Catálogo unificado de serviços clínicos | Configurações: requer anamnese, termo, intervalo mínimo, duração estimada, etc. |
| `Atendimento` | Execução de serviço clínico | Vínculo opcional a slot/agendamento |
| `Anamnese` | Questionário clínico | Profissional responsável obrigatório |
| `PerfilClinico` | Dados de saúde agregados ao Cliente | One-to-one com Cliente |
| `AtendimentoDisponibilidade` / `AtendimentoSlot` | Disponibilidades clínicas legacy | Fase de transição da agenda (substituídos por `agendamentos`) |

- Select2/AJAX: endpoints `/prontuarios/api/search/clientes/` e `/prontuarios/api/search/profissionais/` (padrão `staff_only=1`). A busca de serviços ocorre no módulo `servicos`.
- Quick-create de Procedimento REMOVIDO: crie serviços em `/servicos/`.
- `Atendimento.agendamento` conecta atendimento a agendamento para sincronizar duração e status.
- Tasks de mídia: geração de `imagem_thumbnail`, `imagem_webp`, `video_poster`.

## Tenant Handling
- Introduzido `TenantSafeMixin` prevenindo erros quando tenant não selecionado.
- Views anteriores que usavam `self.request.user.tenant` diretamente foram adaptadas.

## Formulários

- `Servico/ServicoClinico` (app `servicos`): catálogo de serviços clínicos (nome, duração estimada, preço, categoria, requisitos). Criação/edição ocorre no módulo `servicos`.
- Atendimento: campos Cliente/Serviço/Profissional usam Select2 com busca AJAX; sem quick-create inline para serviço.
- Atendimento: mensagens de sucesso após salvar exibidas como toast; ao selecionar um slot, o campo data/hora é preenchido e bloqueado até limpar o slot.
- `servicos/`: CRUD de serviços clínicos.

## Fluxo de Criação de Serviço Clínico
1. Usuário seleciona tenant (session `tenant_id`).
2. Acessa `/servicos/servicos/novo/` (ou rota equivalente no módulo `servicos`).
3. View valida presença do tenant; sem tenant => redireciona.
4. Salva registro e redireciona para lista de serviços.

## Erros Corrigidos
| Tipo | Erro | Correção |
|------|------|----------|
| Template | Tag include com sintaxe incorreta / argumentos extras | Sintaxe `with ...` corrigida |
| Template | Campo inexistente `cuidados_posteriores` | Substituído por `cuidados_pos_procedimento` |
| View | AttributeError em `user.tenant` sem seleção | `TenantSafeMixin` e fallback `get_current_tenant` |

## Próximos Passos Possíveis
- Unificar agenda clínica com novo módulo `agendamentos` (substituir disponibilidade legacy).
- Cache leve de contagem de fotos por atendimento.
- Versões de anamnese versionadas (histórico).
 - Teste cobrindo transição de status para CANCELADO liberando slot automaticamente.

## Slots e Cancelamento

- Ao criar um Atendimento com `slot`, a data do atendimento é forçada para `slot.horario`.
- Na atualização (Update):
	- Se trocar de slot, o slot antigo é liberado (capacidade_utilizada - 1) e o novo é reservado, tudo em transação.
	- Se mudar o `status` para `CANCELADO`, o slot é liberado automaticamente.
	- A liberação ocorre por múltiplas camadas para robustez e idempotência:
		1) Na própria UpdateView (form_valid) com lock/select_for_update.
		2) No `Atendimento.save()` ao detectar transição para CANCELADO.
		3) Em um fallback da `post()` da UpdateView, que libera mesmo se o form for inválido.

### Multi-tenant (cookie compat)

- `core.utils.get_current_tenant()` agora também aceita o cookie `current_tenant_id` e o propaga para `request.session['tenant_id']`. Isso garante que testes ou integrações que só configuram o cookie atinjam o tenant correto.
