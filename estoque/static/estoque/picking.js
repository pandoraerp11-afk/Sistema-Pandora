// picking.js - lógica principal do Kanban de Picking (extraída do template)
window.EstoquePicking = (function(){
  const api = {};
  api.init = function(){ /* inicialização futura */ };
  api.handleWebSocketMessage = function(data){ console.debug('WS picking', data); };
  return api;
})();

function atualizarKanban(){ console.log('Atualizar Kanban (placeholder)'); }
function limparFiltros(){ const ids=['filtro-prioridade','filtro-cliente','filtro-data']; ids.forEach(id=>{const el=document.getElementById(id); if(el) el.value='';}); }
function filtrarPorPrioridade(v){ console.log('Filtro prioridade', v); }
function filtrarPorCliente(v){ console.log('Filtro cliente', v); }
function filtrarPorData(v){ console.log('Filtro data', v); }
