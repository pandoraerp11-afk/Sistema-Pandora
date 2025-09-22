# Backlog: Configurações Avançadas do Wizard de Tenant

Objetivo: consolidar itens avançados não críticos para MVP, com critérios de aceitação e dependências.

## 1) Branding (Tema / Cores)
- Itens
  - Alternar tema claro/escuro por tenant
  - Cor primária e secundária customizadas
- Critérios de Aceitação
  - Preferência salva no modelo do Tenant (ex.: theme, primary_color)
  - Aplicada em tempo real após login (middleware/context processor)
  - CSS gerado com CSS variables (fallback padrão)
- Dependências
  - Base template suportar CSS variables

## 2) Domínio Customizado (CNAME/SSL)
- Itens
  - Campo domínio customizado
  - Verificação de apontamento CNAME
  - Status do certificado SSL
- Critérios de Aceitação
  - Validação de domínio (RFC-1035) e unicidade
  - Tarefa assíncrona para validação DNS e emissão/validação SSL
  - Status visível no painel do tenant
- Dependências
  - Worker/Job (Celery/RQ), integração com provedor SSL

## 3) Notificações
- Itens
  - Canais (e-mail/WhatsApp) por evento
  - Janela de silêncio (quiet hours)
- Critérios de Aceitação
  - Preferências persistidas por tenant
  - Respeito à janela de silêncio no disparo
  - Teste de envio de e-mail via SMTP configurado
- Dependências
  - Serviço de e-mail e provedor WhatsApp/API

## 4) Segurança
- Itens
  - 2FA (TOTP)
  - Timeout de sessão por tenant
  - Política de senha (mínimo, complexidade)
- Critérios de Aceitação
  - Rotas de ativação/backup codes para 2FA
  - Sessão expira conforme configuração do tenant
  - Validações de senha aplicadas no cadastro/troca
- Dependências
  - Django-OTP (ou similar), ajustes de sessão e AUTH_PASSWORD_VALIDATORS

## 5) E-mail Remetente/SMTP
- Itens
  - Nome/E-mail remetente por tenant
  - Credenciais SMTP por tenant (opcional, criptografadas)
- Critérios de Aceitação
  - Tela de teste de envio
  - Fallback para DEFAULT_FROM_EMAIL quando não configurado
- Dependências
  - Cofre/cripto para segredos

## 6) Localização
- Itens
  - País, formato de data, 1º dia da semana
- Critérios de Aceitação
  - Preferências refletidas nos widgets e relatórios
- Dependências
  - i18n/l10n existentes

## 7) Faturamento Avançado
- Itens
  - Ciclo (mensal/anual), método de pagamento
  - Regras de pró-rata e trials
- Critérios de Aceitação
  - Próxima cobrança calculada automaticamente
  - Eventos de billing auditáveis
- Dependências
  - Integração com gateway de pagamento

## 8) Integrações (Webhooks/API Keys)
- Itens
  - Geração/rotacionamento de API keys
  - Webhooks por evento com retries
- Critérios de Aceitação
  - Histórico de entregas e retries com backoff
- Dependências
  - Tarefas assíncronas e storage de segredos

---

Checklist de implementação
- [ ] Modelagem dos campos adicionais no Tenant/Config por tenant
- [ ] Migrações e admin
- [ ] Formulários e validações
- [ ] UI no wizard e no painel de configurações pós-onboarding
- [ ] Serviços (jobs, integrações) e testes
- [ ] Documentação e observabilidade (logs/metrics)
