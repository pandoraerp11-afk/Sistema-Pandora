// AI Auditor - JavaScript Personalizado

// Namespace para o AI Auditor
window.AIAuditor = window.AIAuditor || {};

(function($) {
    'use strict';

    // Configurações globais
    AIAuditor.config = {
        apiBaseUrl: '/ai-auditor/api/',
        refreshInterval: 30000, // 30 segundos
        animationDuration: 300
    };

    // Utilitários
    AIAuditor.utils = {
        // Formatar números grandes
        formatNumber: function(num) {
            if (num >= 1000000) {
                return (num / 1000000).toFixed(1) + 'M';
            } else if (num >= 1000) {
                return (num / 1000).toFixed(1) + 'K';
            }
            return num.toString();
        },

        // Mostrar notificação toast
        showToast: function(message, type = 'info') {
            const toastHtml = `
                <div class="toast toast-${type}" role="alert" aria-live="assertive" aria-atomic="true">
                    <div class="toast-header">
                        <i class="fas fa-robot mr-2"></i>
                        <strong class="mr-auto">Agente de IA</strong>
                        <button type="button" class="ml-2 mb-1 close" data-dismiss="toast" aria-label="Close">
                            <span aria-hidden="true">&times;</span>
                        </button>
                    </div>
                    <div class="toast-body">
                        ${message}
                    </div>
                </div>
            `;
            
            // Adicionar toast container se não existir
            if (!$('#toast-container').length) {
                $('body').append('<div id="toast-container" class="position-fixed" style="top: 20px; right: 20px; z-index: 9999;"></div>');
            }
            
            const $toast = $(toastHtml);
            $('#toast-container').append($toast);
            $toast.toast({ delay: 5000 }).toast('show');
            
            // Remover toast após fechar
            $toast.on('hidden.bs.toast', function() {
                $(this).remove();
            });
        },

        // Confirmar ação
        confirmAction: function(message, callback) {
            if (confirm(message)) {
                callback();
            }
        },

        // Debounce function
        debounce: function(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        }
    };

    // Dashboard
    AIAuditor.dashboard = {
        init: function() {
            this.initCharts();
            this.initCounters();
            this.initRefresh();
            this.bindEvents();
        },

        initCharts: function() {
            // Inicializar gráficos se Chart.js estiver disponível
            if (typeof Chart !== 'undefined') {
                this.initSeverityChart();
                this.initTrendChart();
            }
        },

        initSeverityChart: function() {
            const ctx = document.getElementById('severityChart');
            if (!ctx) return;

            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Críticos', 'Altos', 'Médios', 'Baixos'],
                    datasets: [{
                        data: [
                            parseInt($('#critical-count').text()) || 0,
                            parseInt($('#high-count').text()) || 0,
                            parseInt($('#medium-count').text()) || 0,
                            parseInt($('#low-count').text()) || 0
                        ],
                        backgroundColor: [
                            '#dc3545',
                            '#fd7e14',
                            '#ffc107',
                            '#28a745'
                        ],
                        borderWidth: 0,
                        hoverOffset: 10
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 20,
                                usePointStyle: true
                            }
                        }
                    },
                    animation: {
                        animateRotate: true,
                        duration: 1000
                    }
                }
            });
        },

        initTrendChart: function() {
            const ctx = document.getElementById('trendChart');
            if (!ctx) return;

            // Dados simulados - em produção, buscar via API
            const data = {
                labels: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun'],
                datasets: [{
                    label: 'Problemas Encontrados',
                    data: [12, 19, 8, 15, 10, 7],
                    borderColor: '#4f46e5',
                    backgroundColor: 'rgba(79, 70, 229, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            };

            new Chart(ctx, {
                type: 'line',
                data: data,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0,0,0,0.1)'
                            }
                        },
                        x: {
                            grid: {
                                display: false
                            }
                        }
                    }
                }
            });
        },

        initCounters: function() {
            // Animar contadores
            $('.metric-number').each(function() {
                const $this = $(this);
                const target = parseInt($this.text());
                let current = 0;
                const increment = target / 50;
                
                const timer = setInterval(function() {
                    current += increment;
                    if (current >= target) {
                        current = target;
                        clearInterval(timer);
                    }
                    $this.text(Math.floor(current));
                }, 20);
            });
        },

        initRefresh: function() {
            // Auto-refresh do dashboard
            setInterval(() => {
                this.refreshData();
            }, AIAuditor.config.refreshInterval);
        },

        refreshData: function() {
            // Implementar refresh via AJAX
            console.log('Refreshing dashboard data...');
        },

        bindEvents: function() {
            // Botão de executar auditoria
            $(document).on('click', '[data-action="run-audit"]', function(e) {
                e.preventDefault();
                AIAuditor.audit.run();
            });

            // Botão de gerar testes
            $(document).on('click', '[data-action="generate-tests"]', function(e) {
                e.preventDefault();
                AIAuditor.tests.generate();
            });
        }
    };

    // Auditoria
    AIAuditor.audit = {
        run: function() {
            AIAuditor.utils.confirmAction(
                'Deseja executar uma auditoria completa do sistema? Isso pode levar alguns minutos.',
                () => {
                    this.startAudit();
                }
            );
        },

        startAudit: function() {
            // Mostrar loading
            this.showProgress();
            
            // Simular execução (implementar AJAX real)
            setTimeout(() => {
                this.hideProgress();
                AIAuditor.utils.showToast('Auditoria iniciada com sucesso!', 'success');
            }, 2000);
        },

        showProgress: function() {
            const progressHtml = `
                <div id="audit-progress" class="modal fade" tabindex="-1" role="dialog">
                    <div class="modal-dialog modal-dialog-centered" role="document">
                        <div class="modal-content">
                            <div class="modal-body text-center p-4">
                                <div class="spinner-border text-primary mb-3" role="status">
                                    <span class="sr-only">Carregando...</span>
                                </div>
                                <h5>Executando Auditoria</h5>
                                <p class="text-muted">Analisando código-fonte do sistema...</p>
                                <div class="progress">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                         role="progressbar" style="width: 0%"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            $('body').append(progressHtml);
            $('#audit-progress').modal({ backdrop: 'static', keyboard: false }).modal('show');
            
            // Simular progresso
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += Math.random() * 10;
                if (progress >= 100) {
                    progress = 100;
                    clearInterval(progressInterval);
                }
                $('#audit-progress .progress-bar').css('width', progress + '%');
            }, 200);
        },

        hideProgress: function() {
            $('#audit-progress').modal('hide').on('hidden.bs.modal', function() {
                $(this).remove();
            });
        }
    };

    // Testes
    AIAuditor.tests = {
        generate: function() {
            AIAuditor.utils.confirmAction(
                'Deseja gerar testes unitários automaticamente?',
                () => {
                    AIAuditor.utils.showToast('Geração de testes iniciada!', 'info');
                }
            );
        }
    };

    // Problemas de Código
    AIAuditor.issues = {
        init: function() {
            this.bindEvents();
            this.initFilters();
        },

        bindEvents: function() {
            // Aplicar correção
            $(document).on('click', '[data-action="fix-issue"]', function(e) {
                e.preventDefault();
                const issueId = $(this).data('issue-id');
                AIAuditor.issues.fix(issueId);
            });

            // Ignorar problema
            $(document).on('click', '[data-action="ignore-issue"]', function(e) {
                e.preventDefault();
                const issueId = $(this).data('issue-id');
                AIAuditor.issues.ignore(issueId);
            });

            // Ver detalhes
            $(document).on('click', '[data-action="view-issue"]', function(e) {
                e.preventDefault();
                const issueId = $(this).data('issue-id');
                AIAuditor.issues.showDetails(issueId);
            });
        },

        initFilters: function() {
            // Filtros em tempo real
            $('#severity-filter, #status-filter, #type-filter').on('change', 
                AIAuditor.utils.debounce(() => {
                    this.applyFilters();
                }, 300)
            );
        },

        applyFilters: function() {
            const severity = $('#severity-filter').val();
            const status = $('#status-filter').val();
            const type = $('#type-filter').val();
            
            // Implementar filtros via AJAX ou client-side
            console.log('Applying filters:', { severity, status, type });
        },

        fix: function(issueId) {
            AIAuditor.utils.confirmAction(
                'Deseja aplicar a correção automática para este problema?',
                () => {
                    // Implementar correção via AJAX
                    AIAuditor.utils.showToast(`Correção aplicada para o problema #${issueId}`, 'success');
                }
            );
        },

        ignore: function(issueId) {
            AIAuditor.utils.confirmAction(
                'Deseja marcar este problema como ignorado?',
                () => {
                    // Implementar via AJAX
                    AIAuditor.utils.showToast(`Problema #${issueId} marcado como ignorado`, 'warning');
                }
            );
        },

        showDetails: function(issueId) {
            // Implementar modal com detalhes do problema
            console.log('Showing details for issue:', issueId);
        }
    };

    // Configurações
    AIAuditor.settings = {
        init: function() {
            this.bindEvents();
            this.initValidation();
        },

        bindEvents: function() {
            // Reset para padrões
            $(document).on('click', '[data-action="reset-defaults"]', function(e) {
                e.preventDefault();
                AIAuditor.settings.resetDefaults();
            });

            // Validação de cron
            $('#analysis_schedule').on('blur', function() {
                AIAuditor.settings.validateCron($(this).val());
            });
        },

        initValidation: function() {
            // Validação em tempo real
            $('form').on('submit', function(e) {
                if (!AIAuditor.settings.validateForm()) {
                    e.preventDefault();
                }
            });
        },

        validateForm: function() {
            let isValid = true;
            
            // Validar formato cron
            const cronValue = $('#analysis_schedule').val().trim();
            if (cronValue && !this.isValidCron(cronValue)) {
                AIAuditor.utils.showToast('Formato de cron inválido', 'error');
                isValid = false;
            }
            
            return isValid;
        },

        validateCron: function(cron) {
            if (cron && !this.isValidCron(cron)) {
                AIAuditor.utils.showToast('Formato de cron inválido. Use: "segundos minutos horas dia mês dia_da_semana"', 'warning');
            }
        },

        isValidCron: function(cron) {
            const parts = cron.split(' ');
            return parts.length === 6;
        },

        resetDefaults: function() {
            AIAuditor.utils.confirmAction(
                'Deseja restaurar todas as configurações para os valores padrão?',
                () => {
                    // Definir valores padrão
                    $('#auto_fix_enabled').prop('checked', false);
                    $('#auto_test_generation').prop('checked', true);
                    $('#email_notifications').prop('checked', true);
                    $('#critical_threshold').val(10);
                    $('#analysis_schedule').val('');
                    $('#excluded_apps').val('');
                    
                    AIAuditor.utils.showToast('Configurações restauradas para os valores padrão', 'info');
                }
            );
        }
    };

    // Inicialização
    $(document).ready(function() {
        // Inicializar tooltips
        $('[data-toggle="tooltip"]').tooltip();
        
        // Inicializar popovers
        $('[data-toggle="popover"]').popover();
        
        // Inicializar módulos baseado na página atual
        const currentPage = $('body').data('page');
        
        switch (currentPage) {
            case 'dashboard':
                AIAuditor.dashboard.init();
                break;
            case 'issues':
                AIAuditor.issues.init();
                break;
            case 'settings':
                AIAuditor.settings.init();
                break;
        }
        
        // Animações de entrada
        $('.ai-auditor-card').each(function(index) {
            $(this).css('animation-delay', (index * 0.1) + 's');
        });
        
        // Smooth scroll para âncoras
        $('a[href^="#"]').on('click', function(e) {
            e.preventDefault();
            const target = $(this.getAttribute('href'));
            if (target.length) {
                $('html, body').animate({
                    scrollTop: target.offset().top - 100
                }, 500);
            }
        });
    });

})(jQuery);

// Funções globais para compatibilidade
function runAudit() {
    AIAuditor.audit.run();
}

function generateTests() {
    AIAuditor.tests.generate();
}

function fixIssue(issueId) {
    AIAuditor.issues.fix(issueId);
}

function ignoreIssue(issueId) {
    AIAuditor.issues.ignore(issueId);
}

function showIssueDetails(issueId) {
    AIAuditor.issues.showDetails(issueId);
}

function resetToDefaults() {
    AIAuditor.settings.resetDefaults();
}

function showError(errorMessage) {
    $('#errorContent').text(errorMessage);
    $('#errorModal').modal('show');
}

function exportReport(sessionId) {
    AIAuditor.utils.showToast('Exportando relatório...', 'info');
    // Implementar exportação
}

function fixIssues(sessionId) {
    AIAuditor.utils.confirmAction(
        'Deseja aplicar todas as correções automáticas disponíveis para esta sessão?',
        () => {
            AIAuditor.utils.showToast('Aplicando correções...', 'info');
            // Implementar correções em lote
        }
    );
}

