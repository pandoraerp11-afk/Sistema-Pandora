# 🎯 GUIA DEFINITIVO - DIFERENÇAS ENTRE MÓDULOS PRINCIPAIS

## 📋 RESUMO EXECUTIVO

Este documento esclarece **definitivamente** as diferenças entre os três módulos principais do Pandora ERP, eliminando qualquer confusão sobre suas responsabilidades e níveis de acesso.

---

## 🔑 OS TRÊS MÓDULOS PRINCIPAIS

### **1. CORE - "O Dono do Sistema"**
### **2. admin - "O Administrador da Empresa"** 
### **3. USER_MANAGEMENT - "O Gerenciador Universal"**

---

## 🏛️ MÓDULO CORE - SUPER ADMIN

### **👑 QUEM ACESSA**
```python
# Apenas o DONO DO SISTEMA (Super Administrador)
user.is_superuser = True
# NÃO precisa selecionar empresa
# Acesso TOTAL e IRRESTRITO
```

### **🎯 RESPONSABILIDADE PRINCIPAL**
**Gerenciar o SISTEMA como um todo - todas as empresas clientes**

### **⚡ PODERES ESPECIAIS**
- ✅ **Acesso sem limitações** - Não precisa selecionar empresa
- ✅ **Criar empresas clientes** - Novos tenants no sistema
- ✅ **Configurar módulos** - Quais módulos cada empresa pode usar
- ✅ **Ver TODOS os usuários** - De todas as empresas
- ✅ **Acessar TODOS os módulos** - Sem restrições
- ✅ **Configurações globais** - Parâmetros do sistema
- ✅ **Backup e manutenção** - Operações críticas

### **🌐 ESCOPO DE VISÃO**
```
GLOBAL - VÊ TUDO
├── Empresa A (100 usuários)
├── Empresa B (50 usuários) 
├── Empresa C (200 usuários)
└── Todas as outras empresas...
```

### **📊 DASHBOARDS EXCLUSIVOS**
- **Dashboard Global**: `/core/dashboard/`
  - Total de empresas no sistema
  - Total de usuários globais
  - Uso de recursos por empresa
  - Performance global do sistema

### **🔧 FUNCIONALIDADES ÚNICAS**
```python
# Criar nova empresa cliente
def create_tenant(request):
    # Só Super Admin pode fazer isso
    tenant = Tenant.objects.create(
        name="Nova Empresa Ltda",
        subdomain="nova-empresa",
        enabled_modules={
            'clientes': True,
            'obras': True,
            'financeiro': False  # Pode escolher quais módulos liberar
        }
    )
```

### **📁 URLs PRINCIPAIS**
- `/core/dashboard/` - Dashboard global do sistema
- `/core/tenant/` - Lista todas as empresas
- `/core/tenant/create/` - Criar nova empresa
- `/core/tenant/<id>/edit/` - Editar qualquer empresa
- `/core/system-config/` - Configurações globais

---

## 🏢 MÓDULO admin - ADMIN DA EMPRESA

### **👔 QUEM ACESSA**
```python
# Administradores de empresa específica
user.perfil_estendido.tipo_usuario = 'admin_empresa'
# OBRIGATÓRIO selecionar empresa
# Acesso apenas à SUA empresa
```

### **🎯 RESPONSABILIDADE PRINCIPAL**
**Gerenciar SUA EMPRESA específica - usuários e configurações locais**

### **⚡ PODERES LIMITADOS À SUA EMPRESA**
- ✅ **Gerenciar usuários da empresa** - Apenas funcionários/colaboradores
- ✅ **Configurar departamentos** - Estrutura organizacional local
- ✅ **Definir cargos e permissões** - Hierarquia interna
- ✅ **Convidar novos usuários** - Para trabalhar na empresa
- ✅ **Configurar dados da empresa** - Informações cadastrais
- ✅ **Personalizar interface** - Logo, cores, preferências
- ❌ **NÃO pode criar outras empresas**
- ❌ **NÃO vê usuários de outras empresas**

### **🏢 ESCOPO DE VISÃO**
```
LOCAL - SÓ VÊ SUA EMPRESA
└── Empresa A (SUA empresa)
    ├── Funcionário 1
    ├── Funcionário 2
    ├── Cliente X
    └── Fornecedor Y
    
❌ NÃO VÊ: Empresa B, C, D...
```

### **📊 DASHBOARDS DA EMPRESA**
- **Dashboard Empresarial**: `/admin-panel/management/`
  - Funcionários da empresa
  - Performance da equipe
  - Métricas dos departamentos
  - Atividades recentes da empresa

### **🔧 FUNCIONALIDADES ESPECÍFICAS**
```python
# Convidar usuário para SUA empresa
def invite_user_to_company(request):
    # Admin só pode convidar para sua própria empresa
    convite = ConviteUsuario.objects.create(
        email="novo@funcionario.com",
        tenant=request.tenant,  # Apenas SUA empresa
        tipo_usuario="funcionario",
        convidado_por=request.user
    )
```

### **📁 URLs PRINCIPAIS**
- `/admin-panel/` - Dashboard da empresa
- `/admin-panel/management/` - Gestão completa
- `/admin-panel/users/` - Usuários da empresa
- `/admin-panel/departments/` - Departamentos
- `/admin-panel/settings/` - Configurações da empresa

---

## 👥 MÓDULO USER_MANAGEMENT - GESTÃO UNIFICADA

### **🌟 QUEM ACESSA**
```python
# TODOS os tipos de usuários (mas com visões diferentes)
# Super Admin: Vê TUDO
# Admin Empresa: Vê só sua empresa  
# Usuário comum: Vê só seu perfil
```

### **🎯 RESPONSABILIDADE PRINCIPAL**
**Sistema UNIFICADO de gestão de usuários - adapta-se ao perfil de quem acessa**

### **🔄 FUNCIONAMENTO INTELIGENTE**

#### **Para SUPER ADMIN**
```python
# Visão GLOBAL - Todos os usuários de todas as empresas
if user.is_superuser:
    usuarios = PerfilUsuarioEstendido.objects.all()  # TODOS
    pode_criar_para_qualquer_empresa = True
```

#### **Para ADMIN DA EMPRESA**
```python
# Visão LOCAL - Só usuários da própria empresa
if user.perfil_estendido.tipo_usuario == 'admin_empresa':
    usuarios = PerfilUsuarioEstendido.objects.filter(
        user__tenant=request.tenant  # Só SUA empresa
    )
    pode_criar_para_sua_empresa = True
```

#### **Para USUÁRIO COMUM**
```python
# Visão PESSOAL - Só seu próprio perfil
else:
    usuarios = [user.perfil_estendido]  # Só ele mesmo
    pode_editar_proprio_perfil = True
```

### **⚡ FUNCIONALIDADES ADAPTÁVEIS**

#### **Interface Inteligente**
```html
<!-- A mesma URL, interfaces diferentes -->
/user-management/usuario/

<!-- Para Super Admin -->
<h1>Todos os Usuários do Sistema (500 usuários)</h1>
<button>Criar usuário para qualquer empresa</button>

<!-- Para Admin da Empresa -->
<h1>Usuários da Empresa ABC (25 usuários)</h1>
<button>Convidar usuário para nossa empresa</button>

<!-- Para Usuário Comum -->
<h1>Meu Perfil</h1>
<button>Editar meus dados</button>
```

### **🔧 LÓGICA DE NEGÓCIO UNIFICADA**
```python
class UsuarioViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        user = self.request.user
        
        # Super Admin: VÊ TODOS
        if user.is_superuser:
            return PerfilUsuarioEstendido.objects.all()
        
        # Admin Empresa: VÊ SÓ SUA EMPRESA
        elif user.perfil_estendido.tipo_usuario == 'admin_empresa':
            return PerfilUsuarioEstendido.objects.filter(
                user__tenant=self.request.tenant
            )
        
        # Usuário Comum: VÊ SÓ ELE MESMO
        else:
            return PerfilUsuarioEstendido.objects.filter(
                user=user
            )
    
    def perform_create(self, serializer):
        # Super Admin: Pode criar para qualquer empresa
        if self.request.user.is_superuser:
            tenant_id = self.request.data.get('tenant_id')
            tenant = Tenant.objects.get(id=tenant_id)
        
        # Admin Empresa: Só para sua empresa
        else:
            tenant = self.request.tenant
        
        serializer.save(tenant=tenant)
```

### **📁 URLs UNIFICADAS**
- `/user-management/dashboard/` - Dashboard (filtrado por perfil)
- `/user-management/usuario/` - Lista (filtrada por acesso)
- `/user-management/usuario/create/` - Criar (limitado por perfil)
- `/user-management/perfil/` - Perfil pessoal (todos)
- `/user-management/convite/` - Convites (filtrados)

---

## 🔄 FLUXO PRÁTICO DE USO

### **1. Super Admin (Dono do Sistema)**
```
1. 🔐 Faz login (is_superuser=True)
2. 🏠 Vai para Dashboard Global (/core/dashboard/)
3. 🏢 Ve todas as empresas cadastradas
4. ➕ Pode criar nova empresa no CORE
5. 👥 Pode ir ao USER_MANAGEMENT e ver TODOS os usuários
6. ⚙️ Pode configurar qualquer coisa
```

### **2. Admin da Empresa XYZ**
```
1. 🔐 Faz login (tipo_usuario='admin_empresa')
2. 🏢 OBRIGATÓRIO selecionar empresa XYZ
3. 🏠 Vai para Dashboard da Empresa (/admin-panel/management/)
4. 👥 Só vê funcionários da empresa XYZ
5. ➕ Pode convidar usuários para empresa XYZ
6. ⚙️ Pode configurar apenas a empresa XYZ
7. 🚫 NÃO acessa CORE (negado)
```

### **3. Funcionário da Empresa XYZ**
```
1. 🔐 Faz login (tipo_usuario='funcionario')
2. 🏢 OBRIGATÓRIO selecionar empresa XYZ
3. 🏠 Vai para módulos permitidos (obras, clientes, etc.)
4. 👤 Pode ver/editar apenas seu perfil no USER_MANAGEMENT
5. 🚫 NÃO acessa CORE nem admin
6. ✅ Usa módulos operacionais conforme permissões
```

---

## 📊 MATRIZ COMPARATIVA FINAL

| Aspecto | CORE | admin | USER_MANAGEMENT |
|---------|------|-----------------|-----------------|
| **Quem Acessa** | Só Super Admin | Admin Empresa + Super Admin | Todos (visões diferentes) |
| **Selecionar Empresa** | ❌ Opcional | ✅ Obrigatório | ✅ Obrigatório* |
| **Escopo** | Global (todas empresas) | Local (uma empresa) | Contextual (adaptável) |
| **Criar Empresas** | ✅ Sim | ❌ Não | ❌ Não |
| **Ver Todos Usuários** | ✅ Sim | ❌ Só sua empresa | ✅ Contextual |
| **Configurações** | ✅ Globais | ✅ Da empresa | ❌ Não |
| **Métricas** | ✅ Sistema todo | ✅ Uma empresa | ✅ Usuários |

*Exceto Super Admin no USER_MANAGEMENT

---

## 🎯 CENÁRIOS DE USO PRÁTICO

### **Cenário 1: Criando Nova Empresa Cliente**
```
1. Super Admin acessa CORE
2. Vai em "Gerenciar Empresas"  
3. Clica "Nova Empresa"
4. Preenche dados da empresa
5. Escolhe módulos habilitados
6. Cria admin da empresa
7. Empresa fica disponível no sistema
```

### **Cenário 2: Empresa Configurando Seus Usuários**
```
1. Admin da Empresa faz login
2. Seleciona sua empresa
3. Vai ao admin
4. Acessa "Gerenciar Usuários da Empresa"
5. Convida funcionários
6. Define cargos e permissões
7. Configura departamentos
```

### **Cenário 3: Funcionário Editando Perfil**
```
1. Funcionário faz login
2. Seleciona empresa onde trabalha
3. Vai ao USER_MANAGEMENT
4. Vê apenas "Meu Perfil"
5. Edita dados pessoais
6. Configura notificações
7. Altera senha
```

---

## ⚠️ PRINCIPAIS CONFUSÕES E ESCLARECIMENTOS

### **❌ CONFUSÃO COMUM 1**
"Por que existem 3 módulos para usuários?"

**✅ ESCLARECIMENTO:**
- **CORE**: Para o DONO criar empresas
- **admin**: Para EMPRESAS gerenciarem funcionários
- **USER_MANAGEMENT**: Sistema UNIFICADO que se adapta

### **❌ CONFUSÃO COMUM 2**
"Qual a diferença entre admin e USER_MANAGEMENT?"

**✅ ESCLARECIMENTO:**
- **admin**: Dashboard completo da empresa + gestão local
- **USER_MANAGEMENT**: Módulo específico só para usuários (mas universal)

### **❌ CONFUSÃO COMUM 3**
"Super Admin precisa selecionar empresa?"

**✅ ESCLARECIMENTO:**
- **CORE**: NÃO precisa (acesso global)
- **admin**: Pode selecionar (para ver empresa específica)  
- **USER_MANAGEMENT**: Pode selecionar (para filtrar contexto)
- **Módulos Operacionais**: Precisa selecionar

---

## 🚀 RESUMO FINAL

### **🏛️ CORE = "Eu sou o DONO do sistema"**
- Crio empresas clientes
- Configuro o sistema todo
- Vejo tudo sem limitação

### **🏢 admin = "Eu administro MINHA empresa"**
- Gerencio minha equipe
- Configuro minha empresa
- Não vejo outras empresas

### **👥 USER_MANAGEMENT = "Eu gerencio usuários (conforme meu nível)"**
- Se sou Super Admin: Vejo todos
- Se sou Admin: Vejo minha empresa
- Se sou Usuário: Vejo meu perfil

**Cada módulo tem sua função específica e bem definida no ecossistema Pandora ERP!**
