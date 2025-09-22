# Auditoria de Código – Wizard (core/wizard_views.py) e Admin (admin/views.py)

Data: 2025-08-10
Responsável: GitHub Copilot

Resumo executivo
- Objetivo: identificar duplicações, imports redundantes, inconsistências, riscos e oportunidades de melhoria.
- Escopo auditado: core/wizard_views.py e admin/views.py (com nota sobre arquivo duplicado "wizard_views copy 2.py").
- Resultado: lista de problemas priorizados e plano de ação rápido com correções sugeridas.

1) Problemas críticos e bugs potenciais
- Inconsistência do regex de subdomínio (frontend vs backend)
  - Backend (wizard_views.validate_wizard_data_integrity): `^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])?$` desautoriza subdomínio de 1 caractere.
  - Frontend (JS em step_configuration.html): `^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$` permite 1 caractere.
  - Risco: UX aceita, backend rejeita. Ação: unificar regra. Sugestão: permitir 1-63 caracteres com `{0,61}` no backend (ou alinhar para exigir >=2).

- Campo de usuário em Admin: values_list incorreto
  - admin/views.py (admin_home): `tenant_users.values_list('usuario', flat=True)` — provável campo correto é `user` em `TenantUser`.
  - Risco: queryset vazio ou exceção. Ação: trocar para `values_list('user', flat=True)`.

- Uso inconsistente do User model
  - Topo do arquivo: `User = get_user_model()`; em get_recent_activities(): `from django.contrib.auth.models import User` (override).
  - Risco: referências ao modelo errado em projetos com user customizado. Ação: padronizar uso de `get_user_model()` e remover import interno.

- Possível namespace/rota inconsistente
  - success_url/urls: há referências mistas: `administration:alerts_page`, `admin:configurations-page`. Verificar namespace real no urls.py para evitar NoReverseMatch.

- Arquivo duplicado: core/wizard_views copy 2.py
  - Risco: manutenção confusa e import acidental por engano. Ação: remover arquivo duplicado ou renomear para rascunho fora do pacote.

2) Duplicações e imports redundantes
- core/wizard_views.py (top-level vs dentro de função `process_admin_data`)
  - Duplicados internos: `default_token_generator`, `urlsafe_base64_encode`, `force_bytes`, `send_mail`, `IntegrityError`, `ValidationError`, `secrets`, `string` são importados novamente dentro da função.
  - Ação: optar por (a) manter apenas no topo e remover imports internos OU (b) remover do topo e manter locais (melhor encapsular dependências do bloco de e-mail). Recomendo (a) para consistência e performance.

- core/wizard_views.py (imports não usados ou raramente usados)
  - Prováveis não usados no módulo (fora de `process_admin_data`): `send_mail`, `default_token_generator`, `urlsafe_base64_encode`, `force_bytes`, `IntegrityError`, `ValidationError`, `secrets`, `string`, `reverse` (somente `reverse_lazy` é usado), `ModuleConfigurationForm` (nunca usado), `HttpResponse` só como hint (ok), `ContentFile` (usado), `default_storage` (usado), etc.
  - Ação: rodar ruff (lint+format) e remover os realmente não usados. Se mantiver imports locais em `process_admin_data`, remova do topo para evitar redundância.

- admin/views.py
  - Imports internos e duplicados:
    - Reimporta `Tenant` e `PerfilUsuarioEstendido` dentro de funções já tendo referências importadas no topo.
    - Reimporta `User` (modelo padrão) dentro de método, conflitando com `get_user_model`.
    - `from django.db import models` aparenta não utilizado.
  - Ação: consolidar imports no topo e remover internos; padronizar `User = get_user_model()`.

3) Código morto/obsoleto e organização
- core/wizard_views.py
  - `_apply_pj_pf_data_before_save` marcado como “OBSOLETO” e vazio. Ação: remover para reduzir ruído.
  - `ModuleConfigurationForm` em try/except não é utilizado. Ação: remover bloco try inteiro.
  - Comentários “VERSÃO INDEPENDENTE/ULTRA MODERNO” são úteis, mas há repetições de contexto; considerar resumir.

- admin/views.py
  - Muitas seções “simuladas” com dados fictícios (ok se intencional). Ação: isolar em helpers (ex.: services/dummy_data.py) ou marcar com TODO claro para evitar confusão em produção.

4) Repetição/DRY e coesão
- core/wizard_views.py
  - Tratamento de arquivos temporários (save/remove/collect) está bom, porém repetição de logs/estruturas nos steps. Ação: extrair utilitários (ex.: utils/wizard_files.py) se aumentar.
  - `process_admin_data` concentra várias responsabilidades (criar role, criar usuário, associar, enviar e-mail). Ação: extrair envio de e-mail para helper e reduzir imports locais.

- admin/views.py
  - Padrão de filtros/paginação recorre em várias views. Ação: criar BaseListView com mixins (FilterMixin/PaginationMixin) para reduzir repetição.

5) Validação, segurança e UX
- Upload de documentos (step 4)
  - Falta validação de tipo/tamanho dos arquivos (há validação para logo no form de config, mas não para docs do step 4).
  - Ação: validar extensão e content_type; impor limite configurável; logar e recusar tipos proibidos.

- Mensagens e i18n
  - Mensagens de erro/sucesso em português sem gettext em vários pontos do wizard. Ação: aplicar `gettext_lazy`/`gettext` para internacionalização.

- Logging de dados sensíveis
  - Wizard loga `wizard_data` e diversos campos; cuidado com PII. Ação: reduzir logs ou mascarar campos sensíveis (CPF/CNPJ/e-mail).

6) Consistência e manutenção futura
- Session handling
  - Correto uso de `session.modified = True` e limpeza de temporários. Ação: bom.

- Nomes e padrões
  - `enabled_modules` tratado como lista; garantir que ModelField seja JSONField/ArrayField compatível. Ação: ok, apenas confirmar.

- Tipagem e hints
  - Boas anotações de tipo em vários métodos. Ação: manter e ampliar onde possível.

7) Plano de ação sugerido (quick wins)
- Semana 0 (higienização em lote, sem mudar lógica):
  1. Remover arquivo `core/wizard_views copy 2.py` (ou mover para docs/rascunhos).
  2. Unificar regex de subdomínio no backend para casar com frontend (ou vice-versa).
   3. Rodar ruff (faz lint e formatação) e remover imports não usados nos dois arquivos.
  4. Padronizar `User = get_user_model()` em todo admin/views.py; remover import interno de `User`.
  5. Corrigir `tenant_users.values_list('usuario', flat=True)` -> `values_list('user', flat=True)`.
  6. Validar e uniformizar namespaces de URLs usados em success_url/reverse.

- Semana 1 (refino):
  7. Extrair envio de e-mail de `process_admin_data` para helper (ex.: core/emails.py) e consolidar imports no topo.
  8. Adicionar validação de upload (tipo/tamanho) para documentos do step 4.
  9. Remover `_apply_pj_pf_data_before_save` e `ModuleConfigurationForm` morto.
  10. Internacionalizar mensagens do wizard (gettext).

- Semana 2 (organização avançada):
  11. Criar mixins utilitários para filtros/paginação no admin.
  12. Consolidar dados simulados em camada "services" para fácil substituição por dados reais.

8) Lista detalhada de ocorrências
- core/wizard_views.py
  - Duplicidade de imports: default_token_generator, urlsafe_base64_encode, force_bytes, send_mail, IntegrityError, ValidationError, secrets, string (no topo e dentro de `process_admin_data`).
  - Imports provavelmente não usados: reverse, ModuleConfigurationForm (inteiro try/except), possivelmente send_mail e correlatos se mantidos apenas locais.
  - Função obsoleta: `_apply_pj_pf_data_before_save` (conteúdo vazio).
  - Regex subdomínio divergente do frontend.

- admin/views.py
  - Reimport de modelos e usuários dentro de funções; padronizar topo.
  - Campo incorreto `usuario` no values_list.
  - Import desnecessário: `from django.db import models` (não utilizado).
  - Conflito de User (get_user_model vs User padrão) em `get_recent_activities`.
  - Possível NoReverseMatch por namespaces divergentes (verificar urls.py do módulo).

9) Ferramentas recomendadas
- Linters e formatadores: ruff (substitui flake8/isort/black).
- Verificação de segurança: bandit (para uploads e uso de secrets).
- Testes rápidos: adicionar smoke tests para wizard finish e admin pages.

10) Próximos passos
- Confirmar preferências (manter imports locais em funções críticas vs consolidar no topo).
- Autorizar limpeza automática dos dois arquivos conforme Plano de Ação Semana 0.
- Após limpeza, rodar testes e validar wizard end-to-end.

Obs.: Documento focado nos dois arquivos solicitados. Há também arquivos relacionados (clientes/wizard_views*.py) e um arquivo duplicado "wizard_views copy 2.py" no core que convém remover para reduzir ruído.
