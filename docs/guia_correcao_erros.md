# Guia de Correção de Erros (Ruff, Pylance/Pyright e Django)

Este guia padroniza como corrigir erros e avisos no projeto Pandora para manter o código limpo, seguro e consistente, sem alterar regras de negócio. Abrange Ruff (lint/format), Pylance/Pyright (tipagem), e padrões Django.

## Sumário
- Objetivos e princípios
- Ferramentas e configurações do projeto
- Fluxo de trabalho recomendado
- Correção por categorias de erros
  - Sintaxe e imports (Ruff E/F/I)
  - Estilo e formatação (Ruff E/W)
  - Modernizações Python (Ruff UP)
  - Simplificações (Ruff SIM)
  - Segurança (Ruff S – Bandit)
  - Tipagem: Pylance/Pyright (PL) e Ruff ANN
  - Padrões Django (forms, widgets, validações)
- Uso correto de supressões (# noqa e type: ignore)
- Exemplos práticos do projeto
- Checklist rápido
- Comandos úteis (Windows PowerShell)

---

## Objetivos e princípios
- Corrigir a causa raiz, não suprimir sem necessidade.
- Não remover campos ou mudar regras de negócio ao limpar avisos.
- Preferir padrões consistentes em todo o projeto (imports absolutos, `pathlib.Path`, `gettext`).
- Supressões específicas e justificadas (com código da regra), apenas quando inevitável.

## Ferramentas e configurações do projeto
- Ruff: configurado via `pyproject.toml` (regras E, F, B, I, UP, SIM, S, PL, ANN; largura de 120 colunas).
- Pylance/Pyright: `pyrightconfig.json` controla a análise no VS Code.
- Django 5.x; Python 3.12+.
- Testes: `pytest`.

## Fluxo de trabalho recomendado
1. Abrir a aba Problems no VS Code e o arquivo com erro.
2. Ler o código/descrição da regra (ex.: F401, W293, S308, reportGeneralTypeIssues).
3. Corrigir a causa raiz usando as seções abaixo; somente suprimir se for um falso positivo inevitável.
4. Rodar checagens/formatador e testes.
5. Commitar com mensagem clara (ex.: "lint: corrigir W293 e I001 em core/wizard_forms.py").

Comandos úteis no Windows PowerShell:
```powershell
# Instalar deps de dev (se necessário)
pip install -r requirements-dev.txt

# Lint/format com Ruff
ruff check . --fix
ruff format .

# Rodar testes
C:/Users/Terminal/AppData/Local/Programs/Python/Python313/python.exe -m pytest -q
```

---

## Correção por categorias de erros

### 1) Sintaxe e imports (Ruff E/F/I)
- F401 (import não usado): remover import ou usar onde necessário.
- F821 (nome não definido): corrigir escopo/ordem de definição ou adicionar import.
- E402 (import fora do topo): mover imports para o topo do arquivo.
- I001/I002 (ordem/agrupamento de imports): deixar o Ruff organizar (`ruff check --fix`).
- E999 (erro de sintaxe): consertar indentação, parênteses, dois pontos, etc.

### 2) Estilo e formatação (Ruff E/W)
- E501 (linha longa): quebrar em múltiplas linhas com parênteses; limite: 120.
- W293 (linha em branco com espaços): remover espaços ao fim da linha/linha vazia.
- E302/E305 (linhas em branco faltando/sobrando): ajustar espaçamento entre defs/classes.

### 3) Modernizações Python (Ruff UP)
- UP0xx (literal/estrutura moderna): usar `|` para unions (ex.: `int | None`) em Python 3.12+.
- UP (f-strings vs format): manter coerência com i18n (ver seção Django/i18n abaixo).

### 4) Simplificações (Ruff SIM)
- SIM1xx (if encadeado/retornos redundantes): reduzir complexidade mantendo legibilidade.
- C901 (função muito complexa): refatorar o método em funções auxiliares menores e com responsabilidade única.
- Evitar early-returns confusos quando há tipagem/fluxo melhor com variável acumuladora (ex.: normalização em widgets).

### 5) Segurança (Ruff S – Bandit)
- S308 (mark_safe): preferir `format_html` sempre que possível. Se usar `mark_safe`, garantir que a string é controlada e estática, e justificar com `# noqa: S308` no final da linha.
- Uploads: validar extensão, tamanho e quantidade. Não confiar em `content_type` do cliente. Usar `UploadedFile` e limites configuráveis.

### 6) Tipagem: Pylance/Pyright (PL) e Ruff ANN
- **Assinaturas com `*args` e `**kwargs`**: Para evitar erros `ANN401` (`Dynamically typed expressions (Any) are disallowed`), use tipos explícitos como `tuple` e `dict`. Para assinaturas que precisam de flexibilidade (como `__init__` de Forms), use `noqa` específico.
  *Exemplo 1: Tipagem explícita*
  ```python
  # Em vez de: def create(self, request: Request, *args: Any, **kwargs: Any)
  def create(self, request: Request, *args: tuple, **kwargs: dict) -> Response:
      ...
  ```
  *Exemplo 2: Supressão justificada em `__init__`*
  ```python
  def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
      ...
      super().__init__(*args, **kwargs)
  ```
- `ClassVar`: ao digitar `Meta.fields`, `widgets`, `labels` fora de `class Meta`, anotar com `ClassVar[...]` para não virar atributo de instância.
- Tipos de `Widget.render`: retorno deve ser string segura; use `from django.utils.safestring import mark_safe` e anote o retorno como `str` (ou `SafeString` em `TYPE_CHECKING`).
- `value_from_datadict`: respeitar assinaturas do Django e retornar tipos compatíveis (ex.: `UploadedFile | Sequence[UploadedFile] | None`).
- Evitar `Any` desnecessário; usar `Mapping`, `Sequence`, `Path`.
- **Incompatibilidade entre `HttpRequest` (Django) e `Request` (DRF):** Em `ViewSets` do DRF, `self.request` é um `HttpRequest` do Django. Se uma função auxiliar espera um `rest_framework.request.Request`, o Pylance acusará `reportArgumentType`. A solução é converter o objeto explicitamente.
  *Antes:*
  ```python
  # Causa o erro: O argumento do tipo "HttpRequest" não pode ser atribuído...
  cliente = _resolver_cliente_do_usuario(self.request)
  ```
  *Depois:*
  ```python
  from rest_framework.request import Request

  # Converte o HttpRequest do Django para o Request do DRF
  cliente = _resolver_cliente_do_usuario(Request(self.request))
  ```

### 7) Padrões Django (forms, widgets, validações)
- Widgets: construa `attrs` via `build_attrs`; não exponha valores de file inputs.
- `clean_*`: sempre retornar o valor normalizado e levantar `ValidationError` com mensagens amigáveis.
- Datas: aceitar formatos pt-BR e ISO; ajustar `widget=DateInput(format=..., attrs={...})` sem quebrar a UI.
- Unicidade ao editar: usar `_editing_tenant_pk` para `exclude(pk=...)` no `queryset` de validações.
- i18n: evite f-strings dentro de `_(...)` quando houver variáveis. Prefira placeholders:
  ```python
  raise ValidationError(_("Máximo de %(n)d arquivos.") % {"n": max_files})
  ```

---

## Uso correto de supressões
- Nunca usar `# noqa` sozinho (Ruff acusa PGH004). Sempre específico: `# noqa: S308`.
- Para múltiplas regras: `# noqa: ANN002, ANN003`.
- Em tipagem: preferir ajustar tipos. Se inevitável, `# type: ignore[reportGeneralTypeIssues]` com comentário curto.
- Comente o porquê: supressões devem ser raras, localizadas e justificadas.

---

## Exemplos práticos do projeto

### A) Widget.render seguro
Antes:
```python
return mark_safe(html)  # noqa
```
Depois:
```python
return mark_safe(html)  # noqa: S308  # HTML estático controlado pelo próprio widget
```

### B) Assinatura de ModelForm.__init__
Antes:
```python
def __init__(self, data: dict[str, Any] | None, files: dict[str, Any] | None, editing_tenant_pk: int | None = None):
    ...
```
Depois:
```python
def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
    pk_obj = kwargs.pop("editing_tenant_pk", None)
    self._editing_tenant_pk: int | None = pk_obj if isinstance(pk_obj, int) else None
    super().__init__(*args, **kwargs)
```

### C) value_from_datadict robusto
```python
def value_from_datadict(self, _data: Mapping[str, object], files: Mapping[str, object], name: str):
    result = None
    getlist = getattr(files, "getlist", None)
    if callable(getlist):
        try:
            upload_obj = getlist(name)
        except Exception:
            upload_obj = None
    else:
        upload_obj = None
    # tratar single/múltiplos UploadedFile e filtrar tipos inválidos
    ...
    return result
```

### D) ClassVar para mapas estáticos
```python
widgets: ClassVar[dict[str, forms.Widget]] = { ... }
labels: ClassVar[dict[str, str]] = { ... }
```

### E) Mensagens traduzíveis sem f-string
Antes:
```python
raise ValidationError(_(f"Máximo de {max_files} arquivos."))
```
Depois:
```python
raise ValidationError(_("Máximo de %(n)d arquivos.") % {"n": max_files})
```

---

## Checklist rápido
- Imports absolutos e organizados (Ruff isort).
- Sem espaços à direita; linhas ≤ 120 colunas.
- Sem `# noqa` genérico; use códigos específicos.
- Assinaturas Django com `*args, **kwargs` e supressões `ANN002/ANN003` quando necessário.
- `ClassVar` em mapas estáticos.
- `mark_safe` apenas quando inevitável, com `# noqa: S308` e HTML controlado.
- Validações de upload: limite de quantidade, tamanho e extensão.
- JSON: parse seguro com limites de elementos.
- Datas: input_formats pt-BR e ISO; widgets ajustados.
- Rode `ruff check --fix`, `ruff format` e `pytest` antes de commit.

---

## Comandos úteis (Windows PowerShell)
```powershell
# Lintar e corrigir automaticamente o que for seguro
ruff check . --fix

# Formatar código
ruff format .

# Rodar testes rápidos
C:/Users/Terminal/AppData/Local/Programs/Python/Python313/python.exe -m pytest -q

# Rodar teste de um arquivo específico (exemplo)
C:/Users/Terminal/AppData/Local/Programs/Python/Python313/python.exe -m pytest -q tests/core/menu_middleware/test_views.py
```

---

Dúvidas ou exceções de casos reais? Documente no final deste arquivo a decisão aplicada e o motivo da supressão, para manter o histórico técnico claro.