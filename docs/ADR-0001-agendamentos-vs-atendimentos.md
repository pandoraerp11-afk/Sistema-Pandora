## ADR-0001: Nome do Módulo - "agendamentos" vs "atendimentos"

Data: 2025-08-22

### Contexto
Precisamos extrair a lógica de reserva (slots, disponibilidades, reagendamentos) do módulo `prontuarios`. Dois nomes candidatos: `agendamentos` (booking) e `atendimentos` (service execution). O segundo já está semanticamente carregado no domínio clínico.

### Decisão
Adotar o nome de app **`agendamentos`** para o núcleo genérico de reservas. O termo "atendimento" permanece nos contextos que lidam com execução/registro (ex: prontuário clínico, atendimento operacional) evitando colisão conceitual.

### Consequências
Positivas:
- Neutralidade multissetor.
- Facilita separar lifecycle (Reserva vs Execução).
- Reduz ambiguidade em documentação e APIs.

Negativas / Trade-offs:
- Requer tradução mental para usuários já habituados a chamar todo o fluxo de "atendimento".
- Necessita material educativo (tooltips, docs) na transição.

### Alternativas Consideradas
1. `atendimentos`: rejeitada por conflitar com execução clínica.
2. `agenda` / `calendar`: muito amplo e poderia conflitar com módulo de eventos existente.
3. `compromissos`: menos comum em linguagem de negócio dos clientes atuais.

### Ações de Suporte
- Criar alias/rotas legadas se necessário (`/api/atendimentos/agendar` → redireciona/new service) em fase de transição.
- Atualizar documentação do usuário final.

### Status
Aceita.
