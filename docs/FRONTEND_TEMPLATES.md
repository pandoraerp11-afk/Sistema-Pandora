# Padrões de Templates Ultra Modern

## Bases
| Template | Uso | Blocks Principais |
|----------|-----|-------------------|
| `pandora_ultra_modern_base.html` | Base raiz | `title`, `content`, `extra_css`, `extra_js` |
| `pandora_home_ultra_modern.html` | Homes / Dashboards | `page_title`, `hero`, `statistics` |
| `pandora_list_ultra_modern.html` | Listas padronizadas | `page_icon`, `page_title`, `page_subtitle`, `list_actions`, `list_filters`, `list_table` |
| `pandora_form_ultra_modern.html` | Formulários | `page_title`, `form_main`, `extra_js` |

## Estatísticas
Contexto `statistics` (lista de dicts):
```python
[{
  'label': 'Total',
  'value': 120,
  'icon': 'fas fa-database',
  'color': 'primary'
}]
```
Renderizadas automaticamente em cards.

## Ações de Lista
Partial `_list_actions_card.html` exibe:
- Botão Dashboard (se `dashboard_url`)
- Exportar / Buscar / Adicionar (condicional a variáveis de contexto)

## Campos de Form Dinâmicos
Evitar lógica inline (`'a,b,c'.split(',')`). Usar listas no contexto:
```python
ctx['basic_fields'] = ['cliente','profissional','origem']
```
E filtro `get_field`.

## Filtros Customizados
Local: `agendamentos/templatetags/agendamento_extras.py`
- `get_field(form, name)` retorna bound field ou None.
- `add_class(field, css)` agrega classes.

## Boas Práticas
- Evitar loops sobre strings estáticas com filters não suportados.
- Usar `widthratio` para porcentagens em template quando simples (ou calcular no view).
- Manter ícones Font Awesome declarados em estatísticas / ações.

## Erros Corrigidos Recorrentes
| Problema | Solução |
|----------|---------|
| Uso de `.split()` em template | Substituído por listas no contexto |
| Filtros aritméticos inexistentes (`div`, `mul`) | Cálculo no view / `widthratio` |
| Código fora de método `get_context_data` | Reindentado corretamente |

## Extensão
Para novo módulo:
1. Criar listas herdando `pandora_list_ultra_modern`.
2. Injetar `statistics` e `dashboard_url`.
3. Garantir actions via include do partial.
