# SISTEMA DE WIZARD EXTENSÍVEL - CLIENTES
## Implementação Completa com ZERO RISCO ao Sistema Original

### ✅ **O QUE FOI IMPLEMENTADO**

Este sistema permite **reutilizar** o wizard do core (tenants) para criar/editar **clientes** mantendo **100% da funcionalidade original** intacta.

---

## 🏗️ **ARQUITETURA ZERO-RISCO**

### **1. core/wizard_extensions.py**
**Sistema base para extensões do wizard**
```python
class WizardExtensionMixin:
    """Base para todas as extensões do wizard"""
    
class ClienteWizardMixin(WizardExtensionMixin):
    """Configuração específica para clientes"""
    entity_name = "cliente"
    requires_superuser = False  # Diferente do tenant wizard
    requires_tenant_access = True
```

**🔐 SEGURANÇA**: Mantém todos os mixins de segurança existentes

### **2. clientes/wizard_forms.py**
**Formulários específicos para o wizard de clientes**
```python
# 5 Formulários seguindo exatamente o padrão do core:
ClienteIdentificationWizardForm     # Step 1: Dados básicos + tipo PJ/PF
ClientePessoaJuridicaWizardForm     # Step 1: Dados específicos PJ
ClientePessoaFisicaWizardForm       # Step 1: Dados específicos PF
ClienteAddressWizardForm            # Step 2: Endereço principal
ClienteContactsWizardForm           # Step 3: Contatos adicionais
ClienteDocumentsWizardForm          # Step 4: Upload de documentos
ClienteReviewWizardForm             # Step 5: Confirmação final
```

**✨ CARACTERÍSTICAS**:
- Widgets com classes CSS idênticas ao wizard original
- Validação integrada usando clean_methods
- Suporte completo a PJ/PF (igual ao core)

### **3. clientes/wizard_views.py**
**View principal que HERDA do wizard original**
```python
class ClienteWizardView(ClienteWizardMixin, TenantRequiredMixin, TenantCreationWizardView):
    """
    HERDA 100% da funcionalidade do wizard original
    Apenas customiza o que é específico para clientes
    """
```

**🎯 FUNCIONALIDADES**:
- ✅ Criação de novos clientes via wizard
- ✅ Edição de clientes existentes  
- ✅ Preserva todo o sistema de steps
- ✅ Mantém segurança multi-tenant
- ✅ Preview dinâmico (herda do core)
- ✅ Validação em tempo real
- ✅ Sistema de sessão para dados temporários

### **4. clientes/wizard_urls.py**
**URLs de TESTE isoladas**
```python
# URLs para testar SEM afetar o sistema principal
path('wizard/novo/', ClienteWizardView.as_view(), name='test_wizard_create')
path('wizard/editar/<int:pk>/', ClienteWizardView.as_view(), name='test_wizard_edit')
```

---

## 🛡️ **GARANTIAS DE SEGURANÇA**

### **Multi-Tenant 100% Preservado**
```python
# TODA consulta filtrada por tenant (herdado do core)
Cliente.objects.filter(tenant=self.request.tenant)

# Acesso controlado por TenantRequiredMixin
class ClienteWizardView(TenantRequiredMixin, ...):
    def test_func(self) -> bool:
        return hasattr(self.request, 'tenant') and self.request.tenant is not None
```

### **Permissões Customizadas**
- **Tenant Wizard**: Requer `superuser = True`
- **Cliente Wizard**: Requer apenas `tenant_access = True`

---

## 🚀 **COMO TESTAR**

### **1. Ativar URLs de Teste**
No arquivo principal `pandora_erp/urls.py`, adicione:
```python
# TESTE do wizard de clientes (temporário)
path('clientes/', include('clientes.wizard_urls')),
```

### **2. Acessar URLs de Teste**
```bash
# Criar novo cliente
http://localhost:8000/clientes/wizard/novo/

# Editar cliente existente (ID 1)
http://localhost:8000/clientes/wizard/editar/1/
```

### **3. Testar Funcionalidades**
- ✅ Navegação entre steps
- ✅ Validação de formulários
- ✅ Preview dinâmico
- ✅ Salvamento em sessão
- ✅ Criação/edição de clientes
- ✅ Isolamento multi-tenant

---

## 📋 **CHECKLIST DE VALIDAÇÃO**

### **Funcionalidade Básica**
- [ ] Wizard carrega sem erros
- [ ] Navegação entre steps funciona
- [ ] Formulários validam corretamente
- [ ] Preview atualiza dinamicamente
- [ ] Dados salvam na sessão

### **Funcionalidade de Cliente**
- [ ] Cria cliente PF corretamente
- [ ] Cria cliente PJ corretamente  
- [ ] Edita cliente existente
- [ ] Salva endereços
- [ ] Upload de documentos funciona

### **Segurança Multi-Tenant**
- [ ] Apenas clientes do tenant aparecem
- [ ] Não é possível acessar clientes de outros tenants
- [ ] Permissões de usuário respeitadas

### **Integração com Sistema**
- [ ] Não quebra funcionalidades existentes
- [ ] URLs originais continuam funcionando
- [ ] Wizard de tenants continua intacto

---

## 🔧 **INTEGRAÇÃO FINAL**

Quando os testes estiverem **100% validados**:

### **1. Integrar URLs ao Sistema Principal**
Em `clientes/urls.py`:
```python
# Adicionar ao final
path('wizard/novo/', wizard_views.ClienteWizardView.as_view(), name='wizard_create'),
path('wizard/editar/<int:pk>/', wizard_views.ClienteWizardView.as_view(), name='wizard_edit'),
```

### **2. Adicionar Botões na Interface**
```html
<!-- Em clientes/templates/clientes/list.html -->
<a href="{% url 'clientes:wizard_create' %}" class="btn btn-primary">
    <i class="fas fa-magic"></i> Novo Cliente (Wizard)
</a>
```

### **3. Remover URLs de Teste**
Remover `include('clientes.wizard_urls')` do arquivo principal.

---

## 🌟 **VANTAGENS DESTA ABORDAGEM**

### **1. Zero Risco**
- ❌ **NÃO modifica** uma linha do wizard original
- ✅ **Herda** toda funcionalidade existente
- ✅ **Preserva** toda a segurança

### **2. Máxima Reutilização**
- ✅ Aproveitamento de **100%** do código do core
- ✅ Preview dinâmico **automático**
- ✅ Sistema de sessão **herdado**

### **3. Extensibilidade**
- ✅ Base para wizard de **fornecedores**
- ✅ Base para wizard de **funcionários** 
- ✅ Padrão para **qualquer entidade**

### **4. Manutenibilidade**
- ✅ Melhorias no core beneficiam **todos** os wizards
- ✅ Bugs corrigidos no core se aplicam **automaticamente**
- ✅ Código organizado e **documentado**

---

## 📚 **PRÓXIMOS PASSOS RECOMENDADOS**

1. **Testar** o wizard de clientes isoladamente
2. **Validar** todas as funcionalidades 
3. **Verificar** segurança multi-tenant
4. **Integrar** ao sistema principal quando validado
5. **Implementar** wizard para fornecedores usando a mesma base
6. **Expandir** para outros módulos conforme necessário

---

## 🎯 **CONCLUSÃO**

Este sistema fornece uma **base sólida e segura** para reutilizar o wizard em múltiplos módulos, mantendo **zero risco** ao código original e **máxima compatibilidade** com o sistema existente.

**Status**: ✅ **Pronto para testes**
