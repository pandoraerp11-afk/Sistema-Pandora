// ES Module para ações de user_management (2FA e sessões)
// Profissionalização: uso de utilitário HTTP central, disparo de eventos e zero poluição global.

import { apiPost, fireEvent } from '/static/core/utils/http.js';

let initialized = false;

function updateBadge(enabled) {
  const badge = document.querySelector('[data-2fa-status]');
  if (!badge) return;
  badge.textContent = enabled ? '2FA Ativo' : '2FA Inativo';
  badge.classList.toggle('bg-success', enabled);
  badge.classList.toggle('bg-secondary', !enabled);
}

async function handleToggleTwoFactor(btn) {
  if (!btn) return;
  const url = btn.dataset.url;
  btn.disabled = true;
  try {
    const data = await apiPost(url);
    if (data.status === 'ok') {
      updateBadge(!!data.enabled);
      fireEvent('user:2faToggled', { enabled: !!data.enabled, data });
    } else {
      fireEvent('ui:notify', { type: 'danger', title: 'Erro', message: data.detail || 'Falha ao alterar 2FA' });
      alert(data.detail || 'Erro ao alterar 2FA');
    }
  } catch (err) {
    fireEvent('ui:notify', { type: 'danger', title: 'Erro', message: err.message });
    alert(err.message || 'Falha na requisição');
  } finally {
    btn.disabled = false;
  }
}

async function handleEncerrarSessao(btn) {
  if (!btn) return;
  const url = btn.dataset.url;
  const row = btn.closest('tr');
  btn.disabled = true;
  try {
    const data = await apiPost(url);
    if (data.status === 'ok') {
      if (row) row.remove();
      fireEvent('user:sessionTerminated', { sessionRow: row, data });
    } else {
      fireEvent('ui:notify', { type: 'warning', title: 'Sessão', message: data.detail || 'Erro ao encerrar sessão' });
      alert(data.detail || 'Erro ao encerrar sessão');
    }
  } catch (err) {
    fireEvent('ui:notify', { type: 'danger', title: 'Erro', message: err.message });
    alert(err.message || 'Falha na requisição');
  } finally {
    btn.disabled = false;
  }
}

async function handleSessaoDetalhe(btn) {
  if (!btn) return;
  const url = btn.dataset.url;
  btn.disabled = true;
  try {
    const resp = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
    const data = await resp.json();
    if (data.status === 'ok') {
      fireEvent('user:sessionDetailLoaded', { sessao: data.sessao });
      // Render básico em modal se existir
      const modalEl = document.getElementById('sessionDetailsModal');
      const container = document.getElementById('session-details-content');
      if (modalEl && container) {
        container.innerHTML = `
          <dl class="row mb-0">
            <dt class="col-sm-3">Usuário</dt><dd class="col-sm-9">${data.sessao.user}</dd>
            <dt class="col-sm-3">IP</dt><dd class="col-sm-9">${data.sessao.ip_address||'-'}</dd>
            <dt class="col-sm-3">User Agent</dt><dd class="col-sm-9"><small>${data.sessao.user_agent||'-'}</small></dd>
            <dt class="col-sm-3">Criada</dt><dd class="col-sm-9">${data.sessao.criada_em}</dd>
            <dt class="col-sm-3">Última Atividade</dt><dd class="col-sm-9">${data.sessao.ultima_atividade}</dd>
            <dt class="col-sm-3">Ativa</dt><dd class="col-sm-9">${data.sessao.ativa ? 'Sim' : 'Não'}</dd>
          </dl>`;
        const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
        bsModal.show();
      }
    } else {
      alert(data.detail || 'Erro ao obter detalhes');
    }
  } catch (err) {
    alert(err.message || 'Falha ao obter detalhes');
  } finally { btn.disabled = false; }
}

async function handleEncerrarTodas(btn) {
  if (!btn) return;
  const url = btn.dataset.url;
  btn.disabled = true;
  try {
    const data = await apiPost(url);
    if (data.status === 'ok') {
      fireEvent('user:sessionsTerminatedAll', { encerradas: data.encerradas });
      // Remover sessões do próprio usuário sem reload
      document.querySelectorAll('#sessions-table tbody tr').forEach(tr => {
        const terminateBtn = tr.querySelector('[data-action="encerrar-sessao"]');
        if (terminateBtn && terminateBtn.dataset.url.includes('/sessoes/')) {
          tr.remove();
        }
      });
    } else {
      alert(data.detail || 'Erro ao encerrar sessões');
    }
  } catch (err) {
    alert(err.message || 'Falha ao encerrar sessões');
  } finally { btn.disabled = false; }
}

export function initUserManagementActions() {
  if (initialized) return; // idempotente
  initialized = true;
  document.querySelectorAll('[data-action="toggle-2fa"]').forEach(btn => {
    btn.addEventListener('click', e => { e.preventDefault(); handleToggleTwoFactor(btn); });
  });
  document.querySelectorAll('[data-action="encerrar-sessao"]').forEach(btn => {
    btn.addEventListener('click', e => { e.preventDefault(); handleEncerrarSessao(btn); });
  });
  document.querySelectorAll('[data-action="detalhe-sessao"]').forEach(btn => {
    btn.addEventListener('click', e => { e.preventDefault(); handleSessaoDetalhe(btn); });
  });
  const encerrarTodasBtn = document.querySelector('[data-action="encerrar-todas-sessoes"]');
  if (encerrarTodasBtn) {
    encerrarTodasBtn.addEventListener('click', e => { e.preventDefault(); if (confirm('Encerrar todas as suas sessões ativas?')) handleEncerrarTodas(encerrarTodasBtn); });
  }
  fireEvent('user:actionsInit');
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initUserManagementActions);
} else {
  initUserManagementActions();
}
