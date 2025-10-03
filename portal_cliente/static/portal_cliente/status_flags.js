/* JS utilitário para consumir endpoint de status e habilitar/desabilitar botões.
   Uso: portalClienteStatus.init({agendamentoId: 123, urls: {status: '/portal-cliente/portal/ajax/agendamento/123/status/', checkin: '...', finalizar: '...', avaliar: '...'}})
*/
const portalClienteStatus = (function () {
    async function fetchStatus(url) {
        const r = await fetch(url, { headers: { 'Accept': 'application/json' } })
        if (!r.ok) { return null }
        const data = await r.json();
        return data.status || null;
    }
    function toggle(btnId, enabled) {
        const el = document.getElementById(btnId);
        if (!el) return;
        el.disabled = !enabled;
        el.classList.toggle('disabled', !enabled);
    }
    async function refresh(cfg) {
        const st = await fetchStatus(cfg.urls.status);
        if (!st) return;
        toggle(cfg.ids.checkin, st.pode_checkin);
        toggle(cfg.ids.finalizar, st.pode_finalizar);
        toggle(cfg.ids.avaliar, st.pode_avaliar);
    }
    function init(cfg) {
        if (!cfg || !cfg.urls || !cfg.ids) return;
        refresh(cfg);
        if (cfg.autoIntervalMs) {
            setInterval(() => refresh(cfg), cfg.autoIntervalMs);
        }
    }
    return { init, refresh };
})();
