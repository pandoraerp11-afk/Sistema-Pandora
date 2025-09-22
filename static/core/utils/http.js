// Utilidades HTTP centrais (ES Module)
// Responsável por: CSRF, fetch seguro, tratamento básico de erros e emissão de eventos.

function getCsrfToken() {
  const el = document.querySelector('[name=csrfmiddlewaretoken]');
  return el ? el.value : '';
}

export async function apiRequest(url, { method = 'GET', body = null, headers = {}, timeout = 15000 } = {}) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  const finalHeaders = {
    'X-Requested-With': 'XMLHttpRequest',
    'X-CSRFToken': getCsrfToken(),
    ...headers,
  };
  if (body && !(body instanceof FormData) && !finalHeaders['Content-Type']) {
    finalHeaders['Content-Type'] = 'application/json';
  }
  try {
    const response = await fetch(url, {
      method,
      body: body && !(body instanceof FormData) ? JSON.stringify(body) : body,
      headers: finalHeaders,
      signal: controller.signal,
    });
    clearTimeout(id);
    const ct = response.headers.get('Content-Type') || '';
    let data = null;
    if (ct.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }
    if (!response.ok) {
      const detail = data && data.detail ? data.detail : response.statusText;
      throw new Error(detail || 'Erro na requisição');
    }
    return data;
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('Tempo de requisição excedido');
    }
    throw err;
  }
}

export async function apiPost(url, body = null, opts = {}) {
  return apiRequest(url, { method: 'POST', body, ...opts });
}

export function fireEvent(name, detail = {}) {
  document.dispatchEvent(new CustomEvent(name, { detail, bubbles: true }));
}
