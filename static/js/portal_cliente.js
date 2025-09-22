/**
 * Portal Cliente - JavaScript Principal
 * Funcionalidades interativas para o portal do cliente
 */

// Configurações globais
const PortalCliente = {
    config: {
        animationDuration: 300,
        toastDuration: 5000,
        loadingDelay: 200
    },
    
    // Cache de elementos DOM
    elements: {},
    
    // Estado da aplicação
    state: {
        servicoSelecionado: null,
        slotSelecionado: null,
        loading: false
    }
};

/**
 * Inicialização do portal
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Portal Cliente - Inicializando...');
    
    PortalCliente.init();
    PortalCliente.bindEvents();
    PortalCliente.initComponents();
    
    console.log('✅ Portal Cliente - Carregado com sucesso!');
});

/**
 * Inicialização principal
 */
PortalCliente.init = function() {
    // Cache de elementos frequentemente utilizados
    this.elements = {
        body: document.body,
        loadingSpinner: document.querySelector('.loading-spinner'),
        toastContainer: this.createToastContainer()
    };
    
    // Configurar CSRF token para requests AJAX
    this.setupCSRF();
    
    // Configurar interceptadores de requests
    this.setupRequestInterceptors();
};

/**
 * Vincular eventos globais
 */
PortalCliente.bindEvents = function() {
    // Tooltips
    this.initTooltips();
    
    // Popovers
    this.initPopovers();
    
    // Smooth scroll para anchors
    this.initSmoothScroll();
    
    // Lazy loading de imagens
    this.initLazyLoading();
    
    // Auto-submit de formulários de filtro
    this.initAutoFilters();
};

/**
 * Inicializar componentes específicos
 */
PortalCliente.initComponents = function() {
    // Agendamentos
    if (document.querySelector('#agendamentoForm')) {
        this.initAgendamentoForm();
    }
    
    // Galeria de fotos
    if (document.querySelector('.foto-thumbnail')) {
        this.initGaleria();
    }
    
    // Dashboard
    if (document.querySelector('.stats-card')) {
        this.initDashboard();
    }
};

/**
 * Configurar CSRF para requests AJAX
 */
PortalCliente.setupCSRF = function() {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfToken) {
        // Configurar para fetch API
        window.csrfToken = csrfToken.value;
        
        // Configurar para XMLHttpRequest
        const originalOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function() {
            originalOpen.apply(this, arguments);
            if (arguments[0].toUpperCase() !== 'GET') {
                this.setRequestHeader('X-CSRFToken', window.csrfToken);
            }
        };
    }
};

/**
 * Configurar interceptadores de requests
 */
PortalCliente.setupRequestInterceptors = function() {
    // Interceptar fetch para adicionar loading e tratamento de erro
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        PortalCliente.showLoading();
        
        return originalFetch.apply(this, args)
            .then(response => {
                PortalCliente.hideLoading();
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                return response;
            })
            .catch(error => {
                PortalCliente.hideLoading();
                PortalCliente.showToast('Erro na requisição: ' + error.message, 'error');
                throw error;
            });
    };
};

/**
 * Inicializar tooltips
 */
PortalCliente.initTooltips = function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            trigger: 'hover focus'
        });
    });
};

/**
 * Inicializar popovers
 */
PortalCliente.initPopovers = function() {
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
};

/**
 * Smooth scroll para links âncora
 */
PortalCliente.initSmoothScroll = function() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
};

/**
 * Lazy loading de imagens
 */
PortalCliente.initLazyLoading = function() {
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.classList.add('loaded');
                        imageObserver.unobserve(img);
                    }
                }
            });
        });
        
        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }
};

/**
 * Auto-submit de formulários de filtro
 */
PortalCliente.initAutoFilters = function() {
    document.querySelectorAll('.auto-filter').forEach(select => {
        select.addEventListener('change', function() {
            this.form.submit();
        });
    });
};

/**
 * Inicializar formulário de agendamento
 */
PortalCliente.initAgendamentoForm = function() {
    console.log('📅 Inicializando formulário de agendamento...');
    
    // Seleção de serviço (campo definitivo servico_id)
    const radios = document.querySelectorAll('input[name="servico_id"]');
    radios.forEach(radio => {
        radio.addEventListener('change', function() {
            PortalCliente.selecionarServico(this.value);
        });
    });
    
    // Validação do formulário
    document.getElementById('agendamentoForm').addEventListener('submit', function(e) {
        if (!PortalCliente.validarAgendamento()) {
            e.preventDefault();
        }
    });
};

/**
 * Selecionar serviço (mantém nomenclatura de função por compat)
 */
PortalCliente.selecionarServico = function(servicoId) {
    this.state.servicoSelecionado = servicoId;
    
    // Mostrar seção de filtros
    const filtrosSection = document.getElementById('filtrosSection');
    if (filtrosSection) {
        filtrosSection.style.display = 'block';
        filtrosSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    // Limpar seleções anteriores
    this.limparSelecaoSlot();
    
    // Buscar slots automaticamente
    setTimeout(() => {
        this.buscarSlots();
    }, 500);
};

// Alias removido: usar somente selecionarServico

/**
 * Buscar slots disponíveis
 */
PortalCliente.buscarSlots = function() {
    if (!this.state.servicoSelecionado) {
        this.showToast('Selecione um serviço primeiro', 'warning');
        return;
    }
    
    const dataInicio = document.getElementById('dataInicio')?.value;
    const dataFim = document.getElementById('dataFim')?.value;
    const profissionalId = document.getElementById('profissionalFiltro')?.value;
    
    // Mostrar loading
    const slotsSection = document.getElementById('slotsSection');
    if (slotsSection) {
        slotsSection.style.display = 'block';
        slotsSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    this.showSlotLoading();
    
    // Construir parâmetros
    const params = new URLSearchParams();
    if (dataInicio) params.append('data_inicio', dataInicio);
    if (dataFim) params.append('data_fim', dataFim);
    if (profissionalId) params.append('profissional_id', profissionalId);
    params.append('servico_id', this.state.servicoSelecionado);
    
    // Fazer requisição
    fetch(`/portal_cliente/portal/ajax/slots-disponiveis/?${params.toString()}`)
        .then(response => response.json())
        .then(data => {
            this.hideSlotLoading();
            
            if (data.success) {
                this.renderSlots(data.slots);
            } else {
                this.showSlotsError(data.error);
            }
        })
        .catch(error => {
            this.hideSlotLoading();
            this.showSlotsError('Erro ao buscar horários: ' + error.message);
        });
};

/**
 * Renderizar slots disponíveis
 */
PortalCliente.renderSlots = function(slots) {
    const container = document.getElementById('slotsContainer');
    if (!container) return;
    
    if (slots.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4">
                <i class="fas fa-calendar-times fa-3x text-muted mb-3"></i>
                <h5 class="text-muted">Nenhum horário disponível</h5>
                <p class="text-muted">Tente ajustar os filtros ou escolher outro período.</p>
                <button type="button" class="btn btn-outline-primary" onclick="PortalCliente.resetFiltros()">
                    <i class="fas fa-refresh me-2"></i>Limpar Filtros
                </button>
            </div>
        `;
        return;
    }
    
    // Agrupar slots por data
    const slotsPorData = this.groupSlotsByDate(slots);
    
    let html = '';
    Object.keys(slotsPorData).forEach(data => {
        html += `<h6 class="mt-4 mb-3"><i class="fas fa-calendar me-2"></i>${data}</h6>`;
        html += '<div class="row g-2">';
        
        slotsPorData[data].forEach(slot => {
            const horario = slot.horario_display.split(' às ')[1];
            html += `
                <div class="col-md-3 col-lg-2 mb-2">
                    <div class="card slot-card" data-slot-id="${slot.id}" onclick="PortalCliente.selecionarSlot(${slot.id}, this)">
                        <div class="card-body p-2 text-center">
                            <div class="fw-bold">${horario}</div>
                            <small class="text-muted">${slot.profissional}</small>
                            <div class="badge bg-success badge-sm mt-1">
                                ${slot.capacidade_disponivel} vaga${slot.capacidade_disponivel !== 1 ? 's' : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
    });
    
    container.innerHTML = html;
    this.animateSlots();
};

/**
 * Agrupar slots por data
 */
PortalCliente.groupSlotsByDate = function(slots) {
    const groups = {};
    
    slots.forEach(slot => {
        const data = slot.horario_display.split(' às ')[0];
        if (!groups[data]) groups[data] = [];
        groups[data].push(slot);
    });
    
    return groups;
};

/**
 * Selecionar slot
 */
PortalCliente.selecionarSlot = function(slotId, elemento) {
    // Remover seleção anterior
    document.querySelectorAll('.slot-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    // Selecionar novo slot
    elemento.classList.add('selected');
    this.state.slotSelecionado = slotId;
    
    // Atualizar campo hidden
    const hiddenInput = document.getElementById('slotSelecionado');
    if (hiddenInput) {
        hiddenInput.value = slotId;
    }
    
    // Mostrar próximas seções
    this.mostrarProximasSecoes();
    
    // Feedback visual
    this.showToast('Horário selecionado com sucesso!', 'success');
};

/**
 * Mostrar próximas seções do formulário
 */
PortalCliente.mostrarProximasSecoes = function() {
    const observacoesSection = document.getElementById('observacoesSection');
    const botoesSection = document.getElementById('botoesSection');
    
    if (observacoesSection) {
        observacoesSection.style.display = 'block';
        setTimeout(() => {
            observacoesSection.scrollIntoView({ behavior: 'smooth' });
        }, 100);
    }
    
    if (botoesSection) {
        botoesSection.style.display = 'block';
    }
};

/**
 * Validar formulário de agendamento
 */
PortalCliente.validarAgendamento = function() {
    if (!this.state.servicoSelecionado) {
        this.showToast('Selecione um serviço', 'warning');
        return false;
    }
    
    if (!this.state.slotSelecionado) {
        this.showToast('Selecione um horário', 'warning');
        return false;
    }
    
    return true;
};

/**
 * Limpar seleção de slot
 */
PortalCliente.limparSelecaoSlot = function() {
    this.state.slotSelecionado = null;
    
    const sections = ['slotsSection', 'observacoesSection', 'botoesSection'];
    sections.forEach(sectionId => {
        const section = document.getElementById(sectionId);
        if (section) {
            section.style.display = 'none';
        }
    });
    
    const hiddenInput = document.getElementById('slotSelecionado');
    if (hiddenInput) {
        hiddenInput.value = '';
    }
};

/**
 * Inicializar galeria de fotos
 */
PortalCliente.initGaleria = function() {
    console.log('🖼️ Inicializando galeria de fotos...');
    
    // Lightbox para fotos
    document.querySelectorAll('.foto-thumbnail').forEach(img => {
        img.addEventListener('click', function() {
            PortalCliente.abrirLightbox(this.src, this.alt);
        });
    });
};

/**
 * Abrir lightbox para foto
 */
PortalCliente.abrirLightbox = function(src, alt) {
    // Criar modal dinâmico se não existir
    let modal = document.getElementById('lightboxModal');
    if (!modal) {
        modal = this.createLightboxModal();
    }
    
    const img = modal.querySelector('#lightboxImage');
    const title = modal.querySelector('#lightboxTitle');
    
    if (img) img.src = src;
    if (title) title.textContent = alt;
    
    const bootstrapModal = new bootstrap.Modal(modal);
    bootstrapModal.show();
};

/**
 * Criar modal de lightbox
 */
PortalCliente.createLightboxModal = function() {
    const modalHTML = `
        <div class="modal fade" id="lightboxModal" tabindex="-1">
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="lightboxTitle">Visualizar Foto</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <img id="lightboxImage" src="" class="img-fluid rounded" alt="Foto ampliada">
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    return document.getElementById('lightboxModal');
};

/**
 * Inicializar dashboard
 */
PortalCliente.initDashboard = function() {
    console.log('📊 Inicializando dashboard...');
    
    // Animar entrada dos cards
    this.animateStatsCards();
    
    // Auto-refresh de dados (opcional)
    if (window.location.pathname.includes('dashboard')) {
        // Refresh a cada 5 minutos
        setTimeout(() => {
            this.refreshDashboardData();
        }, 300000);
    }
};

/**
 * Animar cards de estatísticas
 */
PortalCliente.animateStatsCards = function() {
    const cards = document.querySelectorAll('.stats-card');
    cards.forEach((card, index) => {
        setTimeout(() => {
            card.classList.add('fade-in-up');
        }, index * 100);
    });
};

/**
 * Animar entrada dos slots
 */
PortalCliente.animateSlots = function() {
    const slots = document.querySelectorAll('.slot-card');
    slots.forEach((slot, index) => {
        setTimeout(() => {
            slot.style.opacity = '0';
            slot.style.transform = 'translateY(20px)';
            slot.style.transition = 'all 0.3s ease';
            
            setTimeout(() => {
                slot.style.opacity = '1';
                slot.style.transform = 'translateY(0)';
            }, 50);
        }, index * 50);
    });
};

/**
 * Mostrar loading nos slots
 */
PortalCliente.showSlotLoading = function() {
    const spinner = document.querySelector('.loading-spinner');
    if (spinner) {
        spinner.style.display = 'block';
    }
    
    const container = document.getElementById('slotsContainer');
    if (container) {
        container.innerHTML = '';
    }
};

/**
 * Esconder loading nos slots
 */
PortalCliente.hideSlotLoading = function() {
    const spinner = document.querySelector('.loading-spinner');
    if (spinner) {
        spinner.style.display = 'none';
    }
};

/**
 * Mostrar erro nos slots
 */
PortalCliente.showSlotsError = function(message) {
    const container = document.getElementById('slotsContainer');
    if (container) {
        container.innerHTML = `
            <div class="alert alert-danger text-center">
                <i class="fas fa-exclamation-triangle me-2"></i>
                ${message}
                <br><br>
                <button type="button" class="btn btn-outline-danger" onclick="PortalCliente.buscarSlots()">
                    <i class="fas fa-refresh me-2"></i>Tentar Novamente
                </button>
            </div>
        `;
    }
};

/**
 * Mostrar loading global
 */
PortalCliente.showLoading = function() {
    if (this.state.loading) return;
    this.state.loading = true;
    
    // Adicionar cursor de loading
    document.body.style.cursor = 'wait';
    
    // Mostrar spinner se disponível
    if (this.elements.loadingSpinner) {
        this.elements.loadingSpinner.style.display = 'block';
    }
};

/**
 * Esconder loading global
 */
PortalCliente.hideLoading = function() {
    this.state.loading = false;
    
    // Remover cursor de loading
    document.body.style.cursor = 'default';
    
    // Esconder spinner
    if (this.elements.loadingSpinner) {
        this.elements.loadingSpinner.style.display = 'none';
    }
};

/**
 * Criar container de toasts
 */
PortalCliente.createToastContainer = function() {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }
    return container;
};

/**
 * Mostrar toast de notificação
 */
PortalCliente.showToast = function(message, type = 'info') {
    const toastId = 'toast-' + Date.now();
    const iconMap = {
        success: 'fa-check-circle',
        error: 'fa-times-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    const bgMap = {
        success: 'bg-success',
        error: 'bg-danger',
        warning: 'bg-warning',
        info: 'bg-primary'
    };
    
    const toastHTML = `
        <div id="${toastId}" class="toast" role="alert">
            <div class="toast-header ${bgMap[type]} text-white">
                <i class="fas ${iconMap[type]} me-2"></i>
                <strong class="me-auto">Portal Cliente</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    this.elements.toastContainer.insertAdjacentHTML('beforeend', toastHTML);
    
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: this.config.toastDuration
    });
    
    toast.show();
    
    // Remover do DOM após esconder
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
};

/**
 * Resetar filtros de busca
 */
PortalCliente.resetFiltros = function() {
    const dataInicio = document.getElementById('dataInicio');
    const dataFim = document.getElementById('dataFim');
    const profissionalFiltro = document.getElementById('profissionalFiltro');
    
    if (dataInicio) dataInicio.value = '';
    if (dataFim) dataFim.value = '';
    if (profissionalFiltro) profissionalFiltro.value = '';
    
    this.buscarSlots();
};

/**
 * Refresh de dados do dashboard
 */
PortalCliente.refreshDashboardData = function() {
    // Implementar refresh automático se necessário
    console.log('🔄 Refreshing dashboard data...');
};

/**
 * Utilitários de formatação
 */
PortalCliente.utils = {
    formatDate: function(date) {
        return new Date(date).toLocaleDateString('pt-BR');
    },
    
    formatTime: function(time) {
        return new Date(time).toLocaleTimeString('pt-BR', {
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    formatCurrency: function(value) {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        }).format(value);
    }
};

// Expor para escopo global
window.PortalCliente = PortalCliente;
