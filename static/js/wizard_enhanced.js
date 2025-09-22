/*!
 * Wizard Enhanced - Sistema de Formulário com Máscaras e Validações
 * Versão Otimizada para Bootstrap 5 + Django
 */

(function ($) {
    'use strict';

    // Configuração global do wizard
    window.wizardConfig = {
        dateFormat: 'dd/mm/yyyy',
        phonePattern: '(99) 99999-9999',
        cepPattern: '99999-999',
        cpfPattern: '999.999.999-99',
        cnpjPattern: '99.999.999/9999-99',
        cnaePattern: '9999-9/99'
    };

    // Inicialização do wizard quando o DOM estiver pronto
    $(document).ready(function () {
        initializeWizardMasks();
        initializeDatePickers();
        initializePersonTypeToggle();
        initializeCepLookup();
        initializeFormValidation();
        initializeFieldSizing();
        initializeWizardNavigation();
        initializeTooltips();
        initializeWizardAdminsStep();
        initializeWizardAddressesStep();
        initializeWizardContactsStep();
        initializeWizardSocialsStep();
        initializeWizardConfigurationStep();
        // Só tenta inicializar preview se existir algum indicativo de wizard na página
        const isWizardPage = $('.wizard-form, [data-wizard="true"], #wizard-container').length > 0;
        if (isWizardPage) {
            try {
                initializeWizardPreview(); // Nova funcionalidade
            } catch (e) {
                console.error('❌ Erro ao inicializar preview. Prosseguindo sem preview para não bloquear navegação.', e);
                window.updateWizardPreview = function () { }; // no-op
            }
        } else if (window?.wizardConfig?.debug) {
            console.debug('Wizard preview ignorado: página sem elementos de wizard.');
        }
    });

    /**
     * Inicializa todas as máscaras de input
     */
    function initializeWizardMasks() {
        console.log('Inicializando máscaras do wizard...');

        // Máscara de telefone
        $('.phone-mask').inputmask({
            mask: '(99) 99999-9999',
            placeholder: '(99) 99999-9999',
            clearIncomplete: true,
            showMaskOnHover: false,
            showMaskOnFocus: true
        });

        // Máscara de CEP
        $('.cep-mask').inputmask({
            mask: '99999-999',
            placeholder: '99999-999',
            clearIncomplete: true,
            showMaskOnHover: false,
            showMaskOnFocus: true
        });

        // Máscara de CPF
        $('.cpf-mask').inputmask({
            mask: '999.999.999-99',
            placeholder: '999.999.999-99',
            clearIncomplete: true,
            showMaskOnHover: false,
            showMaskOnFocus: true
        });

        // Máscara de CNPJ
        $('.cnpj-mask').inputmask({
            mask: '99.999.999/9999-99',
            placeholder: '99.999.999/9999-99',
            clearIncomplete: true,
            showMaskOnHover: false,
            showMaskOnFocus: true
        });

        // Máscara de CNAE
        $('.cnae-mask').inputmask({
            mask: '9999-9/99',
            placeholder: '9999-9/99',
            clearIncomplete: true,
            showMaskOnHover: false,
            showMaskOnFocus: true
        });

        // Máscara de data
        $('.date-mask').inputmask({
            mask: '99/99/9999',
            placeholder: 'dd/mm/aaaa',
            clearIncomplete: true,
            showMaskOnHover: false,
            showMaskOnFocus: true
        });
    }

    /**
     * Inicializa o Step 2 (Endereços): endereços adicionais via modal + JSON oculto
     */
    function initializeWizardAddressesStep() {
        const section = document.getElementById('wizard-addresses-section');
        const jsonField = document.querySelector('.wizard-additional-addresses-json') || document.querySelector('input[name$="-additional_addresses_json"]');
        const tableBody = document.querySelector('#tblAdditionalAddresses tbody');
        const addBtn = document.getElementById('btnAddAddress');
        const modalEl = document.getElementById('modalAddAddress');
        if (!section || !jsonField || !tableBody || !addBtn || !modalEl) {
            return; // não estamos no step 2
        }

        const maxItems = parseInt(section.getAttribute('data-max-additional-addresses') || '50', 10);
        const bsModal = window.bootstrap ? new bootstrap.Modal(modalEl, { backdrop: true, keyboard: true, focus: true }) : null;

        const fld = {
            tipo: document.getElementById('addrTipo'),
            cep: document.getElementById('addrCep'),
            logradouro: document.getElementById('addrLogradouro'),
            numero: document.getElementById('addrNumero'),
            complemento: document.getElementById('addrComplemento'),
            bairro: document.getElementById('addrBairro'),
            cidade: document.getElementById('addrCidade'),
            uf: document.getElementById('addrUf'),
            pais: document.getElementById('addrPais'),
            ponto: document.getElementById('addrPonto'),
            principal: document.getElementById('addrPrincipal')
        };

        const btnSave = document.getElementById('btnSaveAddress');
        const errorBox = document.getElementById('addrError');
        const modalTitle = document.getElementById('modalAddAddressLabel');
        let editingIndex = null; // null = novo; número = edição
        let items = [];

        function setError(msg) {
            if (!errorBox) return;
            errorBox.classList.add('alert', 'alert-danger');
            errorBox.textContent = msg || '';
            errorBox.style.display = msg ? 'block' : 'none';
        }

        function normalizeCep(v) {
            return (v || '').replace(/\D/g, '').slice(0, 8);
        }

        function resetModal() {
            setError('');
            editingIndex = null;
            modalTitle && (modalTitle.textContent = 'Adicionar Endereço');
            fld.tipo && (fld.tipo.value = 'ENT');
            ['cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'uf', 'pais', 'ponto'].forEach(k => { if (fld[k]) fld[k].value = ''; });
            if (fld.pais) fld.pais.value = 'Brasil';
            if (fld.principal) fld.principal.checked = false;
        }

        function fillModal(it) {
            if (!it) return;
            modalTitle && (modalTitle.textContent = 'Editar Endereço');
            if (fld.tipo) fld.tipo.value = it.tipo || 'ENT';
            if (fld.cep) fld.cep.value = it.cep || '';
            if (fld.logradouro) fld.logradouro.value = it.logradouro || '';
            if (fld.numero) fld.numero.value = it.numero || '';
            if (fld.complemento) fld.complemento.value = it.complemento || '';
            if (fld.bairro) fld.bairro.value = it.bairro || '';
            if (fld.cidade) fld.cidade.value = it.cidade || '';
            if (fld.uf) fld.uf.value = it.uf || '';
            if (fld.pais) fld.pais.value = it.pais || 'Brasil';
            if (fld.ponto) fld.ponto.value = it.ponto_referencia || '';
            if (fld.principal) fld.principal.checked = !!it.principal;
        }

        function openModal(editIdx) {
            resetModal();
            editingIndex = (typeof editIdx === 'number') ? editIdx : null;
            if (editingIndex !== null && items[editingIndex]) fillModal(items[editingIndex]);
            bsModal && bsModal.show();
        }

        function closeModal() {
            bsModal && bsModal.hide();
        }

        function labelTipo(val) {
            const map = {
                'COB': 'Cobrança',
                'ENT': 'Entrega',
                'FISCAL': 'Fiscal',
                'OUTRO': 'Outro'
            };
            return map[val] || val || '';
        }

        function resumoEndereco(it) {
            const parts = [it.logradouro, it.numero, it.complemento, it.bairro, it.cidade, it.uf, it.cep].filter(Boolean);
            return parts.join(', ');
        }

        function renderTable() {
            tableBody.innerHTML = '';
            items.forEach((it, idx) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="text-nowrap">${labelTipo(it.tipo)}</td>
                    <td>${resumoEndereco(it)}</td>
                    <td class="text-center">${it.principal ? '<span class="badge bg-success">Sim</span>' : '<span class="text-muted">Não</span>'}</td>
                    <td class="text-center">
                        <button type="button" class="btn btn-sm btn-outline-secondary me-1 btn-edit" data-idx="${idx}"><i class="fas fa-edit"></i></button>
                        <button type="button" class="btn btn-sm btn-outline-danger btn-del" data-idx="${idx}"><i class="fas fa-trash"></i></button>
                    </td>`;
                tableBody.appendChild(tr);
            });

            // Bind ações
            tableBody.querySelectorAll('.btn-edit').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const idx = parseInt(e.currentTarget.getAttribute('data-idx'), 10);
                    openModal(idx);
                });
            });
            tableBody.querySelectorAll('.btn-del').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const idx = parseInt(e.currentTarget.getAttribute('data-idx'), 10);
                    items.splice(idx, 1);
                    saveToField();
                    renderTable();
                });
            });

            // Limitar botão de adicionar
            addBtn.disabled = items.length >= maxItems;
            addBtn.title = items.length >= maxItems ? `Limite de ${maxItems} endereços adicionais atingido` : 'Adicionar endereço';
        }

        function collectFromModal() {
            const cep = normalizeCep(fld.cep ? fld.cep.value : '');
            const it = {
                tipo: fld.tipo ? fld.tipo.value : 'ENT',
                cep: cep || '',
                logradouro: fld.logradouro ? (fld.logradouro.value || '') : '',
                numero: fld.numero ? (fld.numero.value || '') : '',
                complemento: fld.complemento ? (fld.complemento.value || '') : '',
                bairro: fld.bairro ? (fld.bairro.value || '') : '',
                cidade: fld.cidade ? (fld.cidade.value || '') : '',
                uf: fld.uf ? (fld.uf.value || '') : '',
                pais: fld.pais ? (fld.pais.value || 'Brasil') : 'Brasil',
                ponto_referencia: fld.ponto ? (fld.ponto.value || '') : '',
                principal: fld.principal ? !!fld.principal.checked : false,
            };
            // Campos mínimos
            if (!(it.logradouro && it.cidade && it.uf)) {
                setError('Preencha ao menos Logradouro, Cidade e UF.');
                return null;
            }
            return it;
        }

        function loadFromField() {
            try {
                items = JSON.parse(jsonField.value || '[]');
                if (!Array.isArray(items)) items = [];
                items = items.slice(0, maxItems);
            } catch (e) {
                items = [];
            }
        }

        function saveToField() {
            jsonField.value = JSON.stringify(items);
        }

        // CEP lookup para o modal e para o CEP principal do step
        section.addEventListener('blur', function (ev) {
            const target = ev.target;
            if (!(target instanceof HTMLElement)) return;
            const isCepField = target.id === 'addrCep' || target.getAttribute('name') === 'cep';
            if (!isCepField) return;
            const digits = (target.value || '').replace(/\D/g, '');
            if (digits.length !== 8) return;
            fetch(`https://viacep.com.br/ws/${digits}/json/`).then(r => r.json()).then(data => {
                if (data && !data.erro) {
                    if (target.id === 'addrCep') {
                        if (fld.logradouro) fld.logradouro.value = data.logradouro || '';
                        if (fld.bairro) fld.bairro.value = data.bairro || '';
                        if (fld.cidade) fld.cidade.value = data.localidade || '';
                        if (fld.uf) fld.uf.value = data.uf || '';
                    } else {
                        // campos principais do step
                        const root = section;
                        const setVal = (selector, val) => { const el = root.querySelector(selector); if (el) el.value = val || ''; };
                        setVal('[name="logradouro"]', data.logradouro);
                        setVal('[name="bairro"]', data.bairro);
                        setVal('[name="cidade"]', data.localidade);
                        setVal('[name="uf"]', data.uf);
                    }
                }
            }).catch(() => {
                // silencioso
            });
        }, true);

        // Bind botões
        addBtn.addEventListener('click', function (e) {
            e.preventDefault();
            if (items.length >= maxItems) return;
            openModal(null);
        });

        if (btnSave) {
            btnSave.addEventListener('click', function () {
                const it = collectFromModal();
                if (!it) return;
                if (editingIndex === null) {
                    items.push(it);
                } else {
                    items[editingIndex] = it;
                }
                saveToField();
                renderTable();
                closeModal();
            });
        }

        // Inicializa com dados existentes do JSON escondido
        loadFromField();
        renderTable();
    }

    /**
     * Step 5: Configurações e Módulos
     */
    function initializeWizardConfigurationStep() {
        const section = document.getElementById('wizard-configuration-section');
        if (!section) return; // não é o step 5

        const LS_KEY = 'tenant_wizard_enabled_modules';
        const moduleCheckboxes = section.querySelectorAll('input[name="enabled_modules"]');
        const moduleCounter = document.getElementById('moduleCounter');
        const masterCategoryCbs = section.querySelectorAll('.master-category');

        function updateModuleCount() {
            const selected = section.querySelectorAll('input[name="enabled_modules"]:checked').length;
            const total = moduleCheckboxes.length;
            if (moduleCounter) {
                moduleCounter.textContent = `${selected} de ${total} módulos selecionados`;
                moduleCounter.className = 'badge ' + (selected > 0 ? 'bg-success' : 'bg-secondary');
            }
        }

        function syncMasterForCategory(catSlug) {
            const items = section.querySelectorAll(`.module-card[data-category-item="${catSlug}"] input[name="enabled_modules"]`);
            const master = section.querySelector(`.master-category[data-category-target="${catSlug}"]`);
            if (!master) return;
            const total = items.length;
            const checked = Array.from(items).filter(i => i.checked).length;
            master.indeterminate = checked > 0 && checked < total;
            master.checked = checked === total && total > 0;
        }

        function saveSelectedToLocalStorage() {
            try {
                const selected = Array.from(section.querySelectorAll('input[name="enabled_modules"]:checked')).map(c => c.value);
                if (selected.length) localStorage.setItem(LS_KEY, JSON.stringify(selected));
                else localStorage.removeItem(LS_KEY);
            } catch (_) { }
        }

        function handlePortalAtivoVisibility() {
            const portalCard = section.querySelector('.portal-ativo-wrapper');
            if (!portalCard) return;
            const portalModuleCb = section.querySelector('input[name="enabled_modules"][value="portal_cliente"]');
            const warning = document.getElementById('portalAtivoWarning');
            if (portalModuleCb && portalModuleCb.checked) {
                portalCard.style.display = 'block';
                if (warning) warning.classList.add('d-none');
            } else {
                portalCard.style.display = 'none';
                if (warning) warning.classList.remove('d-none');
                const checkbox = portalCard.querySelector('.portal-ativo-checkbox');
                if (checkbox) checkbox.checked = false;
            }
        }

        // Eventos de mudança
        moduleCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                updateModuleCount();
                const card = checkbox.closest('.module-card');
                if (card) {
                    const cat = card.getAttribute('data-category-item');
                    if (cat) syncMasterForCategory(cat);
                }
                handlePortalAtivoVisibility();
                saveSelectedToLocalStorage();
            });
        });

        masterCategoryCbs.forEach(master => {
            master.addEventListener('change', () => {
                const cat = master.getAttribute('data-category-target');
                const items = section.querySelectorAll(`.module-card[data-category-item="${cat}"] input[name="enabled_modules"]`);
                items.forEach(i => { i.checked = master.checked; });
                updateModuleCount();
                syncMasterForCategory(cat);
                handlePortalAtivoVisibility();
                saveSelectedToLocalStorage();
            });
        });

        // Ações globais Selecionar/Limpar
        const btnSelectAll = document.getElementById('btnSelectAllModules');
        const btnClearAll = document.getElementById('btnClearAllModules');
        if (btnSelectAll) btnSelectAll.addEventListener('click', () => {
            moduleCheckboxes.forEach(cb => { cb.checked = true; });
            masterCategoryCbs.forEach(cb => { cb.checked = true; cb.indeterminate = false; });
            updateModuleCount();
            masterCategoryCbs.forEach(cb => { const cat = cb.getAttribute('data-category-target'); syncMasterForCategory(cat); });
            handlePortalAtivoVisibility();
            saveSelectedToLocalStorage();
        });
        if (btnClearAll) btnClearAll.addEventListener('click', () => {
            moduleCheckboxes.forEach(cb => { cb.checked = false; });
            masterCategoryCbs.forEach(cb => { cb.checked = false; cb.indeterminate = false; });
            updateModuleCount();
            handlePortalAtivoVisibility();
            saveSelectedToLocalStorage();
        });

        // Pré-seleção de módulos via json_script ou localStorage
        try {
            const preselectedEl = document.getElementById('wizard-selected-modules');
            if (preselectedEl) {
                const selectedList = JSON.parse(preselectedEl.textContent || '[]');
                if (Array.isArray(selectedList)) moduleCheckboxes.forEach(cb => { if (selectedList.includes(cb.value)) cb.checked = true; });
            } else {
                const raw = localStorage.getItem(LS_KEY);
                if (raw) { const arr = JSON.parse(raw); if (Array.isArray(arr)) moduleCheckboxes.forEach(cb => { if (arr.includes(cb.value)) cb.checked = true; }); }
            }
        } catch (_) { }

        // Subdomínio: validação e verificação remota
        const subdomainInput = section.querySelector('input[name="subdomain"]');
        const subdomainFeedback = document.getElementById('subdomainFeedback');
        const validateUrl = section.dataset.validateUrl || '';
        const re = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
        let subdomainTimer;

        function setFeedback(text, type) {
            if (!subdomainFeedback) return;
            subdomainFeedback.style.display = text ? 'block' : 'none';
            subdomainFeedback.className = 'form-text mt-1 ' + (type === 'ok' ? 'text-success' : type === 'warn' ? 'text-warning' : type === 'err' ? 'text-danger' : 'text-muted');
            subdomainFeedback.textContent = text || '';
        }

        function getCookie(name) {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; ${name}=`);
            if (parts.length === 2) return parts.pop().split(';').shift();
        }

        async function checkAvailability(value) {
            if (!validateUrl || !subdomainInput) return;
            try {
                const formToken = document.querySelector('input[name="csrfmiddlewaretoken"]');
                const csrf = getCookie('csrftoken') || (formToken ? formToken.value : '');
                const body = new URLSearchParams();
                body.append('field_name', 'subdomain');
                body.append('field_value', value);
                body.append('current_step', subdomainInput?.dataset.currentStep || '5');
                const editingPk = subdomainInput?.dataset.editingPk || '';
                if (editingPk) body.append('editing_tenant_pk', editingPk);

                const resp = await fetch(validateUrl, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrf,
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: body.toString()
                });
                const data = await resp.json();
                if (data.valid) {
                    setFeedback('Subdomínio disponível.', 'ok');
                    subdomainInput.classList.remove('is-invalid');
                    subdomainInput.classList.add('is-valid');
                } else {
                    setFeedback(data.message || 'Este subdomínio já está em uso.', 'err');
                    subdomainInput.classList.remove('is-valid');
                    subdomainInput.classList.add('is-invalid');
                }
            } catch (e) {
                setFeedback('Não foi possível validar agora. Tente novamente.', 'warn');
            }
        }

        if (subdomainInput) {
            subdomainInput.addEventListener('input', function () {
                const v = this.value.trim().toLowerCase();
                if (!v || re.test(v)) {
                    this.setCustomValidity('');
                    this.classList.remove('is-invalid');
                } else {
                    this.setCustomValidity('Use apenas letras minúsculas, números e hífen. Não iniciar/terminar com hífen.');
                    this.classList.add('is-invalid');
                    setFeedback('Formato inválido. Use letras minúsculas, números e hífen.', 'err');
                    return;
                }
                clearTimeout(subdomainTimer);
                if (v) {
                    setFeedback('Verificando disponibilidade...', '');
                    subdomainTimer = setTimeout(() => checkAvailability(v), 450);
                } else {
                    setFeedback('', '');
                    this.classList.remove('is-valid');
                }
            });
            subdomainInput.addEventListener('blur', function () {
                const v = this.value.trim().toLowerCase();
                if (v && re.test(v)) {
                    setFeedback('Verificando disponibilidade...', '');
                    checkAvailability(v);
                }
            });
        }

        // Pré-visualização do logo
        (function () {
            const logoInput = section.querySelector('input[type="file"][name="logo"]');
            const logoPreview = document.getElementById('logoPreview');
            if (logoInput && logoPreview) {
                logoInput.addEventListener('change', function () {
                    const file = this.files && this.files[0];
                    if (file) {
                        const url = URL.createObjectURL(file);
                        logoPreview.src = url;
                        logoPreview.style.display = 'inline-block';
                    } else {
                        logoPreview.removeAttribute('src');
                        logoPreview.style.display = 'none';
                    }
                });
            }
        })();

        // Pré-visualização de tema (apenas visual)
        (function () {
            const themeSelect = section.querySelector('select[name="theme_preview"]');
            const colorInput = document.getElementById('primaryColorPreview');
            if (themeSelect) {
                themeSelect.addEventListener('change', () => {
                    document.documentElement.dataset.theme = themeSelect.value || 'default';
                });
            }
            if (colorInput) {
                colorInput.addEventListener('input', () => {
                    document.documentElement.style.setProperty('--bs-primary', colorInput.value);
                });
            }
        })();

        // Inicializações finais
        updateModuleCount();
        masterCategoryCbs.forEach(cb => { const cat = cb.getAttribute('data-category-target'); syncMasterForCategory(cat); });
        handlePortalAtivoVisibility();
    }

    /**
     * Inicializa os seletores de data (Flatpickr)
     */
    function initializeDatePickers() {
        console.log('Inicializando date pickers...');

        if (typeof flatpickr !== 'undefined') {
            $('.flatpickr').flatpickr({
                dateFormat: 'd/m/Y',
                locale: 'pt',
                allowInput: true,
                clickOpens: true,
                altInput: false,
                parseDate: function (datestr, format) {
                    // Parse de data no formato brasileiro
                    if (datestr && datestr.includes('/')) {
                        const parts = datestr.split('/');
                        if (parts.length === 3) {
                            return new Date(parts[2], parts[1] - 1, parts[0]);
                        }
                    }
                    return null;
                },
                formatDate: function (date, format) {
                    // Formato de saída brasileiro
                    const day = String(date.getDate()).padStart(2, '0');
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const year = date.getFullYear();
                    return `${day}/${month}/${year}`;
                }
            });
        } else {
            console.warn('Flatpickr não encontrado. Usando fallback de data.');
        }
    }

    /**
     * Toggle entre Pessoa Física e Jurídica
     * REMOVIDO: Implementação movida para template step_identification.html
     */
    function initializePersonTypeToggle() {
        console.log('Toggle de tipo de pessoa gerenciado pelo template step_identification.html');
        // Função removida para evitar conflitos
    }

    /**
     * Busca automática de endereço por CEP
     */
    function initializeCepLookup() {
        console.log('Inicializando busca de CEP...');

        $(document).on('blur', '[data-cep-lookup="true"]', function () {
            const cepField = $(this);
            const cep = cepField.val().replace(/\D/g, '');

            if (cep.length === 8) {
                console.log('Buscando CEP:', cep);

                // Mostrar loading
                cepField.addClass('loading');

                // Buscar CEP via ViaCEP
                $.ajax({
                    url: `https://viacep.com.br/ws/${cep}/json/`,
                    type: 'GET',
                    dataType: 'json',
                    timeout: 5000,
                    success: function (data) {
                        if (data && !data.erro) {
                            // Preencher campos automaticamente
                            $('[name="logradouro"]').val(data.logradouro || '');
                            $('[name="bairro"]').val(data.bairro || '');
                            $('[name="cidade"]').val(data.localidade || '');
                            $('[name="estado"]').val(data.uf || '');

                            // Focar no campo número
                            $('[name="numero"]').focus();

                            console.log('CEP encontrado:', data);
                        } else {
                            console.warn('CEP não encontrado');
                            showToast('CEP não encontrado', 'warning');
                        }
                    },
                    error: function () {
                        console.error('Erro ao buscar CEP');
                        showToast('Erro ao buscar CEP', 'error');
                    },
                    complete: function () {
                        cepField.removeClass('loading');
                    }
                });
            }
        });
    }

    /**
     * Validação de formulário em tempo real
     */
    function initializeFormValidation() {
        console.log('Inicializando validação de formulário...');

        // Validação de CPF
        $(document).on('blur', '.cpf-mask', function () {
            const cpf = $(this).val().replace(/\D/g, '');
            if (cpf && !isValidCPF(cpf)) {
                $(this).addClass('is-invalid');
                showFieldError($(this), 'CPF inválido');
            } else {
                $(this).removeClass('is-invalid').addClass('is-valid');
                hideFieldError($(this));
            }
        });

        // Validação de CNPJ
        $(document).on('blur', '.cnpj-mask', function () {
            const cnpj = $(this).val().replace(/\D/g, '');
            if (cnpj && !isValidCNPJ(cnpj)) {
                $(this).addClass('is-invalid');
                showFieldError($(this), 'CNPJ inválido');
            } else {
                $(this).removeClass('is-invalid').addClass('is-valid');
                hideFieldError($(this));
            }
        });

        // Validação de email
        $(document).on('blur', 'input[type="email"]', function () {
            const email = $(this).val();
            if (email && !isValidEmail(email)) {
                $(this).addClass('is-invalid');
                showFieldError($(this), 'E-mail inválido');
            } else {
                $(this).removeClass('is-invalid').addClass('is-valid');
                hideFieldError($(this));
            }
        });
    }

    /**
     * Navegação e validação do wizard
     */
    function initializeWizardNavigation() {
        console.log('Inicializando navegação do wizard...');

        // Interceptar submit do formulário do wizard
        $(document).on('submit', '.wizard-form', function (e) {
            const form = $(this);
            const submitButton = $(document.activeElement);

            console.log('🚀 Submit detectado:', {
                buttonName: submitButton.attr('name'),
                buttonValue: submitButton.val(),
                formId: form.attr('id'),
                action: form.attr('action')
            });

            // Verificar se é botão de próximo (não interceptar voltar ou finalizar)
            if (submitButton.attr('name') === 'wizard_next') {

                console.log('🔍 Validando campos obrigatórios...');

                // Verificar o passo atual para aplicar validações específicas
                const currentStep = form.find('input[name="wizard_step"]').val() ||
                    form.find('[name*="step"]').val() ||
                    window.location.pathname.match(/step_(\d+)/)?.[1];

                console.log('📍 Passo atual detectado:', currentStep);

                // Para o passo 5 (configurações), permitir avançar sem validações rígidas
                if (currentStep === '5' || currentStep === 5) {
                    console.log('✅ Passo 5 detectado - permitindo navegação livre');
                    // Remover qualquer classe de erro que possa existir
                    form.find('.is-invalid').removeClass('is-invalid');
                    form.find('.wizard-field-errors').hide();
                    return true; // Permitir submit sem validação
                }

                // Validar campos obrigatórios APENAS na seção visível
                const tipoPessoa = $('input[name="tipo_pessoa"]:checked').val();
                let requiredFields;

                if (tipoPessoa === 'PF') {
                    requiredFields = $('#wizard-pf-section').find('[required], .required');
                    console.log(`🔍 Validando ${requiredFields.length} campos para PF.`);
                } else if (tipoPessoa === 'PJ') {
                    requiredFields = $('#wizard-pj-section').find('[required], .required');
                    console.log(`🔍 Validando ${requiredFields.length} campos para PJ.`);
                } else {
                    // Fallback para outros steps ou se nenhum tipo for selecionado
                    requiredFields = form.find('[required]:visible, .required:visible');
                    console.log(`🔍 Validando ${requiredFields.length} campos visíveis (fallback).`);
                }

                let hasErrors = false;
                let firstErrorField = null;

                requiredFields.each(function () {
                    const field = $(this);
                    const value = field.val() ? field.val().trim() : '';

                    if (!value) {
                        field.addClass('is-invalid');
                        if (!firstErrorField) firstErrorField = field;
                        hasErrors = true;

                        // Mostrar mensagem de erro
                        showFieldError(field, 'Este campo é obrigatório');
                    } else {
                        field.removeClass('is-invalid');
                        hideFieldError(field);
                    }
                });

                // Validar seções condicionais (PF/PJ)
                const tipoSelect = form.find('select[name*="tipo_pessoa"]');
                if (tipoSelect.length && tipoSelect.val()) {
                    const tipoPessoa = tipoSelect.val();
                    let conditionalSection;

                    if (tipoPessoa === 'PF') {
                        conditionalSection = $('#wizard-pf-section');
                    } else if (tipoPessoa === 'PJ') {
                        conditionalSection = $('#wizard-pj-section');
                    }

                    if (conditionalSection && conditionalSection.is(':visible')) {
                        const conditionalRequired = conditionalSection.find('[required], .required');

                        conditionalRequired.each(function () {
                            const field = $(this);
                            const value = field.val() ? field.val().trim() : '';

                            if (!value) {
                                field.addClass('is-invalid');
                                if (!firstErrorField) firstErrorField = field;
                                hasErrors = true;
                                showFieldError(field, 'Este campo é obrigatório');
                            }
                        });
                    }
                }

                if (hasErrors) {
                    e.preventDefault();

                    // Focar no primeiro campo com erro
                    if (firstErrorField) {
                        firstErrorField.focus();
                    }

                    // Mostrar toast de erro
                    showToast('Por favor, preencha todos os campos obrigatórios antes de continuar.', 'error');

                    console.log('❌ Validação falhou - submit cancelado');
                    return false;
                }

                console.log('✅ Validação passou - continuando...');
            }
        });
    }

    /**
     * Configuração de tamanhos de campo compactos
     */
    function initializeFieldSizing() {
        console.log('Aplicando sizing compacto aos campos...');

        // Aplicar classes de sizing para campos mais compactos
        $('.wizard-field').addClass('form-control-sm');
        $('.form-select.wizard-field').removeClass('form-control-sm').addClass('form-select-sm');

        // Reduzir espaçamento entre campos
        $('.wizard-field').closest('.mb-3').removeClass('mb-3').addClass('mb-2');
        $('.wizard-field').closest('.form-group').addClass('compact-field');
    }

    /**
     * Validadores auxiliares
     */
    function isValidCPF(cpf) {
        if (cpf.length !== 11 || /^(\d)\1{10}$/.test(cpf)) return false;

        let sum = 0;
        for (let i = 0; i < 9; i++) {
            sum += parseInt(cpf.charAt(i)) * (10 - i);
        }
        let check1 = 11 - (sum % 11);
        if (check1 === 10 || check1 === 11) check1 = 0;
        if (check1 !== parseInt(cpf.charAt(9))) return false;

        sum = 0;
        for (let i = 0; i < 10; i++) {
            sum += parseInt(cpf.charAt(i)) * (11 - i);
        }
        let check2 = 11 - (sum % 11);
        if (check2 === 10 || check2 === 11) check2 = 0;

        return check2 === parseInt(cpf.charAt(10));
    }

    function isValidCNPJ(cnpj) {
        if (cnpj.length !== 14) return false;

        const weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
        const weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];

        let sum = 0;
        for (let i = 0; i < 12; i++) {
            sum += parseInt(cnpj.charAt(i)) * weights1[i];
        }
        let check1 = sum % 11 < 2 ? 0 : 11 - (sum % 11);
        if (check1 !== parseInt(cnpj.charAt(12))) return false;

        sum = 0;
        for (let i = 0; i < 13; i++) {
            sum += parseInt(cnpj.charAt(i)) * weights2[i];
        }
        let check2 = sum % 11 < 2 ? 0 : 11 - (sum % 11);

        return check2 === parseInt(cnpj.charAt(13));
    }

    function isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    /**
     * Funções auxiliares de UI
     */
    function showFieldError(field, message) {
        hideFieldError(field);
        field.after(`<div class="invalid-feedback">${message}</div>`);
    }

    function hideFieldError(field) {
        field.next('.invalid-feedback').remove();
    }

    function showToast(message, type = 'info') {
        console.log(`📢 Toast: ${message} (${type})`);

        // Usar SweetAlert2 se disponível
        if (typeof Swal !== 'undefined') {
            const icon = type === 'error' ? 'error' : type === 'warning' ? 'warning' : 'info';
            Swal.fire({
                title: type === 'error' ? 'Erro' : type === 'warning' ? 'Atenção' : 'Informação',
                text: message,
                icon: icon,
                timer: 3000,
                showConfirmButton: false,
                toast: true,
                position: 'top-end'
            });
            return;
        }

        // Fallback para toast básico
        const toastClass = type === 'error' ? 'bg-danger' : type === 'warning' ? 'bg-warning' : 'bg-info';
        const toast = $(`
            <div class="toast ${toastClass} text-white" role="alert" style="position: fixed; top: 20px; right: 20px; z-index: 9999;">
                <div class="toast-body">${message}</div>
            </div>
        `);

        $('body').append(toast);

        // Usar Bootstrap toast se disponível
        if (toast[0].toast) {
            toast.toast('show');
        } else {
            // Fallback manual
            toast.fadeIn();
            setTimeout(() => toast.fadeOut(() => toast.remove()), 3000);
        }
    }

    /**
     * Inicializa os tooltips do Bootstrap
     */
    function initializeTooltips() {
        // Inicializar tooltips do Bootstrap 5
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl, {
                trigger: 'hover focus'
            });
        });

        console.log('✅ Tooltips inicializados:', tooltipList.length);
    }

    // ===== Step 6: Administradores (multi-admin) =====
    function initializeWizardAdminsStep() {
        const section = document.getElementById('multi-admin-section');
        if (!section) return; // não é a página do step 6

        const tableBody = section.querySelector('#admins-table tbody');
        const addBtn = section.querySelector('#btn-add-admin');
        const jsonField = document.getElementById('admins_json');
        const rowErrorsInput = document.getElementById('admin_row_errors');
        const backendRowErrors = rowErrorsInput ? safeJsonParse(rowErrorsInput.value, []) : [];
        const maxAdmins = parseInt(section.getAttribute('data-max-admins') || '50', 10);

        const bulkPasswordInput = document.getElementById('bulkPassword');
        const toggleBulkPassBtn = document.getElementById('btn-toggle-bulk-pass');
        const bulkPassHint = document.getElementById('bulk-pass-hint');
        const generateBulkBtn = document.getElementById('btn-generate-bulk-pass');

        let admins = safeJsonParse(jsonField?.value || '[]', []);
        if (!Array.isArray(admins)) admins = [];

        // Utilitários
        function safeJsonParse(text, defVal) {
            try { return JSON.parse(text); } catch (_) { return defVal; }
        }
        function slugifyName(value) {
            try {
                return value.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase().replace(/[^a-z0-9\s\.]/g, ' ').replace(/\s+/g, ' ').trim();
            } catch (_) { return (value || '').toString().trim().toLowerCase(); }
        }
        function suggestUsername(nome) {
            if (!nome) return '';
            const baseParts = slugifyName(nome).split(' ');
            if (!baseParts.length) return '';
            const first = baseParts[0];
            const last = baseParts.length > 1 ? baseParts[baseParts.length - 1] : '';
            let candidate = (first + (last ? '.' + last : ''));
            let unique = candidate; let c = 1;
            const existingUsernames = admins.map(a => a.username).filter(Boolean);
            while (existingUsernames.includes(unique)) { unique = candidate + c; c++; }
            return unique.substring(0, 30);
        }
        function saveToField() { if (jsonField) jsonField.value = JSON.stringify(admins.filter(a => a.email || a.nome || a.telefone)); }

        // Renderização
        function render() {
            if (!tableBody) return;
            tableBody.innerHTML = '';
            if (!admins.length) {
                const tr = document.createElement('tr');
                const td = document.createElement('td');
                td.colSpan = 4; td.className = 'text-muted text-center py-3';
                td.textContent = 'Nenhum administrador adicionado.';
                tr.appendChild(td); tableBody.appendChild(tr);
            } else {
                admins.forEach((a, idx) => {
                    const tr = document.createElement('tr'); tr.dataset.idx = idx;
                    const tdNome = document.createElement('td'); tdNome.innerHTML = `<span class="d-block">${a.nome || '-'}</span>`;
                    const tdEmail = document.createElement('td'); tdEmail.textContent = a.email || '-';
                    const tdAtivo = document.createElement('td'); tdAtivo.className = 'text-center'; tdAtivo.innerHTML = `<span class="badge ${a.ativo === false ? 'bg-secondary' : 'bg-success'}">${a.ativo === false ? 'Inativo' : 'Ativo'}</span>`;
                    const tdAcoes = document.createElement('td'); tdAcoes.className = 'text-center text-nowrap';
                    tdAcoes.innerHTML = `
                        <div class="d-flex gap-2 justify-content-center">
                            <button type="button" class="btn btn-sm btn-link text-secondary p-0 btn-view" data-idx="${idx}" title="Visualizar" aria-label="Visualizar"><i class="fas fa-eye"></i></button>
                            <button type="button" class="btn btn-sm btn-link text-primary p-0 btn-edit" data-idx="${idx}" title="Editar" aria-label="Editar"><i class="fas fa-pen"></i></button>
                            <button type="button" class="btn btn-sm btn-link text-danger p-0 btn-remove" data-idx="${idx}" title="Remover" aria-label="Remover"><i class="fas fa-trash"></i></button>
                        </div>`;
                    tdAcoes.querySelector('.btn-view').addEventListener('click', function () { const i = parseInt(this.getAttribute('data-idx')); if (!isNaN(i)) openModal(i, true); });
                    tdAcoes.querySelector('.btn-edit').addEventListener('click', function () { const i = parseInt(this.getAttribute('data-idx')); if (!isNaN(i)) openModal(i); });
                    tdAcoes.querySelector('.btn-remove').addEventListener('click', function () { const i = parseInt(this.getAttribute('data-idx')); if (!isNaN(i)) { admins.splice(i, 1); saveToField(); render(); updateAddBtn(); } });
                    tr.appendChild(tdNome); tr.appendChild(tdEmail); tr.appendChild(tdAtivo); tr.appendChild(tdAcoes);
                    if (backendRowErrors && backendRowErrors.length) {
                        const err = backendRowErrors.find(e => e.row === idx);
                        if (err) {
                            tr.classList.add('table-danger');
                            const errDiv = document.createElement('div');
                            errDiv.className = 'small text-danger mt-1';
                            errDiv.innerHTML = (err.errors || []).map(e => `<div><i class='fas fa-exclamation-circle me-1'></i>${e}</div>`).join('');
                            tdNome.appendChild(errDiv);
                        }
                    }
                    tableBody.appendChild(tr);
                });
            }
        }
        function updateAddBtn() { if (addBtn) addBtn.disabled = admins.length >= maxAdmins; }

        // Modal dinâmico somente quando necessário
        let modalEl = document.getElementById('modalAdmin');
        if (!modalEl) {
            modalEl = document.createElement('div'); modalEl.className = 'modal fade'; modalEl.id = 'modalAdmin'; modalEl.tabIndex = -1; modalEl.setAttribute('aria-hidden', 'true');
            modalEl.innerHTML = `
                <div class=\"modal-dialog modal-lg modal-dialog-centered\">\n\
                    <div class=\"modal-content\">\n\
                        <div class=\"modal-header\">\n\
                            <h5 class=\"modal-title\" id=\"modalAdminLabel\">Adicionar Administrador</h5>\n\
                            <button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"modal\" aria-label=\"Close\"></button>\n\
                        </div>\n\
                        <div class=\"modal-body\">\n\
                            <div class=\"alert alert-danger py-2 px-3 d-none\" id=\"adminError\"></div>\n\
                            <div class=\"row g-2\">\n\
                                <div class=\"col-md-6\">\n\
                                    <label class=\"form-label mb-1\">Nome</label>\n\
                                    <input type=\"text\" class=\"form-control form-control-sm\" id=\"admNome\" maxlength=\"100\" placeholder=\"Nome\">\n\
                                </div>\n\
                                <div class=\"col-md-6\">\n\
                                    <label class=\"form-label mb-1\">Username</label>\n\
                                    <input type=\"text\" class=\"form-control form-control-sm\" id=\"admUsername\" maxlength=\"30\" placeholder=\"auto\">\n\
                                </div>\n\
                                <div class=\"col-md-6\">\n\
                                    <label class=\"form-label mb-1\">E-mail</label>\n\
                                    <input type=\"email\" class=\"form-control form-control-sm\" id=\"admEmail\" maxlength=\"254\" placeholder=\"email@dominio.com\">\n\
                                </div>\n\
                                <div class=\"col-md-6\">\n\
                                    <label class=\"form-label mb-1\">Telefone</label>\n\
                                    <input type=\"text\" class=\"form-control form-control-sm\" id=\"admTelefone\" maxlength=\"20\" placeholder=\"(11) 99999-9999\">\n\
                                </div>\n\
                                <div class=\"col-md-6\">\n\
                                    <label class=\"form-label mb-1\">Cargo</label>\n\
                                    <input type=\"text\" class=\"form-control form-control-sm\" id=\"admCargo\" maxlength=\"100\" placeholder=\"Cargo\" list=\"admCargoDatalist\">\n\
                                    <datalist id=\"admCargoDatalist\"></datalist>\n\
                                </div>\n\
                                <div class=\"col-md-6 d-flex align-items-end gap-2\">\n\
                                    <div class=\"flex-grow-1\">\n\
                                        <label class=\"form-label mb-1\">Senha</label>\n\
                                        <input type=\"password\" class=\"form-control form-control-sm\" id=\"admSenha\" maxlength=\"128\" placeholder=\"Senha\">\n\
                                    </div>\n\
                                    <div class=\"flex-grow-1\">\n\
                                        <label class=\"form-label mb-1\">Confirmar</label>\n\
                                        <input type=\"password\" class=\"form-control form-control-sm\" id=\"admConfirm\" maxlength=\"128\" placeholder=\"Confirmar\">\n\
                                    </div>\n\
                                </div>\n\
                                <div class=\"col-md-6 d-flex align-items-center\">\n\
                                    <div class=\"form-check form-switch mt-4\">\n\
                                        <input class=\"form-check-input\" type=\"checkbox\" id=\"admAtivo\" checked>\n\
                                        <label class=\"form-check-label\" for=\"admAtivo\">Ativo</label>\n\
                                    </div>\n\
                                </div>\n\
                                <div class=\"col-md-6\">\n\
                                    <label class=\"form-label mb-1\">Força da Senha</label>\n\
                                    <div class=\"progress\"><div class=\"progress-bar\" id=\"admPwBar\" style=\"width:0%\"></div></div>\n\
                                    <small class=\"text-muted\" id=\"admPwLabel\">Vazia</small>\n\
                                </div>\n\
                            </div>\n\
                        </div>\n\
                        <div class=\"modal-footer\">\n\
                            <button type=\"button\" class=\"btn btn-light\" data-bs-dismiss=\"modal\">Cancelar</button>\n\
                            <button type=\"button\" class=\"btn btn-primary\" id=\"btnSaveAdmin\">Adicionar</button>\n\
                        </div>\n\
                    </div>\n\
                </div>`;
            document.body.appendChild(modalEl);
        }
        const bsModal = window.bootstrap && modalEl ? new bootstrap.Modal(modalEl, { backdrop: true, keyboard: true, focus: true }) : null;
        const fld = { nome: document.getElementById('admNome'), username: document.getElementById('admUsername'), email: document.getElementById('admEmail'), telefone: document.getElementById('admTelefone'), cargo: document.getElementById('admCargo'), senha: document.getElementById('admSenha'), confirm: document.getElementById('admConfirm'), ativo: document.getElementById('admAtivo') };
        const pwBar = document.getElementById('admPwBar'); const pwLabel = document.getElementById('admPwLabel');
        const errorBox = document.getElementById('adminError'); const btnSave = document.getElementById('btnSaveAdmin'); const modalTitle = document.getElementById('modalAdminLabel');
        let editingIndex = null;

        function setError(msg) { if (!errorBox) return; if (!msg) { errorBox.classList.add('d-none'); errorBox.textContent = ''; return; } errorBox.textContent = msg; errorBox.classList.remove('d-none'); }
        function resetModal() { setError(''); Object.values(fld).forEach(i => { if (i && i.type !== 'checkbox') i.value = ''; }); if (fld.ativo) fld.ativo.checked = true; updatePw(''); }
        function fillModal(a) { if (!a) return; fld.nome.value = a.nome || ''; fld.username.value = a.username || ''; fld.email.value = a.email || ''; fld.telefone.value = a.telefone || ''; fld.cargo.value = a.cargo || ''; fld.senha.value = a.senha || ''; fld.confirm.value = a.confirm_senha || ''; if (fld.ativo) fld.ativo.checked = (a.ativo !== false); updatePw(fld.senha.value); }
        function setReadOnly(ro) {
            const nodes = [fld.nome, fld.username, fld.email, fld.telefone, fld.cargo, fld.senha, fld.confirm, fld.ativo];
            nodes.forEach(n => { if (!n) return; if (n.type === 'checkbox') { n.disabled = !!ro; } else { n.readOnly = !!ro; } });
            if (btnSave) btnSave.style.display = ro ? 'none' : '';
        }
        function openModal(idx, readOnly = false) {
            editingIndex = (typeof idx === 'number' && !isNaN(idx)) ? idx : null;
            if (editingIndex !== null) { fillModal(admins[editingIndex] || {}); if (modalTitle) modalTitle.textContent = readOnly ? 'Visualizar Administrador' : 'Editar Administrador'; if (btnSave) btnSave.textContent = 'Salvar'; }
            else { resetModal(); if (modalTitle) modalTitle.textContent = 'Adicionar Administrador'; if (btnSave) btnSave.textContent = 'Adicionar'; }
            setReadOnly(!!readOnly);
            if (bsModal) bsModal.show(); else { modalEl.classList.add('show'); modalEl.style.display = 'block'; modalEl.setAttribute('aria-modal', 'true'); modalEl.removeAttribute('aria-hidden'); document.body.classList.add('modal-open'); }
        }
        function updatePw(pwd) { if (!pwBar || !pwLabel) return; const st = passwordStrength(pwd); const perc = Math.min(100, st.score * 20 + (pwd.length >= 8 ? 10 : 0)); pwBar.style.width = perc + '%'; pwBar.className = 'progress-bar ' + st.class; pwLabel.textContent = st.label; }
        function passwordStrength(pwd) {
            if (!pwd) return { score: 0, label: 'Vazia', class: 'bg-secondary' };
            let score = 0; if (pwd.length >= 8) score++; if (pwd.length >= 12) score++;
            if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score++; if (/[0-9]/.test(pwd)) score++; if (/[^A-Za-z0-9]/.test(pwd)) score++;
            let label = 'Fraca', cls = 'bg-danger';
            if (score >= 5) { label = 'Forte'; cls = 'bg-success'; }
            else if (score === 4) { label = 'Boa'; cls = 'bg-primary'; }
            else if (score === 3) { label = 'Razoável'; cls = 'bg-warning'; }
            else if (score <= 2) { label = 'Fraca'; cls = 'bg-danger'; }
            return { score: score, label: label, class: cls };
        }

        function collectModal() {
            const nome = (fld.nome?.value || '').trim();
            const email = (fld.email?.value || '').trim();
            const username = (fld.username?.value || '').trim() || suggestUsername(nome);
            const telefone = (fld.telefone?.value || '').trim();
            const cargo = (fld.cargo?.value || '').trim();
            const senha = (fld.senha?.value || '');
            const confirm_senha = (fld.confirm?.value || '');
            const ativo = !!(fld.ativo?.checked);
            if (!email && !nome && !telefone) { setError('Informe ao menos Nome, E-mail ou Telefone.'); return null; }
            if (senha && senha.length < 8) { setError('Senha deve conter ao menos 8 caracteres.'); return null; }
            if (senha && confirm_senha && senha !== confirm_senha) { setError('Confirmação de senha não coincide.'); return null; }
            setError('');
            return { nome, email, username, telefone, cargo, senha, confirm_senha, ativo };
        }

        if (addBtn) addBtn.addEventListener('click', function (e) { e.preventDefault(); if (admins.length >= maxAdmins) { showToast(`Limite de ${maxAdmins} administradores atingido.`, 'warning'); return; } openModal(null); });

        if (btnSave) btnSave.addEventListener('click', function () { const data = collectModal(); if (!data) return; if (editingIndex !== null) { admins[editingIndex] = data; } else { admins.push(data); } saveToField(); render(); updateAddBtn(); if (bsModal) bsModal.hide(); });

        // CSV import
        const csvInput = document.getElementById('csvAdminsInput');
        const parseBtn = document.getElementById('btn-parse-csv');
        const csvStatus = document.getElementById('csvAdminsStatus');
        if (parseBtn) {
            parseBtn.addEventListener('click', function () {
                if (!csvInput?.files?.length) { if (csvStatus) csvStatus.textContent = 'Selecione um arquivo.'; return; }
                const file = csvInput.files[0];
                const reader = new FileReader();
                reader.onload = function (evt) {
                    try {
                        const lines = String(evt.target.result || '').split(/\r?\n/).filter(l => l.trim());
                        if (!lines.length) { if (csvStatus) csvStatus.textContent = 'Arquivo vazio.'; return; }
                        const header = lines[0].split(',').map(h => h.trim().toLowerCase());
                        const idxNome = header.indexOf('nome');
                        const idxEmail = header.indexOf('email');
                        const idxTel = header.indexOf('telefone');
                        const idxCargo = header.indexOf('cargo');
                        let added = 0;
                        for (let i = 1; i < lines.length; i++) {
                            if (admins.length >= maxAdmins) break;
                            const cols = lines[i].split(',');
                            const email = (cols[idxEmail] || '').trim();
                            if (!email) continue;
                            admins.push({
                                nome: (idxNome >= 0 ? cols[idxNome].trim() : ''),
                                email: email,
                                telefone: (idxTel >= 0 ? cols[idxTel].trim() : ''),
                                cargo: (idxCargo >= 0 ? cols[idxCargo].trim() : ''),
                                ativo: true
                            });
                            added++;
                        }
                        render(); updateAddBtn();
                        if (csvStatus) csvStatus.textContent = added + ' administradores adicionados.';
                    } catch (err) { if (csvStatus) csvStatus.textContent = 'Erro ao processar CSV: ' + err; }
                };
                reader.readAsText(file);
            });
        }

        // Bulk password
        function genPassword(len = 12) { const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%'; let out = ''; for (let i = 0; i < len; i++) { out += chars[Math.floor(Math.random() * chars.length)]; } return out; }
        if (toggleBulkPassBtn && bulkPasswordInput) toggleBulkPassBtn.addEventListener('click', () => { bulkPasswordInput.type = bulkPasswordInput.type === 'password' ? 'text' : 'password'; toggleBulkPassBtn.innerHTML = bulkPasswordInput.type === 'password' ? '<i class="fas fa-eye"></i>' : '<i class="fas fa-eye-slash"></i>'; });
        if (generateBulkBtn && bulkPasswordInput && bulkPassHint) generateBulkBtn.addEventListener('click', () => { const pwd = genPassword(12); bulkPasswordInput.value = pwd; bulkPassHint.textContent = 'Senha gerada. Será usada apenas se senhas individuais não forem definidas.'; });

        const formEl = section.closest('form') || document.querySelector('form');
        if (formEl) formEl.addEventListener('submit', () => { saveToField(); if (bulkPasswordInput?.value) { let hidden = document.getElementById('bulk_password_field'); if (!hidden) { hidden = document.createElement('input'); hidden.type = 'hidden'; hidden.name = 'bulk_admin_password'; hidden.id = 'bulk_password_field'; formEl.appendChild(hidden); } hidden.value = bulkPasswordInput.value; } });

        // Autocomplete de Cargo
        (function () {
            const input = document.getElementById('admCargo');
            if (!input) return;
            const datalist = document.getElementById('admCargoDatalist');
            const apiUrl = section.getAttribute('data-cargo-api') || (window.CORE_CARGO_SUGGESTIONS_URL || '');
            if (!apiUrl) return;
            let lastQuery = '';
            let timer = null;
            function renderOptions(items) { if (!datalist) return; datalist.innerHTML = ''; (items || []).forEach(v => { const opt = document.createElement('option'); opt.value = v; datalist.appendChild(opt); }); }
            async function fetchSuggestions(q) { try { const url = q ? `${apiUrl}?q=${encodeURIComponent(q)}&limit=15` : `${apiUrl}?limit=15`; const resp = await fetch(url, { headers: { 'Accept': 'application/json' } }); if (!resp.ok) return; const data = await resp.json(); const arr = Array.isArray(data?.results) ? data.results : []; renderOptions(arr); } catch (_) { } }
            function debouncedFetch(q) { if (q === lastQuery) return; lastQuery = q; if (timer) clearTimeout(timer); timer = setTimeout(() => fetchSuggestions(q), 200); }
            input.addEventListener('input', () => debouncedFetch(input.value.trim()));
            input.addEventListener('focus', () => { if (!datalist || datalist.children.length === 0) { fetchSuggestions(''); } });
        })();

        // Inicializa
        render(); updateAddBtn();
    }

    // ===== Step 7: Contatos adicionais =====
    function initializeWizardContactsStep() {
        const section = document.getElementById('wizard-extra-contacts-section');
        // Autocomplete para cargos dos campos principais (se existirem na página)
        (function attachCargoAutocompleteToMain() {
            const apiUrl = (section && section.getAttribute('data-cargo-api')) || (window.CORE_CARGO_SUGGESTIONS_URL || '');
            if (!apiUrl) return;
            const ids = [
                'id_cargo_contato_principal',
                'id_cargo_responsavel_comercial',
                'id_cargo_responsavel_financeiro'
            ];
            ids.forEach(function (id) {
                const input = document.getElementById(id);
                if (!input) return;
                const dlId = id + '_datalist';
                let datalist = document.getElementById(dlId);
                if (!datalist) {
                    datalist = document.createElement('datalist');
                    datalist.id = dlId;
                    input.setAttribute('list', dlId);
                    input.parentElement && input.parentElement.appendChild(datalist);
                }
                let lastQuery = ''; let timer = null;
                function renderOptions(items) { datalist.innerHTML = ''; (items || []).forEach(function (v) { const opt = document.createElement('option'); opt.value = v; datalist.appendChild(opt); }); }
                async function fetchSuggestions(q) {
                    try {
                        const url = q ? `${apiUrl}?q=${encodeURIComponent(q)}&limit=15` : `${apiUrl}?limit=15`;
                        const resp = await fetch(url, { headers: { 'Accept': 'application/json' } });
                        if (!resp.ok) return; const data = await resp.json();
                        const arr = Array.isArray(data?.results) ? data.results : []; renderOptions(arr);
                    } catch (_) { }
                }
                function debouncedFetch(q) { if (q === lastQuery) return; lastQuery = q; if (timer) clearTimeout(timer); timer = setTimeout(function () { fetchSuggestions(q); }, 200); }
                input.addEventListener('input', function () { debouncedFetch(input.value.trim()); });
                input.addEventListener('focus', function () { if (!datalist || datalist.children.length === 0) { fetchSuggestions(''); } });
            });
        })();

        if (!section) return; // não é a página
        const maxContacts = parseInt(section.getAttribute('data-max-contacts') || '100', 10);
        const jsonField = document.querySelector('.wizard-extra-contacts-json') || document.querySelector('input[name$="contacts_json"]');
        const tableBody = document.querySelector('#tblExtraContacts tbody');
        const addBtn = document.getElementById('btnAddExtraContact');

        let items = safeParse(jsonField?.value || '[]', []);
        if (!Array.isArray(items)) items = [];

        function safeParse(txt, def) { try { return JSON.parse(txt); } catch (_) { return def; } }
        function save() { if (jsonField) jsonField.value = JSON.stringify(items); }
        function updateAddBtn() { if (addBtn) addBtn.disabled = items.length >= maxContacts; }
        function render() {
            if (!tableBody) return; tableBody.innerHTML = ''; if (!items.length) { const tr = document.createElement('tr'); const td = document.createElement('td'); td.colSpan = 5; td.className = 'text-muted text-center py-3'; td.textContent = 'Nenhum contato adicionado.'; tr.appendChild(td); tableBody.appendChild(tr); return; } items.forEach(function (it, idx) {
                const tr = document.createElement('tr'); const tdNome = document.createElement('td'); const tdCargo = document.createElement('td'); const tdContato = document.createElement('td'); const tdObs = document.createElement('td'); const tdAcoes = document.createElement('td'); tdCargo.className = 'text-nowrap'; tdContato.className = 'text-nowrap'; tdAcoes.className = 'text-center text-nowrap'; tdNome.textContent = it.nome || '-'; tdCargo.textContent = it.cargo || '-'; const parts = []; if (it.telefone) parts.push(it.telefone); if (it.email) parts.push(it.email); tdContato.textContent = parts.join(' • '); tdObs.textContent = (it.observacao || '').slice(0, 60); tdAcoes.innerHTML = '<div class="d-flex gap-2 justify-content-center">\
<button type="button" class="btn btn-sm btn-link text-primary p-0 btn-edit" data-idx="'+ idx + '" title="Editar" aria-label="Editar"><i class="fas fa-pen"></i></button>\
<button type="button" class="btn btn-sm btn-link text-danger p-0 btn-remove" data-idx="'+ idx + '" title="Remover" aria-label="Remover"><i class="fas fa-trash"></i></button>\
</div>'; tdAcoes.querySelector('.btn-edit').addEventListener('click', function () { const i = parseInt(this.getAttribute('data-idx')); if (!isNaN(i)) openModal(i); }); tdAcoes.querySelector('.btn-remove').addEventListener('click', function () { const i = parseInt(this.getAttribute('data-idx')); if (!isNaN(i)) { items.splice(i, 1); save(); render(); updateAddBtn(); } }); tr.appendChild(tdNome); tr.appendChild(tdCargo); tr.appendChild(tdContato); tr.appendChild(tdObs); tr.appendChild(tdAcoes); tableBody.appendChild(tr);
            });
        }

        // Modal dinâmico
        let modalEl = document.getElementById('modalExtraContact');
        if (!modalEl) {
            modalEl = document.createElement('div'); modalEl.className = 'modal fade'; modalEl.id = 'modalExtraContact'; modalEl.tabIndex = -1; modalEl.setAttribute('aria-hidden', 'true');
            modalEl.innerHTML = '\
<div class="modal-dialog modal-dialog-centered">\
    <div class="modal-content">\
        <div class="modal-header">\
            <h5 class="modal-title" id="modalExtraContactLabel">Adicionar Contato</h5>\
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>\
        </div>\
        <div class="modal-body">\
            <div class="alert alert-danger py-2 px-3 d-none" id="extraContactError"></div>\
            <div class="row g-2">\
                <div class="col-md-6"><label class="form-label mb-1">Nome</label><input type="text" class="form-control form-control-sm" id="extraContactNome" maxlength="100" placeholder="Nome"></div>\
                <div class="col-md-6"><label class="form-label mb-1">Cargo</label><input type="text" class="form-control form-control-sm" id="extraContactCargo" maxlength="100" placeholder="Cargo" list="extraContactCargoDatalist"><datalist id="extraContactCargoDatalist"></datalist></div>\
                <div class="col-md-6"><label class="form-label mb-1">Telefone</label><input type="text" class="form-control form-control-sm" id="extraContactTelefone" maxlength="20" placeholder="(11) 99999-9999"></div>\
                <div class="col-md-6"><label class="form-label mb-1">E-mail</label><input type="email" class="form-control form-control-sm" id="extraContactEmail" maxlength="254" placeholder="email@dominio.com"></div>\
                <div class="col-12"><label class="form-label mb-1">Observação</label><input type="text" class="form-control form-control-sm" id="extraContactObservacao" maxlength="500" placeholder="Observação"></div>\
            </div>\
        </div>\
        <div class="modal-footer">\
            <button type="button" class="btn btn-light" data-bs-dismiss="modal">Cancelar</button>\
            <button type="button" class="btn btn-primary" id="btnSaveExtraContact">Adicionar</button>\
        </div>\
    </div>\
</div>';
            document.body.appendChild(modalEl);
        }
        const bsModal = window.bootstrap && modalEl ? new bootstrap.Modal(modalEl, { backdrop: true, keyboard: true, focus: true }) : null;
        const fld = { nome: document.getElementById('extraContactNome'), cargo: document.getElementById('extraContactCargo'), telefone: document.getElementById('extraContactTelefone'), email: document.getElementById('extraContactEmail'), observacao: document.getElementById('extraContactObservacao') };
        const errorBox = document.getElementById('extraContactError');
        const btnSave = document.getElementById('btnSaveExtraContact');
        const modalTitle = document.getElementById('modalExtraContactLabel');
        let editingIndex = null;

        function setError(msg) { if (!errorBox) return; if (!msg) { errorBox.classList.add('d-none'); errorBox.textContent = ''; return; } errorBox.textContent = msg; errorBox.classList.remove('d-none'); }
        function resetModal() { setError(''); Object.values(fld).forEach(function (i) { if (i) i.value = ''; }); }
        function fillModal(it) { if (!it) return; fld.nome.value = it.nome || ''; fld.cargo.value = it.cargo || ''; fld.telefone.value = it.telefone || ''; fld.email.value = it.email || ''; fld.observacao.value = it.observacao || ''; }
        function openModal(editIdx) { editingIndex = (typeof editIdx === 'number' && !isNaN(editIdx)) ? editIdx : null; if (editingIndex !== null) { fillModal(items[editingIndex] || {}); if (modalTitle) modalTitle.textContent = 'Editar Contato'; if (btnSave) btnSave.textContent = 'Salvar'; } else { resetModal(); if (modalTitle) modalTitle.textContent = 'Adicionar Contato'; if (btnSave) btnSave.textContent = 'Adicionar'; } if (bsModal) bsModal.show(); else { modalEl.classList.add('show'); modalEl.style.display = 'block'; modalEl.setAttribute('aria-modal', 'true'); modalEl.removeAttribute('aria-hidden'); document.body.classList.add('modal-open'); } }

        // Eventos
        if (addBtn) addBtn.addEventListener('click', function (e) { e.preventDefault(); if (items.length >= maxContacts) { showToast('Limite de ' + maxContacts + ' contatos atingido.', 'warning'); return; } openModal(null); });
        if (btnSave) btnSave.addEventListener('click', function () { const novo = collect(); if (!novo) return; if (editingIndex !== null) { items[editingIndex] = novo; } else { items.push(novo); } save(); render(); updateAddBtn(); if (bsModal) bsModal.hide(); });

        function collect() { const nome = (fld.nome?.value || '').trim(); const telefone = (fld.telefone?.value || '').trim(); const email = (fld.email?.value || '').trim(); const cargo = (fld.cargo?.value || '').trim(); const observacao = (fld.observacao?.value || '').trim(); if (!nome && !telefone && !email) { setError('Informe ao menos Nome, Telefone ou E-mail.'); return null; } setError(''); return { nome, telefone, email, cargo, observacao }; }

        // Autocomplete de Cargo no modal
        (function () { const input = fld.cargo; if (!input) return; const datalist = document.getElementById('extraContactCargoDatalist'); const apiUrl = section.getAttribute('data-cargo-api') || (window.CORE_CARGO_SUGGESTIONS_URL || ''); if (!apiUrl) return; let lastQuery = ''; let timer = null; function renderOptions(items) { if (!datalist) return; datalist.innerHTML = ''; (items || []).forEach(function (v) { const opt = document.createElement('option'); opt.value = v; datalist.appendChild(opt); }); } async function fetchSuggestions(q) { try { const url = q ? `${apiUrl}?q=${encodeURIComponent(q)}&limit=15` : `${apiUrl}?limit=15`; const resp = await fetch(url, { headers: { 'Accept': 'application/json' } }); if (!resp.ok) return; const data = await resp.json(); const arr = Array.isArray(data?.results) ? data.results : []; renderOptions(arr); } catch (_) { } } function debouncedFetch(q) { if (q === lastQuery) return; lastQuery = q; if (timer) clearTimeout(timer); timer = setTimeout(function () { fetchSuggestions(q); }, 200); } input.addEventListener('input', function () { debouncedFetch(input.value.trim()); }); input.addEventListener('focus', function () { if (!datalist || datalist.children.length === 0) { fetchSuggestions(''); } }); })();

        // Inicialização
        render(); updateAddBtn(); save();
    }

    // ===== Step 7: Redes sociais =====
    function initializeWizardSocialsStep() {
        const section = document.getElementById('wizard-socials-section');
        if (!section) return;
        const maxSocials = parseInt(section.getAttribute('data-max-socials') || '50', 10);
        const jsonField = document.querySelector('.wizard-socials-json') || document.querySelector('input[name$="socials_json"]');
        const tableBody = document.querySelector('#tblSocials tbody');
        const addBtn = document.getElementById('btnAddSocial');

        let items = safeParse(jsonField?.value || '[]', []);
        if (!Array.isArray(items)) items = [];
        function safeParse(txt, def) { try { return JSON.parse(txt); } catch (_) { return def; } }
        function save() { if (jsonField) jsonField.value = JSON.stringify(items); }
        function updateAddBtn() { if (addBtn) addBtn.disabled = items.length >= maxSocials; }
        function render() {
            if (!tableBody) return; tableBody.innerHTML = ''; if (!items.length) { const tr = document.createElement('tr'); const td = document.createElement('td'); td.colSpan = 3; td.className = 'text-muted text-center py-3'; td.textContent = 'Nenhuma rede adicionada.'; tr.appendChild(td); tableBody.appendChild(tr); return; } items.forEach(function (it, idx) {
                const tr = document.createElement('tr'); const tdNome = document.createElement('td'); const tdLink = document.createElement('td'); const tdAcoes = document.createElement('td'); tdAcoes.className = 'text-center text-nowrap'; tdNome.textContent = it.nome || '-'; const link = (it.link || '').trim(); tdLink.innerHTML = link ? '<a href="' + link + '" target="_blank" rel="noopener">' + link + '</a>' : '-'; tdAcoes.innerHTML = '<div class="d-flex gap-2 justify-content-center">\
<a class="btn btn-sm btn-link text-secondary p-0" href="'+ (link || '#') + '" target="_blank" rel="noopener" title="Abrir" aria-label="Abrir"><i class="fas fa-external-link-alt"></i></a>\
<button type="button" class="btn btn-sm btn-link text-primary p-0 btn-edit" data-idx="'+ idx + '" title="Editar" aria-label="Editar"><i class="fas fa-pen"></i></button>\
<button type="button" class="btn btn-sm btn-link text-danger p-0 btn-remove" data-idx="'+ idx + '" title="Remover" aria-label="Remover"><i class="fas fa-trash"></i></button>\
</div>'; tdAcoes.querySelector('.btn-edit').addEventListener('click', function () { const i = parseInt(this.getAttribute('data-idx')); if (!isNaN(i)) openModal(i); }); tdAcoes.querySelector('.btn-remove').addEventListener('click', function () { const i = parseInt(this.getAttribute('data-idx')); if (!isNaN(i)) { items.splice(i, 1); save(); render(); updateAddBtn(); } }); tr.appendChild(tdNome); tr.appendChild(tdLink); tr.appendChild(tdAcoes); tableBody.appendChild(tr);
            });
        }

        // Modal
        let modalEl = document.getElementById('modalSocial');
        if (!modalEl) {
            modalEl = document.createElement('div'); modalEl.className = 'modal fade'; modalEl.id = 'modalSocial'; modalEl.tabIndex = -1; modalEl.setAttribute('aria-hidden', 'true');
            modalEl.innerHTML = '\
<div class="modal-dialog modal-dialog-centered">\
    <div class="modal-content">\
        <div class="modal-header">\
            <h5 class="modal-title" id="modalSocialLabel">Adicionar Rede Social</h5>\
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>\
        </div>\
        <div class="modal-body">\
            <div class="alert alert-danger py-2 px-3 d-none" id="socialError"></div>\
            <div class="row g-2">\
                <div class="col-md-5"><label class="form-label mb-1">Nome da rede</label><input type="text" class="form-control form-control-sm" id="socialNome" maxlength="50" placeholder="Instagram, LinkedIn, ..."></div>\
                <div class="col-md-7"><label class="form-label mb-1">Link</label><input type="url" class="form-control form-control-sm" id="socialLink" maxlength="500" placeholder="https://instagram.com/empresa"></div>\
            </div>\
        </div>\
        <div class="modal-footer">\
            <button type="button" class="btn btn-light" data-bs-dismiss="modal">Cancelar</button>\
            <button type="button" class="btn btn-primary" id="btnSaveSocial">Adicionar</button>\
        </div>\
    </div>\
</div>';
            document.body.appendChild(modalEl);
        }
        const bsModal = window.bootstrap && modalEl ? new bootstrap.Modal(modalEl, { backdrop: true, keyboard: true, focus: true }) : null;
        const fld = { nome: document.getElementById('socialNome'), link: document.getElementById('socialLink') };
        const errorBox = document.getElementById('socialError');
        const btnSave = document.getElementById('btnSaveSocial');
        const modalTitle = document.getElementById('modalSocialLabel');
        let editingIndex = null;

        function setError(msg) { if (!errorBox) return; if (!msg) { errorBox.classList.add('d-none'); errorBox.textContent = ''; return; } errorBox.textContent = msg; errorBox.classList.remove('d-none'); }
        function resetModal() { setError(''); if (fld.nome) fld.nome.value = ''; if (fld.link) fld.link.value = ''; }
        function fillModal(it) { if (!it) return; fld.nome.value = it.nome || ''; fld.link.value = it.link || ''; }
        function openModal(editIdx) { editingIndex = (typeof editIdx === 'number' && !isNaN(editIdx)) ? editIdx : null; if (editingIndex !== null) { fillModal(items[editingIndex] || {}); if (modalTitle) modalTitle.textContent = 'Editar Rede Social'; if (btnSave) btnSave.textContent = 'Salvar'; } else { resetModal(); if (modalTitle) modalTitle.textContent = 'Adicionar Rede Social'; if (btnSave) btnSave.textContent = 'Adicionar'; } if (bsModal) bsModal.show(); else { modalEl.classList.add('show'); modalEl.style.display = 'block'; modalEl.setAttribute('aria-modal', 'true'); modalEl.removeAttribute('aria-hidden'); document.body.classList.add('modal-open'); } }

        // Eventos
        if (addBtn) addBtn.addEventListener('click', function (e) { e.preventDefault(); if (items.length >= maxSocials) { showToast('Limite de ' + maxSocials + ' redes atingido.', 'warning'); return; } openModal(null); });
        if (btnSave) btnSave.addEventListener('click', function () { const novo = collect(); if (!novo) return; if (editingIndex !== null) { items[editingIndex] = novo; } else { items.push(novo); } save(); render(); updateAddBtn(); if (bsModal) bsModal.hide(); });
        function collect() { const nome = (fld.nome?.value || '').trim(); const link = (fld.link?.value || '').trim(); if (!nome) { setError('Informe o nome da rede.'); return null; } if (!link) { setError('Informe o link da rede.'); return null; } setError(''); return { nome, link }; }

        // Inicialização
        render(); updateAddBtn(); save();
    }

    /**
     * Inicializa o preview dinâmico da empresa
     */
    function initializeWizardPreview() {
        console.log('🔍 Inicializando preview dinâmico da empresa...');

        // Elementos do preview
        const previewElements = {
            nome: $('#preview-nome'),
            subdomain: $('#preview-subdomain'),
            tipo: $('#preview-tipo'),
            email: $('#preview-email'),
            endereco: $('#preview-endereco'),
            categoria: $('#preview-categoria'),
            status: $('#preview-status'),
            icon: $('#preview-icon')
        };

        // Verificar se os elementos existem
        if (previewElements.nome.length === 0) {
            // Apenas log se for página de wizard (já detectada) e estiver faltando estrutura
            const isWizardPage = $('.wizard-form, [data-wizard="true"], #wizard-container').length > 0;
            if (isWizardPage) {
                console.warn('⚠️ Estrutura de preview ausente em página marcada como wizard. (IDs preview-*)');
            }
            return;
        }

        // Função para atualizar o preview
        function updatePreview() {
            console.log('🔄 Atualizando preview da empresa...');

            // Coletar dados dos formulários ativos
            const formData = collectFormData();

            // Atualizar nome da empresa
            if (formData.name) {
                previewElements.nome.text(formData.name);
                previewElements.subdomain.text(formData.subdomain ? `${formData.subdomain}.pandora.com` : 'Defina um subdomínio');
            }

            // Atualizar tipo de pessoa
            if (formData.tipo_pessoa) {
                const tipoTexto = formData.tipo_pessoa === 'PJ' ? 'Pessoa Jurídica' : 'Pessoa Física';
                previewElements.tipo.text(tipoTexto);
                previewElements.categoria.text(formData.tipo_pessoa === 'PJ' ? 'Empresa' : 'Pessoa');

                // Atualizar ícone
                const iconClass = formData.tipo_pessoa === 'PJ' ? 'fas fa-building' : 'fas fa-user';
                previewElements.icon.attr('class', `${iconClass} fa-2x text-primary`);
            }

            // Atualizar email
            if (formData.email) {
                previewElements.email.text(formData.email);
            }

            // Atualizar endereço
            if (formData.cidade || formData.uf) {
                const enderecoTexto = `${formData.cidade || ''}${formData.cidade && formData.uf ? '/' : ''}${formData.uf || ''}`;
                previewElements.endereco.text(enderecoTexto || 'Endereço não informado');
            }

            console.log('✅ Preview atualizado:', formData);
        }

        // Função para coletar dados dos formulários
        function collectFormData() {
            const data = {};

            // Detectar tipo de pessoa dos radio buttons
            const tipoRadioChecked = $('input[name="tipo_pessoa"]:checked');
            if (tipoRadioChecked.length > 0) {
                data.tipo_pessoa = tipoRadioChecked.val();
                console.log('🔍 Tipo pessoa detectado via radio:', data.tipo_pessoa);
            }

            // Coletar dados baseado no tipo de pessoa usando IDs com prefixos
            if (data.tipo_pessoa === 'PJ') {
                // Dados PJ com suporte a IDs com hífen e underscore
                const nameField = $('#id_pj-name, #id_pj_name, #id_pj-razao_social, #id_pj_razao_social').first();
                const emailField = $('#id_pj-email, #id_pj_email').first();
                if (nameField.length) data.name = nameField.val();
                if (emailField.length) data.email = emailField.val();
            } else if (data.tipo_pessoa === 'PF') {
                // Dados PF com suporte a IDs com hífen e underscore
                const nameField = $('#id_pf-name, #id_pf_name').first();
                const emailField = $('#id_pf-email, #id_pf_email').first();
                if (nameField.length) data.name = nameField.val();
                if (emailField.length) data.email = emailField.val();
            } else {
                // Fallback para campos gerais
                const nameField = $('[name*="name"], [name*="nome"]').first();
                const emailField = $('[name*="email"]').not('[name*="admin"]').first();

                if (nameField.length) data.name = nameField.val();
                if (emailField.length) data.email = emailField.val();
            }

            // Dados gerais (independente do tipo)
            const subdomainField = $('[name*="subdomain"]').first();
            const cidadeField = $('[name*="cidade"]').first();
            const ufField = $('[name*="uf"], [name*="estado"]').first();

            if (subdomainField.length) data.subdomain = subdomainField.val();
            if (cidadeField.length) data.cidade = cidadeField.val();
            if (ufField.length) data.uf = ufField.val();

            console.log('📊 Dados coletados:', data);
            return data;
        }

        // Listeners para atualização em tempo real
        $(document).on('input change blur', [
            // Campos gerais
            '[name*="name"]',
            '[name*="nome"]',
            '[name*="razao_social"]',
            '[name*="nome_fantasia"]',
            '[name*="subdomain"]',
            '[name*="email"]',
            '[name*="cidade"]',
            '[name*="uf"]',
            '[name*="estado"]',
            // IDs únicos PJ
            '#id_pj_name',
            '#id_pj-name',
            '#id_pj_email',
            '#id_pj-email',
            '#id_pj_telefone',
            '#id_pj-telefone',
            // IDs únicos PF
            '#id_pf_name',
            '#id_pf-name',
            '#id_pf_email',
            '#id_pf-email',
            '#id_pf_telefone',
            '#id_pf-telefone',
            // Radio buttons tipo pessoa
            'input[name="tipo_pessoa"]'
        ].join(', '), function () {
            // Debounce para evitar muitas atualizações
            clearTimeout(window.previewUpdateTimeout);
            window.previewUpdateTimeout = setTimeout(updatePreview, 300);
        });

        // Atualização inicial
        setTimeout(updatePreview, 1000);

        // Expor função globalmente para uso em outros scripts
        window.updateWizardPreview = updatePreview;

        console.log('✅ Preview dinâmico inicializado');
    }

    // Inicialização completa removida - implementada no template

})(jQuery);
