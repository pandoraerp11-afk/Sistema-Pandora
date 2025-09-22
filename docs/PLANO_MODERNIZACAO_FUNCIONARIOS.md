# PLANO DE MODERNIZAÇÃO DO MÓDULO FUNCIONÁRIOS
## Foco: Integração com Controle de Estoque e Gestão de Materiais

### 📋 **SITUAÇÃO ATUAL**
O módulo de funcionários possui uma estrutura básica com informações pessoais, trabalhistas e salariais, mas não possui integração com o controle de estoque para gerenciar retiradas de materiais pelos funcionários.

### 🎯 **OBJETIVOS DA MODERNIZAÇÃO**
1. **Controle de Materiais**: Permitir que funcionários retirem materiais do estoque
2. **Rastreabilidade**: Registrar quem retirou, quando e para que obra/departamento
3. **Aprovação**: Sistema de aprovação para retiradas de materiais
4. **Relatórios**: Relatórios de consumo por funcionário, obra e período
5. **Responsabilidade**: Controle de responsabilidade sobre materiais entregues
6. **EPI/Ferramentas**: Controle específico para EPIs e ferramentas
7. **Integração Mobile**: Interface para retiradas via dispositivos móveis

---

## 🏗️ **FASE 1: EXTENSÃO DE MODELOS**

### 1.1 **PerfilFuncionario (Novo)**
```python
class PerfilFuncionario(models.Model):
    funcionario = models.OneToOneField(Funcionario, on_delete=models.CASCADE, related_name='perfil_estoque')
    pode_retirar_materiais = models.BooleanField(default=False, verbose_name="Pode Retirar Materiais")
    limite_valor_retirada = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    necessita_aprovacao = models.BooleanField(default=True, verbose_name="Necessita Aprovação")
    aprovador = models.ForeignKey(Funcionario, on_delete=models.SET_NULL, null=True, blank=True, related_name='funcionarios_supervisionados')
    depositos_autorizados = models.ManyToManyField('estoque.Deposito', blank=True, verbose_name="Depósitos Autorizados")
    categorias_autorizadas = models.ManyToManyField('produtos.Categoria', blank=True, verbose_name="Categorias Autorizadas")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
```

### 1.2 **CrachaFuncionario (Novo)**
```python
class CrachaFuncionario(models.Model):
    funcionario = models.OneToOneField(Funcionario, on_delete=models.CASCADE, related_name='cracha')
    codigo_cracha = models.CharField(max_length=50, unique=True, verbose_name="Código do Crachá")
    codigo_barras = models.CharField(max_length=100, blank=True, null=True, verbose_name="Código de Barras")
    qr_code = models.CharField(max_length=200, blank=True, null=True, verbose_name="QR Code")
    ativo = models.BooleanField(default=True)
    data_emissao = models.DateField(auto_now_add=True)
    data_validade = models.DateField(null=True, blank=True)
```

---

## 🏗️ **FASE 2: SISTEMA DE RETIRADA DE MATERIAIS**

### 2.1 **SolicitacaoMaterial (Novo)**
```python
class SolicitacaoMaterial(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('APROVADA', 'Aprovada'),
        ('REJEITADA', 'Rejeitada'),
        ('ENTREGUE', 'Entregue'),
        ('PARCIAL', 'Parcialmente Entregue'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    TIPO_CHOICES = [
        ('OBRA', 'Para Obra'),
        ('MANUTENCAO', 'Manutenção'),
        ('EPI', 'EPI'),
        ('FERRAMENTAS', 'Ferramentas'),
        ('CONSUMO_GERAL', 'Consumo Geral'),
    ]

    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE, related_name='solicitacoes_material')
    funcionario_solicitante = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name='solicitacoes_feitas')
    obra = models.ForeignKey('obras.Obra', on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitacoes_material')
    departamento = models.ForeignKey('core.Department', on_delete=models.SET_NULL, null=True, blank=True)
    
    numero_solicitacao = models.CharField(max_length=50, unique=True, verbose_name="Número da Solicitação")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='OBRA')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    
    data_solicitacao = models.DateTimeField(auto_now_add=True)
    data_necessidade = models.DateField(verbose_name="Data de Necessidade")
    prioridade = models.CharField(max_length=10, choices=[('BAIXA', 'Baixa'), ('MEDIA', 'Média'), ('ALTA', 'Alta')], default='MEDIA')
    
    aprovador = models.ForeignKey(Funcionario, on_delete=models.SET_NULL, null=True, blank=True, related_name='solicitacoes_aprovadas')
    data_aprovacao = models.DateTimeField(null=True, blank=True)
    observacoes_aprovacao = models.TextField(blank=True, null=True)
    
    funcionario_entrega = models.ForeignKey(Funcionario, on_delete=models.SET_NULL, null=True, blank=True, related_name='entregas_realizadas')
    data_entrega = models.DateTimeField(null=True, blank=True)
    
    justificativa = models.TextField(verbose_name="Justificativa da Solicitação")
    observacoes = models.TextField(blank=True, null=True)
    valor_total_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_total_real = models.DecimalField(max_digits=12, decimal_places=2, default=0)
```

### 2.2 **ItemSolicitacaoMaterial (Novo)**
```python
class ItemSolicitacaoMaterial(models.Model):
    solicitacao = models.ForeignKey(SolicitacaoMaterial, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.CASCADE)
    quantidade_solicitada = models.DecimalField(max_digits=14, decimal_places=4)
    quantidade_aprovada = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    quantidade_entregue = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    
    deposito_origem = models.ForeignKey('estoque.Deposito', on_delete=models.CASCADE)
    custo_unitario_estimado = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    custo_unitario_real = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    
    observacoes_item = models.TextField(blank=True, null=True)
    urgente = models.BooleanField(default=False)
```

---

## 🏗️ **FASE 3: CONTROLE DE RESPONSABILIDADE**

### 3.1 **ResponsabilidadeMaterial (Novo)**
```python
class ResponsabilidadeMaterial(models.Model):
    STATUS_CHOICES = [
        ('ATIVO', 'Ativo'),
        ('DEVOLVIDO', 'Devolvido'),
        ('PERDIDO', 'Perdido/Danificado'),
        ('CONSUMIDO', 'Consumido'),
    ]

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name='materiais_responsabilidade')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.CASCADE)
    obra = models.ForeignKey('obras.Obra', on_delete=models.SET_NULL, null=True, blank=True)
    
    quantidade_retirada = models.DecimalField(max_digits=14, decimal_places=4)
    quantidade_devolvida = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=6)
    
    data_retirada = models.DateTimeField()
    data_previsao_devolucao = models.DateField(null=True, blank=True)
    data_devolucao = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ATIVO')
    observacoes = models.TextField(blank=True, null=True)
    movimento_retirada = models.ForeignKey('estoque.MovimentoEstoque', on_delete=models.SET_NULL, null=True, related_name='responsabilidades_criadas')
    movimento_devolucao = models.ForeignKey('estoque.MovimentoEstoque', on_delete=models.SET_NULL, null=True, blank=True, related_name='responsabilidades_finalizadas')
```

### 3.2 **ControleFerramenta (Novo)**
```python
class ControleFerramenta(models.Model):
    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name='ferramentas_controle')
    produto = models.ForeignKey('produtos.Produto', on_delete=models.CASCADE)
    numero_serie = models.CharField(max_length=100, blank=True, null=True)
    patrimonio = models.CharField(max_length=50, blank=True, null=True)
    
    data_entrega = models.DateTimeField()
    data_previsao_devolucao = models.DateField()
    data_devolucao_real = models.DateTimeField(null=True, blank=True)
    
    condicao_entrega = models.TextField(verbose_name="Condição na Entrega")
    condicao_devolucao = models.TextField(blank=True, null=True, verbose_name="Condição na Devolução")
    
    termo_assinado = models.BooleanField(default=False)
    foto_entrega = models.ImageField(upload_to='controle_ferramentas/entrega/', blank=True, null=True)
    foto_devolucao = models.ImageField(upload_to='controle_ferramentas/devolucao/', blank=True, null=True)
```

---

## 🏗️ **FASE 4: VIEWS E TEMPLATES**

### 4.1 **Views Principais**
- `SolicitacaoMaterialListView`: Lista de solicitações
- `SolicitacaoMaterialCreateView`: Criação de nova solicitação
- `SolicitacaoMaterialDetailView`: Detalhes da solicitação
- `SolicitacaoMaterialApprovalView`: Aprovação de solicitações
- `EntregaMaterialView`: Interface para entrega de materiais
- `ResponsabilidadeMaterialListView`: Lista de materiais sob responsabilidade
- `RelatorioConsumoView`: Relatórios de consumo

### 4.2 **Templates Modernos**
- Interface responsiva com Bootstrap 5
- Filtros avançados por período, funcionário, obra
- Modais para aprovação rápida
- Interface móvel para retiradas

---

## 🏗️ **FASE 5: FUNCIONALIDADES AVANÇADAS**

### 5.1 **Sistema de Aprovação Hierárquica**
```python
class FluxoAprovacao(models.Model):
    tenant = models.ForeignKey('core.Tenant', on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    tipo_solicitacao = models.CharField(max_length=50)
    valor_minimo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_maximo = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    aprovadores = models.ManyToManyField(Funcionario, through='NivelAprovacao')
    ativo = models.BooleanField(default=True)

class NivelAprovacao(models.Model):
    fluxo = models.ForeignKey(FluxoAprovacao, on_delete=models.CASCADE)
    aprovador = models.ForeignKey(Funcionario, on_delete=models.CASCADE)
    nivel = models.PositiveIntegerField()
    obrigatorio = models.BooleanField(default=True)
```

### 5.2 **Alertas e Notificações**
- Notificações push para solicitações pendentes
- Alertas de materiais em atraso na devolução
- Notificações de aprovação/rejeição
- Alertas de estoque baixo para materiais frequentes

### 5.3 **Dashboard de Controle**
- Gráficos de consumo por funcionário
- Ranking de solicitações por departamento
- Indicadores de performance (tempo de aprovação, entregas)
- Mapa de calor de consumo por obra

---

## 🏗️ **FASE 6: INTEGRAÇÕES**

### 6.1 **Integração com Obras**
- Vinculação automática de solicitações a obras
- Controle de orçamento por obra
- Relatórios de consumo por obra

### 6.2 **Integração com Ponto Eletrônico**
- Registro automático de retiradas via crachá
- Validação de horário de trabalho para retiradas
- Integração com sistema de ponto

### 6.3 **Integração Mobile (Future)**
- App mobile para solicitações
- Scanner de QR Code para retiradas rápidas
- Foto comprovante de entrega/devolução

---

## 🏗️ **FASE 7: RELATÓRIOS E ANÁLISES**

### 7.1 **Relatórios Operacionais**
- Relatório de Consumo por Funcionário
- Relatório de Materiais em Atraso
- Relatório de Aprovações Pendentes
- Relatório de Custo por Obra/Departamento

### 7.2 **Análises Gerenciais**
- Análise de Perfil de Consumo
- Previsão de Demanda por Material
- Análise de Performance de Aprovadores
- ROI de Controle de Materiais

---

## 🏗️ **CRONOGRAMA DE IMPLEMENTAÇÃO**

### **Sprint 1 (2 semanas)**: Modelos Base
- [ ] Extensão do modelo Funcionario
- [ ] Criação dos modelos SolicitacaoMaterial e ItemSolicitacao
- [ ] Migrations e testes básicos

### **Sprint 2 (2 semanas)**: Interface Básica
- [ ] Views CRUD para solicitações
- [ ] Templates responsivos
- [ ] Sistema básico de aprovação

### **Sprint 3 (2 semanas)**: Controle de Responsabilidade
- [ ] Modelo ResponsabilidadeMaterial
- [ ] Interface de entrega/devolução
- [ ] Integração com MovimentoEstoque

### **Sprint 4 (2 semanas)**: Relatórios e Dashboard
- [ ] Relatórios básicos
- [ ] Dashboard de controle
- [ ] Filtros avançados

### **Sprint 5 (1 semana)**: Refinamentos
- [ ] Notificações
- [ ] Melhorias de UX
- [ ] Testes e documentação

---

## 📊 **MÉTRICAS DE SUCESSO**

1. **Operacionais**:
   - Redução de 80% no tempo de aprovação de solicitações
   - 100% de rastreabilidade de materiais entregues
   - Redução de 50% em perdas de materiais

2. **Financeiras**:
   - Redução de 30% no desperdício de materiais
   - ROI positivo em 6 meses
   - Controle de 95% dos custos de material por obra

3. **Qualidade**:
   - 95% de satisfação dos funcionários com o sistema
   - Redução de 70% em conflitos sobre responsabilidade de materiais
   - 100% de conformidade com auditorias internas

---

## 🔧 **TECNOLOGIAS UTILIZADAS**

- **Backend**: Django 4.x, Django REST Framework
- **Frontend**: Bootstrap 5, JavaScript ES6+, Chart.js
- **Database**: PostgreSQL com otimizações para relatórios
- **Mobile**: PWA (Progressive Web App) para início
- **Notificações**: Django Channels + WebSockets
- **Relatórios**: ReportLab + Pandas para análises

---

## 🛡️ **CONSIDERAÇÕES DE SEGURANÇA**

- Auditoria completa de todas as movimentações
- Controle de acesso baseado em perfis
- Criptografia de dados sensíveis
- Backup automático de dados críticos
- Logs detalhados para compliance

---

## 📚 **DOCUMENTAÇÃO E TREINAMENTO**

- Manual do usuário com screenshots
- Vídeos tutoriais para cada funcionalidade
- Treinamento presencial para administradores
- FAQ com casos mais comuns
- Documentação técnica para desenvolvedores

---

Este plano estabelece uma modernização completa do módulo de funcionários com foco específico na gestão de materiais e integração com o controle de estoque. A implementação será feita de forma incremental, permitindo uso imediato das funcionalidades básicas enquanto as avançadas são desenvolvidas.
