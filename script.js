document.addEventListener('DOMContentLoaded', () => {
    // --- VARIÁVEIS GLOBAIS ---
    const API_URL = 'http://127.0.0.1:5001/api';
    let currentUser = null;
    let allTasks = []; 
    let currentFilter = 'all';
    let currentCategoryFilter = 'all';
    let editTaskModal, commentsModal, confirmationModal, forceResetModal, adminUserEditModal;
    let quickAddTaskModal; 
    let assignCategoriesModal;
    let manageCategoryUsersModal;
    
    // --- ATUALIZAÇÃO DE SEGURANÇA: Novos Modais ---
    let login2faModal; // Modal para pedir o código 2FA
    let setup2faModal; // Modal para mostrar o QR Code de configuração
    let disable2faModal; // Modal para confirmar a desativação do 2FA
    
    // --- ATUALIZAÇÃO DE SEGURANÇA: Variável para o fluxo de login ---
    let loginUsernameCache = ''; // Armazena o username durante o pedido 2FA

    // --- SELETORES DO DOM ---
    const authContainer = document.querySelector('.auth-container');
    const appContainer = document.querySelector('.app-container');
    const mainContent = document.getElementById('main-content');
    
    const impersonationBanner = document.getElementById('impersonation-banner');
    const impersonationUsername = document.getElementById('impersonation-username');


    // --- ================================== ---
    // --- ATUALIZAÇÃO: Helpers de Segurança (Frontend)
    // --- ================================== ---
    
    /**
     * Valida a força da senha no frontend para feedback imediato.
     * @param {string} password - A senha a ser verificada.
     * @returns {object} - { strong: boolean, message: string }
     */
    function validatePasswordStrength(password) {
        if (password.length < 8) {
            return { strong: false, message: "A senha deve ter pelo menos 8 caracteres." };
        }
        if (!/[A-Z]/.test(password)) {
            return { strong: false, message: "Deve conter pelo menos uma letra maiúscula." };
        }
        if (!/[a-z]/.test(password)) {
            return { strong: false, message: "Deve conter pelo menos uma letra minúscula." };
        }
        if (!/[0-9]/.test(password)) {
            return { strong: false, message: "Deve conter pelo menos um número." };
        }
        if (!/[\W_]/.test(password)) { // \W é qualquer não-palavra (símbolo)
            return { strong: false, message: "Deve conter pelo menos um caractere especial." };
        }
        return { strong: true, message: "Senha forte." };
    }
    
    /**
     * Valida o formato do e-mail no frontend.
     * @param {string} email - O e-mail a ser verificado.
     * @returns {boolean}
     */
    function validateEmailFormat(email) {
        const pattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        return pattern.test(email);
    }
    
    /**
     * Mostra os requisitos de senha no formulário de registro.
     * @param {HTMLElement} errorElement - O elemento <div> para exibir os erros.
     * @param {string} password - A senha atual.
     */
    function showPasswordRequirements(errorElement, password) {
        let messages = [];
        if (password.length < 8) messages.push("Pelo menos 8 caracteres.");
        if (!/[A-Z]/.test(password)) messages.push("Pelo menos 1 letra maiúscula (A-Z).");
        if (!/[a-z]/.test(password)) messages.push("Pelo menos 1 letra minúscula (a-z).");
        if (!/[0-9]/.test(password)) messages.push("Pelo menos 1 número (0-9).");
        if (!/[\W_]/.test(password)) messages.push("Pelo menos 1 símbolo (ex: !@#$).");

        if (messages.length > 0) {
            errorElement.innerHTML = "A senha deve ter:<br> - " + messages.join("<br> - ");
            errorElement.style.color = 'var(--error-color)';
        } else {
            errorElement.textContent = "✓ Senha forte!";
            errorElement.style.color = 'var(--success-color)';
        }
    }
    // --- Fim dos Helpers de Segurança ---


    // --- AUTENTICAÇÃO / FORM SWITCH ---
    const showSection = (sectionToShow) => {
        [document.getElementById('login-section'), document.getElementById('registration-section'), document.getElementById('forgot-password-section')].forEach(s => s.style.display = 'none');
        sectionToShow.style.display = 'block';
    };
    document.getElementById('show-register').addEventListener('click', (e) => { e.preventDefault(); showSection(document.getElementById('registration-section')); });
    document.getElementById('show-login').addEventListener('click', (e) => { e.preventDefault(); showSection(document.getElementById('login-section')); });
    document.getElementById('show-forgot-password').addEventListener('click', (e) => { e.preventDefault(); showSection(document.getElementById('forgot-password-section')); });
    document.getElementById('show-login-from-forgot').addEventListener('click', (e) => { e.preventDefault(); showSection(document.getElementById('login-section')); });

    // Registro (ATUALIZADO COM VALIDAÇÃO)
    try {
        // Feedback de senha em tempo real
        const regPassInput = document.getElementById('register-password');
        const regErrEl = document.getElementById('register-error');
        if (regPassInput) {
            regPassInput.addEventListener('input', (e) => {
                showPasswordRequirements(regErrEl, e.target.value);
            });
        }
        
        document.getElementById('register-form').elements.role.forEach(radio => {
            radio.addEventListener('change', (e) => {
                const isAdmin = e.target.value === 'admin';
                document.getElementById('admin-fields').style.display = isAdmin ? 'block' : 'none';
                document.getElementById('employee-fields').style.display = isAdmin ? 'none' : 'block';
                // --- ATUALIZAÇÃO: Admin também precisa de e-mail ---
                document.getElementById('admin-key').required = isAdmin;
                document.getElementById('register-email').required = !isAdmin;
                document.getElementById('admin-email').required = isAdmin;
            });
        });
    } catch(e) { /* form might differ per deployment; ignore safely */ }

    document.getElementById('register-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const err = document.getElementById('register-error');
        err.textContent = '';
        
        const role = e.target.elements.role.value;
        // --- ATUALIZAÇÃO: Pega o e-mail do campo correto ---
        const email = (role === 'admin') 
            ? document.getElementById('admin-email').value.trim()
            : document.getElementById('register-email').value.trim();
            
        const password = e.target.elements['register-password'].value;
        
        // --- ATUALIZAÇÃO: Validação de Frontend ---
        if (!validateEmailFormat(email)) {
            err.textContent = 'O formato do e-mail é inválido.';
            return;
        }
        const passCheck = validatePasswordStrength(password);
        if (!passCheck.strong) {
            err.textContent = `Senha fraca: ${passCheck.message}`;
            return;
        }
        // --- Fim da Validação ---
        
        const fd = {
            username: e.target.elements['register-username'].value.trim(),
            password: password,
            role: role,
            email: email,
            job_title: document.getElementById('register-job-title').value.trim(),
            adminKey: document.getElementById('admin-key').value,
            consent: e.target.elements['register-consent'].checked
        };
        try {
            const res = await fetch(`${API_URL}/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(fd)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Erro ao registrar');
            
            // --- ATUALIZAÇÃO: Mensagem de Verificação de E-mail ---
            alert('Usuário registrado com sucesso! Se o sistema estiver em modo de produção, um e-mail de verificação será enviado.');
            // --- Fim da Atualização ---
            
            showSection(document.getElementById('login-section'));
            e.target.reset();
        } catch (error) {
            err.textContent = error.message;
        }
    });

    // Login (ATUALIZADO COM FLUXO 2FA)
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const err = document.getElementById('login-error');
        const username = e.target.elements.username.value;
        const password = e.target.elements.password.value;
        err.textContent = '';
        
        try {
            const res = await fetch(`${API_URL}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const data = await res.json();
            
            if (!res.ok) {
                 // Erros 4xx (senha errada, usuário não encontrado, e-mail não verificado)
                throw new Error(data.error || 'Erro ao logar');
            }

            // --- ATUALIZAÇÃO: Fluxo 2FA ---
            if (data.user && data.user.needsPasswordReset) {
                // 1. Caso: Reset de Senha Forçado
                currentUser = data.user;
                initializeModalsAndChat(); // Garante que o modal está pronto
                forceResetModal.show();
            
            } else if (data['2fa_required']) {
                // 2. Caso: 2FA é necessário
                loginUsernameCache = username; // Salva o username
                initializeModalsAndChat(); // Garante que o modal 2FA está pronto
                document.getElementById('login-2fa-error').textContent = '';
                document.getElementById('login-2fa-form').reset();
                login2faModal.show(); // Mostra o modal pedindo o código
            
            } else {
                // 3. Caso: Login direto (bem-sucedido)
                startSession(data.user);
            }
            // --- Fim da Atualização ---
            
        } catch (error) {
            err.textContent = error.message;
        }
    });
    
    // --- ATUALIZAÇÃO: Novo Handler para o Modal 2FA ---
    try {
        document.getElementById('login-2fa-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const err = document.getElementById('login-2fa-error');
            const code = document.getElementById('login-2fa-code').value;
            err.textContent = '';
            
            if (!loginUsernameCache) {
                 err.textContent = 'Erro de sessão. Por favor, tente logar novamente.';
                 return;
            }
            
            try {
                const res = await fetch(`${API_URL}/login/2fa`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: loginUsernameCache, totp_code: code })
                });
                const data = await res.json();
                
                if (!res.ok) {
                     throw new Error(data.error || 'Erro ao verificar código 2FA');
                }
                
                // Sucesso!
                login2faModal.hide();
                loginUsernameCache = ''; // Limpa o cache
                startSession(data.user); // Inicia a sessão
                
            } catch (error) {
                err.textContent = error.message;
            }
        });
    } catch(e) { /* ok */ }

    // Forgot password (sem alterações)
    document.getElementById('forgot-password-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fb = document.getElementById('forgot-feedback');
        fb.textContent = '';
        fb.classList.remove('text-success');
        try {
            const res = await fetch(`${API_URL}/forgot-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: e.target.elements['forgot-email'].value })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Erro ao recuperar senha');
            fb.textContent = data.message;
            fb.classList.add('text-success');
            
        } catch (error) {
            fb.textContent = error.message;
        }
    });

    // Force reset form (ATUALIZADO COM VALIDAÇÃO)
    try {
        const resetPassInput = document.getElementById('reset-new-password');
        const resetErrEl = document.getElementById('force-reset-error');
        if(resetPassInput) {
            // Mostra requisitos em tempo real
            resetPassInput.addEventListener('input', (e) => {
                showPasswordRequirements(resetErrEl, e.target.value);
            });
        }
    
        document.getElementById('force-reset-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const err = document.getElementById('force-reset-error');
            const newPass = document.getElementById('reset-new-password').value;
            const confPass = document.getElementById('reset-confirm-password').value;
            err.textContent = '';
            
            // --- ATUALIZAÇÃO: Validação de Frontend ---
            const passCheck = validatePasswordStrength(newPass);
            if (!passCheck.strong) {
                err.textContent = `Senha fraca: ${passCheck.message}`;
                return;
            }
            // --- Fim da Validação ---
            
            if (newPass !== confPass) { err.textContent = 'As senhas não coincidem.'; return; }
            
            try {
                const res = await fetch(`${API_URL}/user/reset-password`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ userId: currentUser.id, newPassword: newPass })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Erro ao resetar senha');
                alert('Senha atualizada com sucesso!');
                forceResetModal.hide();
                if (currentUser.impersonating) {
                    localStorage.removeItem('originalAdminSession');
                }
                currentUser.needsPasswordReset = false;
                startSession(currentUser);
            } catch (error) {
                err.textContent = error.message;
            }
        });
    } catch(e) { /* ok if modal not present */ }

    // --- SESSÃO (sem alterações) ---
    function startSession(user) {
        currentUser = user;
        authContainer.style.display = 'none';
        appContainer.style.display = 'flex';
        document.getElementById('chat-container').style.display = 'block';
        document.getElementById('header-username').textContent = currentUser.username;
        
        const isAdmin = currentUser.role === 'admin';
        document.getElementById('quick-add-task-btn').style.display = (currentUser) ? 'flex' : 'none';
        
        const navLogout = document.getElementById('nav-logout');
        
        if (currentUser.impersonating) {
            impersonationBanner.style.display = 'flex';
            impersonationUsername.textContent = currentUser.username;
            navLogout.innerHTML = `<a href="#"><i class="bi bi-box-arrow-in-right"></i><span>Retornar ao Admin</span></a>`;
            document.getElementById('nav-activity-log').style.display = 'none';
            document.getElementById('nav-ssap').style.display = 'none';
            document.getElementById('nav-dpo').style.display = 'none';
            if (document.getElementById('nav-categories')) { 
                document.getElementById('nav-categories').style.display = 'none'; 
            } 
        } else {
            impersonationBanner.style.display = 'none';
            navLogout.innerHTML = `<a href="#"><i class="bi bi-box-arrow-left"></i><span>Sair</span></a>`;
            document.getElementById('nav-activity-log').style.display = isAdmin ? 'list-item' : 'none';
            document.getElementById('nav-ssap').style.display = isAdmin ? 'list-item' : 'none';
            document.getElementById('nav-dpo').style.display = isAdmin ? 'list-item' : 'none';
            if (document.getElementById('nav-categories')) { 
                document.getElementById('nav-categories').style.display = isAdmin ? 'list-item' : 'none'; 
            } 
        }
        
        setupEventListeners();
        renderView('dashboard');
        initializeNotificationState(); 
        updateDpoBadge();
    }
    
    function logout() {
        if (currentUser && currentUser.impersonating) {
            const adminSessionStr = localStorage.getItem('originalAdminSession');
            localStorage.removeItem('originalAdminSession');
            if (adminSessionStr) {
                const adminSession = JSON.parse(adminSessionStr);
                startSession(adminSession);
            } else {
                performFullLogout();
            }
        } else {
            performFullLogout();
        }
    }
    
    function performFullLogout() {
        currentUser = null; 
        allTasks = [];
        localStorage.removeItem('originalAdminSession'); 
        appContainer.style.display = 'none';
        mainContent.innerHTML = '';
        document.getElementById('chat-container').style.display = 'none';
        authContainer.style.display = 'flex';
        showSection(document.getElementById('login-section'));
        document.getElementById('login-form').reset();
    }

    // --- EVENT LISTENERS GERAIS (sem alterações) ---
    function setupEventListeners() {
        const oldToggle = document.getElementById('sidebar-toggle');
        if (oldToggle && oldToggle.parentNode) {
            const newToggle = oldToggle.cloneNode(true);
            oldToggle.parentNode.replaceChild(newToggle, oldToggle);
            newToggle.addEventListener('click', () => {
                document.body.classList.toggle('sidebar-collapsed');
            });
        }

        const oldLogout = document.getElementById('nav-logout');
        if (oldLogout && oldLogout.parentNode) {
            const newLogout = oldLogout.cloneNode(true);
            oldLogout.parentNode.replaceChild(newLogout, oldLogout);
            newLogout.addEventListener('click', logout);
        }
        
        const oldStopImpersonation = document.getElementById('stop-impersonation-btn');
        if (oldStopImpersonation && oldStopImpersonation.parentNode) {
            const newStopImpersonation = oldStopImpersonation.cloneNode(true);
            oldStopImpersonation.parentNode.replaceChild(newStopImpersonation, oldStopImpersonation);
            newStopImpersonation.addEventListener('click', logout);
        }

        const oldUserInfo = document.getElementById('header-user-info');
        if (oldUserInfo && oldUserInfo.parentNode) {
            const newUserInfo = oldUserInfo.cloneNode(true);
            oldUserInfo.parentNode.replaceChild(newUserInfo, oldUserInfo);
            newUserInfo.addEventListener('click', () => {
                renderView('profile');
            });
        }

        const oldQuickAddBtn = document.getElementById('quick-add-task-btn');
        if (oldQuickAddBtn && oldQuickAddBtn.parentNode) {
            const newQuickAddBtn = oldQuickAddBtn.cloneNode(true);
            oldQuickAddBtn.parentNode.replaceChild(newQuickAddBtn, oldQuickAddBtn);
            newQuickAddBtn.addEventListener('click', handleOpenQuickAddModal);
        }

        document.querySelectorAll('#sidebar .components li').forEach(item => {
            if (item && item.parentNode) {
                const newItem = item.cloneNode(true);
                item.parentNode.replaceChild(newItem, item);
                newItem.addEventListener('click', (e) => {
                    e.preventDefault();
                    const view = newItem.getAttribute('data-view');
                    if (view) renderView(view);
                });
            }
        });
    }

    // --- RENDERIZAÇÃO DE VIEWS (sem alterações) ---
    function renderView(viewName) {
        document.querySelector('#sidebar .components li.active')?.classList.remove('active');
        document.querySelector(`#sidebar .components li[data-view="${viewName}"]`)?.classList.add('active');
        
        const searchContainer = document.getElementById('header-search-container');
        searchContainer.style.display = (viewName === 'dashboard') ? 'block' : 'none';

        if (viewName === 'dpo') {
            const dpoBadge = document.getElementById('dpo-notification-badge');
            if(dpoBadge) dpoBadge.style.display = 'none';
        } else {
            updateDpoBadge();
        }

        if (viewName === 'dashboard') renderDashboardView();
        else if (viewName === 'analytics') renderAnalyticsView();
        else if (viewName === 'profile') renderProfileView();
        else if (viewName === 'team') renderTeamView();
        else if (viewName === 'log') renderActivityLogView();
        else if (viewName === 'ssap') renderSSAPView(); 
        else if (viewName === 'categories') renderCategoryManagementView(); 
        else if (viewName === 'dpo') renderDpoView();
    }

    // --- PROFILE VIEW (ATUALIZADO COM SEÇÃO 2FA) ---
    async function renderProfileView() {
        mainContent.innerHTML = `
            <div class="content-header"><h2>Meu Perfil</h2></div>
            <div class="row">
                <div class="col-lg-7">
                    <div class="card mb-4"><div class="card-header"><h5 class="mb-0">Detalhes do Perfil</h5></div>
                    <div class="card-body">
                        <form id="profile-form">
                            <div class="mb-3"><label for="profile-username" class="form-label">Nome de Usuário</label><input type="text" class="form-control" id="profile-username" required></div>
                            <div class="mb-3"><label for="profile-email" class="form-label">E-mail</label><input type="email" class="form-control" id="profile-email" required></div>
                            <div class="mb-3"><label for="profile-job-title" class="form-label">Cargo</label><input type="text" class="form-control" id="profile-job-title" placeholder="Ex: Desenvolvedor Jr."></div>
                            <div id="profile-error" class="error-message"></div>
                            <div id="profile-success" class="text-success mb-2"></div>
                            <button type="submit" class="btn btn-primary" ${currentUser.impersonating ? 'disabled' : ''}>Salvar Alterações</button>
                            ${currentUser.impersonating ? '<p class="text-danger small mt-2">Você não pode editar um perfil enquanto estiver impersonando.</p>' : ''}
                        </form>
                    </div></div>

                    <div class="card"><div class="card-header"><h5 class="mb-0">Alterar Senha</h5></div>
                    <div class="card-body">
                        <form id="change-password-form">
                            <div class="mb-3"><label for="old-password" class="form-label">Senha Antiga</label><input type="password" class="form-control" id="old-password" required></div>
                            <div class="mb-3"><label for="new-password" class="form-label">Nova Senha</label><input type="password" class="form-control" id="new-password" required></div>
                            <div class="mb-3"><label for="confirm-password" class="form-label">Confirmar Nova Senha</label><input type="password" class="form-control" id="confirm-password" required></div>
                            <div id="password-error" class="error-message"></div>
                            <div id="password-success" class="text-success mb-2"></div>
                            <button type="submit" class="btn btn-primary" ${currentUser.impersonating ? 'disabled' : ''}>Alterar Senha</button>
                            ${currentUser.impersonating ? '<p class="text-danger small mt-2">Você não pode alterar a senha enquanto estiver impersonando.</p>' : ''}
                        </form>
                    </div></div>
                </div>

                <div class="col-lg-5">
                    <div class="card mb-4"><div class="card-header"><h5 class="mb-0">Minhas Estatísticas</h5></div>
                    <div class="card-body">
                        <div class="stat-item-wrapper">
                            <div class="stat-item"><div id="stat-my-completed" class="stat-item-number success">0</div><div class="stat-item-label">Concluídas</div></div>
                            <div class="stat-item"><div id="stat-my-pending" class="stat-item-number pending">0</div><div class="stat-item-label">Pendentes</div></div>
                            <div class="stat-item"><div id="stat-my-overdue" class="stat-item-number danger">0</div><div class="stat-item-label">Atrasadas</div></div>
                        </div>
                    </div></div>

                    <div class="card mb-4">
                        <div class="card-header"><h5 class="mb-0">Segurança (2FA)</h5></div>
                        <div class="card-body" id="security-2fa-card-body">
                            <div class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div></div>
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header"><h5 class="mb-0">Central de Privacidade (LGPD)</h5></div>
                        <div class="card-body">
                            <p class="text-muted small">Use este formulário para enviar uma solicitação formal ao nosso Encarregado de Proteção de Dados (DPO).</p>
                            <form id="dpo-request-form">
                                <div class="mb-3"><label for="dpo-request-type" class="form-label">Tipo de Solicitação</label><select id="dpo-request-type" class="form-select" required><option value="">Selecione...</option><option value="access">Solicitar cópia dos meus dados</option><option value="correction">Solicitar correção de dados</option><option value="anonymization">Solicitar exclusão</option><option value="question">Dúvida geral sobre privacidade</option></select></div>
                                <div class="mb-3"><label for="dpo-request-message" class="form-label">Mensagem</label><textarea id="dpo-request-message" class="form-control" rows="4" placeholder="Detalhe sua solicitação aqui..." required></textarea></div>
                                <button type="submit" class="btn btn-outline-primary w-100">Enviar para o DPO</button>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-lg-7 mt-4">
                    <div class="card">
                        <div class="card-header"><h5 class="mb-0">Minhas Solicitações DPO</h5></div>
                        <div class="card-body">
                            <div id="my-dpo-requests-list" style="max-height: 400px; overflow-y: auto;">
                                <div class="text-center p-3"><div class="spinner-border spinner-border-sm text-primary" role="status"></div></div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-lg-5 mt-4">
                     ${currentUser.role === 'funcionario' ? `
                    <div class="card">
                        <div class="card-header"><h5 class="mb-0">Meu Histórico de Conclusões</h5></div>
                        <div class="card-body">
                            <p class="text-muted small">Suas 100 últimas tarefas concluídas.</p>
                            <div id="user-activity-log-container">
                                <div class="text-center p-3"><div class="spinner-border spinner-border-sm text-primary" role="status"></div></div>
                            </div>
                        </div>
                    </div>
                    ` : ''}
                </div>

                <div class="col-12 mt-4">
                    <div class="card border-danger">
                        <div class="card-header bg-danger text-white"><h5 class="mb-0">Zona de Perigo</h5></div>
                        <div class="card-body">
                            <p class="text-muted">Esta ação (exclusão) iniciará uma solicitação formal ao DPO. Sua conta será agendada para exclusão em 7 dias. Esta ação, após executada pelo DPO, não pode ser desfeita.</p>
                            <button id="delete-account-btn" class="btn btn-danger" ${currentUser.impersonating ? 'disabled' : ''}>
                                Solicitar Exclusão da Minha Conta
                            </button>
                            ${currentUser.impersonating ? '<p class="text-danger small mt-2">Ações de exclusão estão desabilitadas during a impersonação.</p>' : ''}
                        </div>
                    </div>
                </div>
            </div>`;
            
        // --- Lógica das Novas Features ---
        // 1. Calcular Minhas Estatísticas
        if (allTasks.length > 0) {
            const myTasks = allTasks.filter(t => t.assigned_to_id === currentUser.id);
            const completed = myTasks.filter(t => t.completed).length;
            const pending = myTasks.length - completed;
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            const overdue = myTasks.filter(t => !t.completed && t.due_date && new Date(t.due_date + 'T00:00:00') < today).length;

            document.getElementById('stat-my-completed').textContent = completed;
            document.getElementById('stat-my-pending').textContent = pending;
            document.getElementById('stat-my-overdue').textContent = overdue;
        }
        
        // 2. Adicionar Listener do Formulário DPO
        document.getElementById('dpo-request-form').addEventListener('submit', handleDpoRequest);
        
        // 3. Carregar dados do perfil (agora inclui 2FA)
        loadProfileData();

        // Listeners dos formulários (lógica original)
        document.getElementById('profile-form').addEventListener('submit', handleProfileUpdate);
        
        // ATUALIZAÇÃO: Adiciona feedback de senha em tempo real
        const newPassInput = document.getElementById('new-password');
        const passErrEl = document.getElementById('password-error');
        if (newPassInput) {
            newPassInput.addEventListener('input', (e) => {
                showPasswordRequirements(passErrEl, e.target.value);
            });
        }
        document.getElementById('change-password-form').addEventListener('submit', handleChangePassword);
        
        // Listener do botão de exclusão (agora solicitação)
        document.getElementById('delete-account-btn').addEventListener('click', handleDeleteSelfAccount);

        loadMyDpoRequests();
        
        if (currentUser.role === 'funcionario') {
            loadMyActivityLog();
        }
    }
    
    // --- ATUALIZAÇÃO: Nova Função para Carregar Dados do Perfil (inclui 2FA) ---
    async function loadProfileData() {
        try {
            const response = await fetch(`${API_URL}/user/${currentUser.id}`);
            if (!response.ok) throw new Error('Não foi possível carregar os dados do perfil.');
            const userData = await response.json();
            
            // 1. Preenche o formulário de perfil
            document.getElementById('profile-username').value = userData.username;
            document.getElementById('profile-email').value = userData.email;
            document.getElementById('profile-job-title').value = userData.job_title || '';
            
            // 2. Atualiza o card de segurança 2FA
            render2faCard(userData.is_totp_enabled);
            
        } catch(error) {
            document.getElementById('profile-error').textContent = error.message;
        }
    }

    // --- ATUALIZAÇÃO: Nova Função para Renderizar o Card 2FA ---
    function render2faCard(is2faEnabled) {
        const container = document.getElementById('security-2fa-card-body');
        if (currentUser.impersonating) {
            container.innerHTML = '<p class="text-danger small">A configuração de segurança está desabilitada durante a impersonação.</p>';
            return;
        }
        
        if (is2faEnabled) {
            // 2FA Está ATIVADO
            container.innerHTML = `
                <div class="d-flex align-items-center">
                    <i class="bi bi-shield-check text-success" style="font-size: 2rem; margin-right: 15px;"></i>
                    <div>
                        <h6 class="mb-0">2FA está ATIVADO</h6>
                        <p class="small text-muted mb-0">Sua conta está protegida com um parâmetro extra de login.</p>
                    </div>
                </div>
                <button id="disable-2fa-btn" class="btn btn-outline-danger w-100 mt-3">Desativar 2FA</button>
            `;
            container.querySelector('#disable-2fa-btn').addEventListener('click', () => {
                 initializeModalsAndChat(); // Garante que o modal está pronto
                 document.getElementById('disable-2fa-form').reset();
                 document.getElementById('disable-2fa-error').textContent = '';
                 disable2faModal.show();
            });
            
        } else {
            // 2FA Está DESATIVADO
            container.innerHTML = `
                <div class="d-flex align-items-center">
                    <i class="bi bi-shield-exclamation text-warning" style="font-size: 2rem; margin-right: 15px;"></i>
                    <div>
                        <h6 class="mb-0">2FA está DESATIVADO</h6>
                        <p class="small text-muted mb-0">Proteja sua conta com um aplicativo autenticador.</p>
                    </div>
                </div>
                <button id="enable-2fa-btn" class="btn btn-primary w-100 mt-3">Ativar 2FA</button>
            `;
            container.querySelector('#enable-2fa-btn').addEventListener('click', handleEnable2FA);
        }
    }

    // --- ATUALIZAÇÃO: Handler de Update de Perfil (com validação) ---
    async function handleProfileUpdate(e) {
        e.preventDefault();
        if (currentUser.impersonating) return;
        
        const errorEl = document.getElementById('profile-error');
        const successEl = document.getElementById('profile-success');
        errorEl.textContent = '';
        successEl.textContent = '';
        
        const email = document.getElementById('profile-email').value.trim();
        // Validação
        if (!validateEmailFormat(email)) {
            errorEl.textContent = 'O formato do e-mail é inválido.';
            return;
        }
        
        const updatedData = {
            username: document.getElementById('profile-username').value.trim(),
            email: email,
            job_title: document.getElementById('profile-job-title').value.trim(),
            acting_user_id: currentUser.id 
        };
        try {
            const response = await fetch(`${API_URL}/user/${currentUser.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updatedData)
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Erro ao atualizar perfil');
            
            // Atualiza o currentUser local com os novos dados
            currentUser.username = data.user.username;
            currentUser.email = data.user.email;
            currentUser.jobTitle = data.user.job_title;
            
            document.getElementById('header-username').textContent = currentUser.username;
            successEl.textContent = 'Perfil atualizado com sucesso!';
        } catch (error) {
            errorEl.textContent = error.message;
        }
    }
    
    // --- ATUALIZAÇÃO: Handler de Mudar Senha (com validação) ---
    async function handleChangePassword(e) {
        e.preventDefault();
        if (currentUser.impersonating) return;

        const errorEl = document.getElementById('password-error');
        const successEl = document.getElementById('password-success');
        errorEl.textContent = '';
        successEl.textContent = '';
        const oldPassword = document.getElementById('old-password').value;
        const newPassword = document.getElementById('new-password').value;
        const confirmPassword = document.getElementById('confirm-password').value;
        
        // Validação
        const passCheck = validatePasswordStrength(newPassword);
        if (!passCheck.strong) {
            errorEl.innerHTML = `Senha fraca:<br>${passCheck.message.replace(/\./g, '.<br>')}`;
            return;
        }
        
        if (newPassword !== confirmPassword) {
            errorEl.textContent = 'As novas senhas não coincidem.';
            return;
        }
        try {
            const response = await fetch(`${API_URL}/user/change-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ userId: currentUser.id, oldPassword, newPassword })
            });
            const data = await response.json(); 
            if (!response.ok) throw new Error(data.error || 'Erro ao alterar senha');
            successEl.textContent = data.message;
            e.target.reset();
        } catch (error) {
            errorEl.textContent = error.message;
        }
    }
    
    
    // --- (Funções DPO, Exclusão, Dashboard, etc. permanecem aqui, sem alterações) ---
    async function handleDpoRequest(e) {
        e.preventDefault();
        const requestType = document.getElementById('dpo-request-type').value;
        const message = document.getElementById('dpo-request-message').value;
        try {
            const response = await fetch(`${API_URL}/dpo-request`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    acting_user_id: currentUser.id,
                    request_type: requestType,
                    message_text: message
                })
            });
            const data = await response.json(); 
            if (!response.ok) throw new Error(data.error || 'Erro ao enviar solicitação.');
            
            alert(data.message); 
            e.target.reset();
            loadMyDpoRequests(); 

        } catch (error) {
            alert(`Erro: ${error.message}`);
        }
    }
    function handleDeleteSelfAccount(e) {
        if (currentUser.impersonating) return;
        const confirmationText = 'Você confirma a SOLICITAÇÃO de exclusão da sua conta? Esta ação é permanente e será agendada para 7 dias.';
        document.getElementById('confirmation-modal-body').textContent = confirmationText;
        const confirmBtn = document.getElementById('confirm-action-btn');
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        newConfirmBtn.addEventListener('click', async () => {
            try {
                const res = await fetch(`${API_URL}/user/delete-self`, { 
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: currentUser.id })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Não foi possível solicitar a exclusão.');
                confirmationModal.hide();
                alert(data.message || 'Solicitação de exclusão registrada com sucesso.');
                loadMyDpoRequests(); 
            } catch (err) {
                alert(err.message);
                confirmationModal.hide();
            }
        }, { once: true });
        confirmationModal.show();
    }
    async function renderDashboardView() {
        const searchContainer = document.getElementById('header-search-container');
        searchContainer.innerHTML = `<input type="search" id="task-search-input" class="form-control" placeholder="🔍 Buscar tarefas...">`;
        document.getElementById('task-search-input').addEventListener('input', renderTasks);
        const isAdminView = (currentUser.role === 'admin' && !currentUser.impersonating);
        mainContent.innerHTML = `
            <div class="content-header">
                <h2>Dashboard de Tarefas</h2>
                <div class="d-flex flex-wrap gap-2" style="align-items: center;">
                    <div class.="flex-grow-1" style="min-width: 200px;">
                        <select id="category-filter-select" class="form-select">
                            <option value="all">Todas as Categorias</option>
                            <option value="none">Tarefas sem Categoria</option>
                            </select>
                    </div>
                    <div class="task-filters btn-group" role="group">
                        <button type="button" class="btn btn-outline-primary active" data-filter="all">Todas</button>
                        <button type="button" class="btn btn-outline-primary" data-filter="mine">Minhas Tarefas</button>
                        <button type="button" class="btn btn-outline-primary" data-filter="overdue">Atrasadas</button>
                    </div>
                </div>
            </div>
            <div id="due-soon-container" class="due-soon-panel" style="display: none;">
                <h5><i class="bi bi-alarm-fill"></i>Vencendo em Breve</h5>
                <ul id="due-soon-list" class="due-soon-list"></ul>
            </div>
            <div id="add-task-card" class="card my-4" style="display: ${isAdminView ? 'block' : 'none'}">
                <div class="card-header bg-white py-3"><h5 class="mb-0 fw-bold">Adicionar Nova Tarefa</h5></div>
                <div class="card-body p-4"><form id="task-form"></form></div>
            </div>
            <div id="task-list" class="row gy-4"></div>`;
        mainContent.querySelector('.task-filters').addEventListener('click', handleFilterClick);
        mainContent.querySelector('#category-filter-select').addEventListener('change', handleCategoryFilterChange); 
        populateDashboardCategoryFilter(); 
        const taskForm = mainContent.querySelector('#task-form');
        if (taskForm) {
            taskForm.innerHTML = `
                <div class="row g-3">
                    <div class="col-md-12"><label class="form-label">Título</label><input type="text" id="task-title" class="form-control" required></div>
                    <div class="col-md-6"><label class="form-label">Descrição</label><textarea id="task-description" class="form-control" rows="3" required></textarea></div>
                    <div class="col-md-6">
                        <div class="row g-3">
                            <div class="col-12"><label class="form-label">Atribuir para:</label><select id="assign-to" class="form-select"><option value="">Ninguém</option></select></div>
                            <div class="col-12"><label class="form-label">Categoria:</label><select id="task-category" class="form-select"><option value="">Nenhuma Categoria</option></select></div>
                        </div>
                    </div>
                    <div class="col-md-6"><label class="form-label">Prioridade</label><select id="task-priority" class="form-select"><option value="3">Baixa</option><option value="2" selected>Média</option><option value="1">Alta</option></select></div>
                    <div class="col-md-6"><label class="form-label">Prazo</label><input type="date" id="task-due-date" class="form-control"></div>
                    <div class="col-12 text-end"><button type="submit" class="btn btn-success fw-semibold px-4">Salvar Tarefa</button></div>
                </div>`;
            if (isAdminView) {
                await Promise.all([
                    populateAssigneeDropdown(taskForm.querySelector('#assign-to')),
                    populateCategoryDropdown(taskForm.querySelector('#task-category'))
                ]);
                if (currentCategoryFilter !== 'all' && currentCategoryFilter !== 'none') {
                    taskForm.querySelector('#task-category').value = currentCategoryFilter;
                }
            }
            taskForm.addEventListener('submit', handleAddTask);
        }
        mainContent.querySelector('#task-list').addEventListener('click', handleTaskListClick);
        initializeModalsAndChat();
        fetchAndRenderTasks();
    }
    
    // ... (Analytics, Team, Log, SSAP, DueSoon, RenderTasks, etc. sem alterações)
    async function renderAnalyticsView() {
        mainContent.innerHTML = `
            <div class="content-header"><h2>Análise de Desempenho</h2></div>
            <div id="analytics-grid" class="analytics-grid">
                <div class="text-center p-5"><div class="spinner-border text-primary" role="status"></div></div>
            </div>`;
        try {
            const response = await fetch(`${API_URL}/analytics`);
            if (!response.ok) throw new Error('Não foi possível carregar os dados de análise.');
            const data = await response.json();
            document.getElementById('analytics-grid').innerHTML = `
                <div class="stat-card"><i class="bi bi-stack"></i><div class="stat-number">${data.totalTasks}</div><div class="stat-title">Total de Tarefas</div></div>
                <div class="stat-card"><i class="bi bi-hourglass-split" style="color: #ffc107;"></i><div class="stat-number">${data.pendingTasks}</div><div class="stat-title">Tarefas Pendentes</div></div>
                <div class="stat-card"><i class="bi bi-check2-circle" style="color: #198754;"></i><div class="stat-number">${data.completedTasks}</div><div class="stat-title">Tarefas Concluídas</div></div>
                <div class="stat-card"><i class="bi bi-calendar-x" style="color: #dc3545;"></i><div class="stat-number">${data.overdueTasks}</div><div class="stat-title">Tarefas Atrasadas</div></div>
                <div class="stat-card col-span-2"><i class="bi bi-person-check-fill" style="color: #0dcaf0;"></i><div class="stat-number">${data.topUser.username}</div><div class="stat-title">Top Funcionário (${data.topUser.task_count} tarefas)</div></div>`;
        } catch (error) {
             document.getElementById('analytics-grid').innerHTML = `<p class="text-danger">${error.message}</p>`;
        }
    }
    async function renderTeamView() {
        mainContent.innerHTML = `
            <div class="content-header"><h2>Membros da Equipe</h2></div>
            <div id="team-list" class="team-grid"><div class="text-center p-5"><div class="spinner-border text-primary" role="status"></div></div></div>`;
        try {
            const response = await fetch(`${API_URL}/users/employees`);
            if (!response.ok) throw new Error('Não foi possível carregar a lista de funcionários.');
            const employees = await response.json();
            const listEl = document.getElementById('team-list');
            listEl.innerHTML = '';
            if (employees.length === 0) { listEl.innerHTML = '<p class="text-muted">Nenhum funcionário encontrado.</p>'; return; }
            employees.forEach(emp => {
                listEl.innerHTML += `<div class="team-card"><div class="team-card-icon"><i class="bi bi-person"></i></div><div class="team-card-info"><p class="name">${emp.username}</p><p class="title">${emp.job_title || 'Funcionário'}</p><p class="email">${emp.email}</p></div></div>`;
            });
        } catch (error) {
            document.getElementById('team-list').innerHTML = `<p class="text-danger">${error.message}</p>`;
        }
    }
    async function renderActivityLogView() {
        mainContent.innerHTML = `
            <div class="content-header">
                <h2>Log de Atividades do Sistema</h2>
                <div class="btn-group" role="group">
                    <button id="purge-chat-btn" class="btn btn-warning text-dark">
                        <i class="bi bi-trash-fill"></i> Limpar Chat
                    </button>
                    <button id="purge-log-btn" class="btn btn-danger">
                        <i class="bi bi-shield-x"></i> Limpar Log de Atividades
                    </button>
                </div>
            </div>
            <div class="card">
                <div class="card-body">
                    <div id="activity-log-container" class="table-responsive">
                        <div class="text-center p-5"><div class="spinner-border text-primary" role="status"></div></div>
                    </div>
                </div>
            </div>`;
        document.getElementById('purge-chat-btn').addEventListener('click', handleAdminPurgeChat);
        document.getElementById('purge-log-btn').addEventListener('click', handleAdminPurgeLog);
        try {
            const response = await fetch(`${API_URL}/activity-log`);
            if (!response.ok) throw new Error('Não foi possível carregar o log de atividades.');
            const logs = await response.json();
            const container = document.getElementById('activity-log-container');
            if (logs.length === 0) {
                container.innerHTML = '<p class="text-muted text-center">Nenhuma atividade registrada.</p>';
                return;
            }
            let tableHtml = `
                <table class="table table-striped table-hover activity-log-table">
                    <thead class="table-light">
                        <tr>
                            <th scope="col">Usuário</th>
                            <th scope="col">Ação</th>
                            <th scope="col">Data e Hora</th>
                        </tr>
                    </thead>
                    <tbody>`;
            logs.forEach(log => {
                const timestamp = new Date(log.timestamp).toLocaleString('pt-BR');
                tableHtml += `
                    <tr>
                        <td><strong>${log.username || '[desconhecido]'}</strong></td>
                        <td>${log.action_text}</td>
                        <td class="text-muted small">${timestamp}</td>
                    </tr>`;
            });
            tableHtml += `</tbody></table>`;
            container.innerHTML = tableHtml;
        } catch (error) {
            document.getElementById('activity-log-container').innerHTML = `<p class="text-danger">${error.message}</p>`;
        }
    }
    async function renderSSAPView() {
        mainContent.innerHTML = `
            <div class="content-header">
                <h2>Gerenciamento de Usuários</h2>
            </div>
            <div class="card">
                <div class="card-body">
                    <div id="user-management-container" class="table-responsive">
                        <div class="text-center p-5"><div class="spinner-border text-primary" role="status"></div></div>
                    </div>
                </div>
            </div>`;
        try {
            const response = await fetch(`${API_URL}/admin/users?admin_user_id=${currentUser.id}`);
            if (!response.ok) throw new Error((await response.json()).error || 'Não foi possível carregar os usuários.');
            const users = await response.json();
            const container = document.getElementById('user-management-container');
            if (users.length === 0) {
                container.innerHTML = '<p class="text-muted text-center">Nenhum usuário encontrado.</p>';
                return;
            }
            let tableHtml = `
                <table class="table table-hover user-management-table">
                    <thead class="table-light">
                        <tr>
                            <th scope="col">Usuário</th>
                            <th scope="col">E-mail</th>
                            <th scope="col">Cargo</th>
                            <th scope="col">Role</th>
                            <th scope="col" class="text-end">Ações</th>
                        </tr>
                    </thead>
                    <tbody>`;
            users.forEach(user => {
                const isCurrentUser = user.id === currentUser.id;
                const roleBadge = user.role === 'admin' 
                    ? `<span class="badge bg-primary role-badge">Admin</span>` 
                    : `<span class="badge bg-secondary role-badge">Funcionário</span>`;
                const actions = isCurrentUser ? '<span class="text-muted small">Não é possível alterar a si mesmo</span>' : `
                    <button class="btn btn-sm btn-outline-info" title="Associar Categorias" data-action="categories" data-id="${user.id}" data-username="${user.username}" 
                            style="display: ${user.role === 'admin' ? 'none' : 'inline-block'}">
                        <i class="bi bi-folder-plus"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-secondary" title="Impersonar" data-action="impersonate" data-id="${user.id}" data-username="${user.username}"><i class="bi bi-person-fill-gear"></i></button>
                    <button class="btn btn-sm btn-outline-primary" title="Editar" data-action="edit" data-id="${user.id}"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-sm btn-outline-warning" title="Forçar Reset de Senha" data-action="reset" data-id="${user.id}" data-username="${user.username}"><i class="bi bi-key-fill"></i></button>
                    <button class="btn btn-sm btn-outline-danger" title="Excluir" data-action="delete" data-id="${user.id}" data-username="${user.username}"><i class="bi bi-trash"></i></button>
                `;
                tableHtml += `
                    <tr>
                        <td><strong>${user.username}</strong> ${user.needs_password_reset ? '<span class="badge bg-warning text-dark">Reset Pendente</span>' : ''}</td>
                        <td>${user.email || 'N/A'}</td>
                        <td>${user.job_title || 'N/A'}</td>
                        <td>${roleBadge}</td>
                        <td class="actions-cell" style="min-width: 260px;">${actions}</td> </tr>`;
            });
            tableHtml += `</tbody></table>`;
            container.innerHTML = tableHtml;
            container.addEventListener('click', (e) => {
                const button = e.target.closest('button[data-action]');
                if (!button) return;
                const action = button.dataset.action;
                const userId = parseInt(button.dataset.id);
                const username = button.dataset.username;
                if (action === 'delete') handleAdminDeleteUser(userId, username);
                if (action === 'reset') handleAdminForceReset(userId, username);
                if (action === 'edit') handleAdminOpenEditModal(userId);
                if (action === 'impersonate') handleAdminImpersonate(userId, username);
                if (action === 'categories') handleOpenAssignCategoriesModal(userId, username);
            });
        } catch (error) {
            document.getElementById('user-management-container').innerHTML = `<p class="text-danger text-center">${error.message}</p>`;
        }
    }
    function renderDueSoonTasks() {
        const container = document.getElementById('due-soon-container');
        const listEl = document.getElementById('due-soon-list');
        if (!container || !listEl) return; 
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const sevenDaysFromNow = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);
        const dueSoonTasks = allTasks.filter(task => {
            if (task.completed || !task.due_date) return false;
            const dueDate = new Date(task.due_date + 'T00:00:00');
            return dueDate >= today && dueDate <= sevenDaysFromNow;
        });
        dueSoonTasks.sort((a, b) => new Date(a.due_date) - new Date(b.due_date));
        if (dueSoonTasks.length === 0) {
            container.style.display = 'none';
            return;
        }
        container.style.display = 'block';
        listEl.innerHTML = ''; 
        dueSoonTasks.forEach(task => {
            const dueDate = new Date(task.due_date + 'T00:00:00');
            const daysLeft = Math.round((dueDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
            let dateClass = '';
            let dateText = '';
            if (daysLeft === 0) {
                dateText = 'Vence hoje!';
                dateClass = 'due-date'; // Vermelho
            } else if (daysLeft === 1) {
                dateText = 'Vence amanhã!';
                dateClass = 'due-date-warning'; // Amarelo
            } else if (daysLeft <= 3) {
                dateText = `Vence em ${daysLeft} dias`;
                dateClass = 'due-date-warning'; // Amarelo
            } else {
                dateText = `Vence em ${daysLeft} dias`;
            }
            listEl.innerHTML += `
                <li>
                    <span class="task-title">${task.title}</span>
                    <span class="${dateClass}">${dateText}</span>
                </li>
            `;
        });
    }

    // --- ================================== ---
    // --- FUNÇÃO RENDER TASKS (ATUALIZADA) ---
    // --- ================================== ---
    
  function renderTasks() {
        const searchTerm = document.getElementById('task-search-input')?.value.toLowerCase() || '';
        const filteredBySearch = allTasks.filter(task => (task.title || '').toLowerCase().includes(searchTerm) || (task.description || '').toLowerCase().includes(searchTerm));
        renderDueSoonTasks(); 
        const filteredByStatus = filteredBySearch.filter(task => {
            if (currentFilter === 'mine') return task.assigned_to_id === currentUser.id;
            if (currentFilter === 'overdue') {
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                return !task.completed && task.due_date && new Date(task.due_date + 'T00:00:00') < today;
            }
            return true;
        });
        const categoryId = currentCategoryFilter;
        const tasksToRender = filteredByStatus.filter(task => {
            if (categoryId === 'all') {
                return true; 
            }
            if (categoryId === 'none') {
                return !task.category_id;
            }
            return task.category_id == categoryId; 
        });
        const taskList = mainContent.querySelector('#task-list');
        if (!taskList) return;
        taskList.innerHTML = tasksToRender.length === 0 ? '<p class="text-center text-muted">Nenhuma tarefa encontrada.</p>' : '';
        const isAdminView = (currentUser.role === 'admin' && !currentUser.impersonating);
        tasksToRender.forEach(task => {
            // <-- MUDANÇA AQUI: Cores alteradas para Laranja (warning) e Ciano (info)
            const priority = {1:{bg:'danger',txt:'Alta'}, 2:{bg:'warning',txt:'Média'}, 3:{bg:'info',txt:'Baixa'}}[task.priority] || {bg:'info', txt:'Baixa'};
            
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            const isOverdue = !task.completed && task.due_date && new Date(task.due_date + 'T00:00:00') < today;
            const adminButtons = isAdminView
                ? `<button class="btn btn-outline-secondary" title="Editar" data-action="edit" data-id="${task.id}"><i class="bi bi-pencil"></i></button><button class="btn btn-outline-danger" title="Excluir" data-action="delete" data-id="${task.id}"><i class="bi bi-trash"></i></button>`
                : '';
            const card = document.createElement('div');
            card.className = 'col-md-6 col-lg-4';
            const completedStr = task.completed ? 'true' : 'false';
            const createdAtStr = task.created_at ? new Date(task.created_at).toLocaleString('pt-BR') : 'N/A';
            const unreadCount = task.unread_comment_count || 0;
            const commentBadge = unreadCount > 0 ? `<span class="notification-badge count">${unreadCount}</span>` : '';
            card.innerHTML = `
                <div class="card h-100 task-card ${task.completed ? 'completed-task' : ''}">
                    <div class="task-actions">
                        ${adminButtons}
                        <button class="btn btn-outline-info task-comment-btn" title="Comentários" data-action="comments" data-id="${task.id}">
                            <i class="bi bi-chat-left-text"></i>
                            ${commentBadge}
                        </button>
                        <button class="${task.completed ? 'btn btn-outline-secondary' : 'btn btn-success'}" title="${task.completed ? 'Reabrir' : 'Concluir'}" data-action="toggle-complete" data-id="${task.id}" data-completed="${completedStr}">
                            <i class="bi ${task.completed ? 'bi-x-lg' : 'bi-check-lg'}"></i>
                        </button>
                    </div>
                    <div class="card-body">
                        
                        <div class="d-flex justify-content-between align-items-start">
                            <h5 class="card-title">${task.title}</h5>
                            <span class="badge bg-${priority.bg}-subtle text-${priority.bg}-emphasis p-2">${priority.txt}</span>
                        </div>
                        
                        <p class="card-text text-muted small">${task.description || ''}</p>
                        <div class="small text-muted"><b>Prazo:</b> ${task.due_date ? new Date(task.due_date + 'T00:00:00').toLocaleDateString('pt-BR') : 'N/A'} ${isOverdue ? '<span class="badge bg-danger ms-2">Atrasada</span>' : ''}</div>
                        <div class="small text-muted mt-1"><b>Para:</b> ${task.assignee_name || 'Ninguém'}</div>
                        <div class="small text-muted mt-1"><b>Categoria:</b> ${task.category_name || 'Nenhuma'}</div> 
                        <div class="small text-muted mt-3"><b>Criado por:</b> ${task.creator_name || 'N/A'}</div>
                        <div class="small text-muted mt-1"><b>Criado em:</b> ${createdAtStr}</div>
                    </div>
                </div>`;
            taskList.appendChild(card);
        });
    }

    // --- MODAIS / CHAT (ATUALIZADO PARA INCLUIR MODAIS 2FA) ---
    function initializeModalsAndChat() {
        if (!editTaskModal) {
            const el = document.getElementById('editTaskModal');
            if (el) {
                el.innerHTML = `<div class="modal-dialog modal-lg"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Editar Tarefa</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><form id="edit-task-form"></form></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button><button type="submit" form="edit-task-form" class="btn btn-primary">Salvar</button></div></div></div>`;
                editTaskModal = new bootstrap.Modal(el);
                el.querySelector('#edit-task-form').addEventListener('submit', handleEditTask);
            }
        }
        if (!adminUserEditModal) {
            const el = document.getElementById('adminUserEditModal');
            if (el) {
                adminUserEditModal = new bootstrap.Modal(el);
                el.querySelector('#admin-user-edit-form').addEventListener('submit', handleAdminEditUser);
            }
        }
        if (!assignCategoriesModal) {
            const el = document.getElementById('assignCategoriesModal');
            if (el) { 
                assignCategoriesModal = new bootstrap.Modal(el);
                el.querySelector('#assign-categories-form').addEventListener('submit', handleAdminSaveUserCategories);
            }
        }
        if (!manageCategoryUsersModal) {
            const el = document.getElementById('manageCategoryUsersModal');
            if (el) {
                manageCategoryUsersModal = new bootstrap.Modal(el);
                el.querySelector('#manage-category-users-form').addEventListener('submit', handleAdminSaveCategoryUsers);
            }
        }
        if (!quickAddTaskModal) {
            const el = document.getElementById('quickAddTaskModal');
            if (el) {
                quickAddTaskModal = new bootstrap.Modal(el);
                el.querySelector('#quick-add-task-form').addEventListener('submit', handleQuickAddTask);
            }
        }
        if (!commentsModal) {
            const el = document.getElementById('commentsModal');
            if (el) {
                el.innerHTML = `<div class="modal-dialog modal-dialog-centered"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Comentários</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div id="comments-list" class="mb-3" style="max-height: 400px; overflow-y: auto;"></div><form id="comment-form"><input type="hidden" id="comment-task-id"><div class="input-group"><input type="text" id="comment-input" class="form-control" placeholder="Adicionar comentário..." required autocomplete="off"><button class="btn btn-outline-primary" type="submit">Enviar</button></div></form></div></div></div>`;
                commentsModal = new bootstrap.Modal(el);
                el.querySelector('#comment-form').addEventListener('submit', handleAddComment);
            }
        }
        if (!confirmationModal) {
            const el = document.getElementById('confirmationModal');
            if (el) confirmationModal = new bootstrap.Modal(el);
        }
        
        // --- ATUALIZAÇÃO: Inicializa os novos modais de segurança ---
        if (!login2faModal) {
            const el = document.getElementById('login2faModal');
            if(el) login2faModal = new bootstrap.Modal(el, { backdrop: 'static', keyboard: false });
        }
        if (!setup2faModal) {
            const el = document.getElementById('setup2faModal');
            if(el) {
                setup2faModal = new bootstrap.Modal(el);
                el.querySelector('#setup-2fa-form').addEventListener('submit', handleVerify2FA);
            }
        }
         if (!disable2faModal) {
            const el = document.getElementById('disable2faModal');
            if(el) {
                disable2faModal = new bootstrap.Modal(el);
                el.querySelector('#disable-2fa-form').addEventListener('submit', handleDisable2FA);
            }
        }
        // --- Fim da Atualização ---
        
        // --- ATUALIZAÇÃO: Inicializa o modal de reset forçado ---
        if (!forceResetModal) {
            const el = document.getElementById('forcePasswordResetModal');
            if (el) forceResetModal = new bootstrap.Modal(el, { backdrop: 'static', keyboard: false });
        }
        // --- Fim da Atualização ---


        // Inicialização do Chat (sem alterações)
        const chat = document.getElementById('chat-container');
        if (chat && !chat.innerHTML.trim()) {
            chat.innerHTML = `
                <div id="chat-bubble">
                    <i class="bi bi-chat-dots-fill"></i>
                    <span id="chat-notification-badge" class="notification-badge" style="display: none;"></span>
                </div>
                <div id="chat-window">
                    <div class="chat-header">Chat da Equipe</div>
                    <div id="chat-messages"></div>
                    <form id="chat-form">
                        <input type="text" id="chat-input" class="form-control" placeholder="Digite sua mensagem..." autocomplete="off">
                        <button type="submit" class="btn btn-primary ms-2"><i class="bi bi-send-fill"></i></button>
                    </form>
                </div>`;
            const chatBubble = chat.querySelector('#chat-bubble');
            const chatWindow = document.getElementById('chat-window');
            chatBubble.addEventListener('click', async () => {
                const isOpen = window.getComputedStyle(chatWindow).display === 'flex';
                chatWindow.style.display = isOpen ? 'none' : 'flex';
                if (!isOpen) {
                    try {
                        await renderChatMessages(); 
                    } catch (err) {
                        console.error('Erro ao carregar mensagens do chat:', err);
                    }
                }
            });
            chat.querySelector('#chat-form').addEventListener('submit', handleSendChatMessage);
        }
    }


    // --- (Funções de Tarefa, Dropdowns, Filtros, etc. permanecem aqui) ---
    // ... (populateAssigneeDropdown, populateCategoryDropdown, handleFilterClick, fetchAndRenderTasks, etc.)
    async function populateAssigneeDropdown(selectElement) {
        try {
            const res = await fetch(`${API_URL}/users/employees`);
            if (!res.ok) throw new Error('Falha ao buscar funcionários');
            const employees = await res.json();
            selectElement.innerHTML = '<option value="">Ninguém</option>';
            employees.forEach(emp => selectElement.innerHTML += `<option value="${emp.id}">${emp.username}</option>`);
        } catch (error) {
            console.error(error.message);
        }
    }
    async function populateCategoryDropdown(selectElement, selectedValue = '') {
        try {
            const res = await fetch(`${API_URL}/categories`);
            if (!res.ok) throw new Error('Falha ao buscar categorias');
            const categories = await res.json();
            const firstOption = selectElement.querySelector('option');
            selectElement.innerHTML = '';
            if (firstOption && (firstOption.value === "" || firstOption.value === "none")) {
                selectElement.appendChild(firstOption);
            } else {
                selectElement.innerHTML = '<option value="">Nenhuma Categoria</option>';
            }
            categories.forEach(cat => {
                selectElement.innerHTML += `<option value="${cat.id}">${cat.name}</option>`;
            });
            if (selectedValue) {
                selectElement.value = selectedValue;
            }
        } catch (error) {
            console.error(error.message);
        }
    }
    function handleFilterClick(e) {
        if (e.target.tagName === 'BUTTON') {
            mainContent.querySelector('.task-filters .active').classList.remove('active');
            e.target.classList.add('active');
            currentFilter = e.target.dataset.filter;
            renderTasks();
        }
    }
    async function fetchAndRenderTasks() {
        try {
            const res = await fetch(`${API_URL}/tasks?user_id=${currentUser.id}`);
            if (!res.ok) throw new Error('Falha ao carregar tarefas');
            allTasks = await res.json();
            renderTasks();
        } catch (error) {
            const list = mainContent.querySelector('#task-list');
            if (list) list.innerHTML = `<p class="text-center text-danger">${error.message}</p>`;
        }
    }
    function handleTaskListClick(e) {
        const button = e.target.closest('button[data-action]');
        if (!button) return;
        if (currentUser.impersonating && (button.dataset.action === 'edit' || button.dataset.action === 'delete')) {
            alert('Ações de administrador estão desabilitadas durante a impersonação.');
            return;
        }
        const action = button.dataset.action;
        const taskId = parseInt(button.dataset.id);
        const actions = {
            'edit': () => handleOpenEditModal(taskId),
            'delete': () => handleDeleteTask(taskId),
            'comments': () => handleOpenCommentsModal(taskId, button),
            'toggle-complete': () => handleToggleComplete(taskId)
        };
        if (actions[action]) actions[action]();
    }
    async function handleAddTask(e) {
        e.preventDefault();
        const assigneeId = document.getElementById('assign-to').value;
        const categoryId = document.getElementById('task-category').value;
        const taskData = {
            title: document.getElementById('task-title').value,
            description: document.getElementById('task-description').value,
            priority: parseInt(document.getElementById('task-priority').value),
            due_date: document.getElementById('task-due-date').value || null,
            creator_id: currentUser.id, 
            assigned_to_id: assigneeId ? parseInt(assigneeId) : null,
            category_id: categoryId ? parseInt(categoryId) : null
        };
        try {
            const res = await fetch(`${API_URL}/tasks`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(taskData)
            });
            if (!res.ok) throw new Error((await res.json()).error || 'Erro ao criar tarefa');
            e.target.reset();
            if (categoryId) {
                 document.getElementById('task-category').value = categoryId;
            }
            fetchAndRenderTasks();
        } catch (error) {
            alert(`Erro: ${error.message}`);
        }
    }
    async function handleOpenQuickAddModal() {
        const form = document.getElementById('quick-add-task-form');
        form.reset(); 
        const assignContainer = document.getElementById('quick-assign-container');
        const isAdmin = (currentUser.role === 'admin' && !currentUser.impersonating);
        const categorySelect = document.getElementById('quick-task-category');
        if (isAdmin) {
            await Promise.all([
                populateAssigneeDropdown(document.getElementById('quick-assign-to')),
                populateCategoryDropdown(categorySelect)
            ]);
            assignContainer.style.display = 'block';
        } else {
            await populateCategoryDropdown(categorySelect);
            assignContainer.style.display = 'none';
        }
        if (currentCategoryFilter !== 'all' && currentCategoryFilter !== 'none') {
            categorySelect.value = currentCategoryFilter;
        }
        quickAddTaskModal.show();
    }
    async function handleQuickAddTask(e) {
        e.preventDefault();
        const isAdmin = (currentUser.role === 'admin' && !currentUser.impersonating);
        let assigneeId = null;
        if (isAdmin) {
            assigneeId = document.getElementById('quick-assign-to').value;
        } else {
            assigneeId = currentUser.id;
        }
        const dueDate = document.getElementById('quick-task-due-date').value;
        const taskData = {
            title: document.getElementById('quick-task-title').value,
            description: document.getElementById('quick-task-description').value,
            priority: parseInt(document.getElementById('quick-task-priority').value),
            due_date: dueDate || null,
            creator_id: currentUser.id,
            assigned_to_id: assigneeId ? parseInt(assigneeId) : null,
            category_id: document.getElementById('quick-task-category').value || null
        };
        try {
            const res = await fetch(`${API_URL}/tasks`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(taskData)
            });
            if (!res.ok) throw new Error((await res.json()).error || 'Erro ao criar tarefa');
            quickAddTaskModal.hide();
            if (document.getElementById('task-list')) {
                fetchAndRenderTasks();
            }
        } catch (error) {
            alert(`Erro: ${error.message}`);
        }
    }
    async function handleEditTask(e) {
        e.preventDefault();
        const form = e.target;
        const taskId = parseInt(form.dataset.taskId);
        const assigneeId = form.elements['edit-assign-to'].value;
        const taskData = {
            title: form.elements['edit-task-title'].value,
            description: form.elements['edit-task-description'].value,
            priority: parseInt(form.elements['edit-task-priority'].value),
            due_date: form.elements['edit-task-due-date'].value || null,
            assigned_to_id: assigneeId ? parseInt(assigneeId) : null,
            category_id: form.elements['edit-task-category'].value || null,
            acting_user_id: currentUser.id
        };
        try {
            const res = await fetch(`${API_URL}/tasks/${taskId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(taskData)
            });
            if (!res.ok) throw new Error((await res.json()).error || 'Erro ao editar tarefa');
            editTaskModal.hide();
            fetchAndRenderTasks();
        } catch (error) {
            alert(`Erro: ${error.message}`);
        }
    }
    async function handleToggleComplete(taskId) {
        try {
            let task = allTasks.find(t => t.id === taskId);
            if (!task) {
                const resTask = await fetch(`${API_URL}/tasks/${taskId}`);
                if (!resTask.ok) throw new Error('Não foi possível obter o estado da tarefa.');
                task = await resTask.json();
            }
            const currentCompleted = !!task.completed;
            const payload = { 
                completed: !currentCompleted,
                acting_user_id: currentUser.id 
            };
            const res = await fetch(`${API_URL}/tasks/${taskId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.error || data.message || 'Erro ao alternar conclusão');
            await fetchAndRenderTasks();
        } catch (error) {
            alert(`Erro: ${error.message}`);
        }
    }
    function handleDeleteTask(taskId) {
        const confirmationText = 'Você confirma a exclusão desta tarefa? Esta ação é irreversível.';
        document.getElementById('confirmation-modal-body').textContent = confirmationText;
        const confirmBtn = document.getElementById('confirm-action-btn');
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        newConfirmBtn.addEventListener('click', async () => {
            try {
                const res = await fetch(`${API_URL}/tasks/${taskId}`, { 
                    method: 'DELETE', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ acting_user_id: currentUser.id })
                });
                let data;
                try { data = await res.json(); } catch (e) { data = {}; }
                if (!res.ok) {
                    alert(data.error || data.message || 'Não foi possível excluir a tarefa.');
                    return;
                }
                confirmationModal.hide();
                fetchAndRenderTasks();
            } catch (err) {
                alert('Erro ao conectar com o servidor.');
            }
        }, { once: true });
        confirmationModal.show();
    }
    async function handleOpenEditModal(taskId) {
        try {
            const res = await fetch(`${API_URL}/tasks/${taskId}`);
            if (!res.ok) throw new Error('Não foi possível carregar os dados da tarefa.');
            const task = await res.json();
            const form = document.getElementById('edit-task-form');
            form.dataset.taskId = taskId;
            form.innerHTML = `<div class="row g-3">
                <div class="col-12"><label class="form-label">Título</label><input type="text" id="edit-task-title" class="form-control" value="${task.title}" required></div>
                <div class="col-md-6"><label class="form-label">Prioridade</label><select id="edit-task-priority" class="form-select"></select></div>
                <div class="col-md-6"><label class="form-label">Prazo</label><input type="date" id="edit-task-due-date" class="form-control" value="${task.due_date ? task.due_date.split('T')[0] : ''}"></div>
                <div class="col-12"><label class="form-label">Descrição</label><textarea id="edit-task-description" class="form-control" rows="3" required>${task.description || ''}</textarea></div>
                <div class="col-md-6"><label class="form-label">Atribuir para:</label><select id="edit-assign-to" class="form-select"><option value="">Ninguém</option></select></div>
                <div class="col-md-6"><label class="form-label">Categoria:</label><select id="edit-task-category" class="form-select"><option value="">Nenhuma Categoria</option></select></div>
            </div>`;
            const prioritySelect = form.elements['edit-task-priority'];
            prioritySelect.innerHTML = `<option value="1">Alta</option><option value="2">Média</option><option value="3">Baixa</option>`;
            prioritySelect.value = task.priority;
            const assigneeSelect = form.elements['edit-assign-to'];
            const categorySelect = form.elements['edit-task-category'];
            await Promise.all([
                populateAssigneeDropdown(assigneeSelect),
                populateCategoryDropdown(categorySelect) 
            ]);
            assigneeSelect.value = task.assigned_to_id || "";
            categorySelect.value = task.category_id || "";
            editTaskModal.show();
        } catch (error) {
            alert(error.message);
        }
    }
    function handleAdminDeleteUser(userId, username) {
        const confirmationText = `Você confirma a EXCLUSÃO permanente do usuário '${username}'? Esta ação é irreversível.`;
        document.getElementById('confirmation-modal-body').textContent = confirmationText;
        const confirmBtn = document.getElementById('confirm-action-btn');
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        newConfirmBtn.addEventListener('click', async () => {
            try {
                const res = await fetch(`${API_URL}/admin/user/${userId}`, { 
                    method: 'DELETE', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ admin_user_id: currentUser.id })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Não foi possível excluir o usuário.');
                confirmationModal.hide();
                alert(data.message || 'Usuário excluído com sucesso.');
                renderView('ssap');
            } catch (err) {
                alert(err.message);
            }
        }, { once: true });
        confirmationModal.show();
    }
    function handleAdminForceReset(userId, username) {
        const confirmationText = `Você confirma a redefinição de senha forçada para '${username}'? O usuário será obrigado a criar uma nova senha no próximo login.`;
        document.getElementById('confirmation-modal-body').textContent = confirmationText;
        const confirmBtn = document.getElementById('confirm-action-btn');
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        newConfirmBtn.addEventListener('click', async () => {
            try {
                const res = await fetch(`${API_URL}/admin/force-reset-password`, { 
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        admin_user_id: currentUser.id,
                        target_user_id: userId
                    })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Não foi possível resetar a senha.');
                confirmationModal.hide();
                alert(data.message); 
                renderView('ssap');
            } catch (err) {
                alert(err.message);
            }
        }, { once: true });
        confirmationModal.show();
    }
    async function handleAdminOpenEditModal(userId) {
        try {
            const res = await fetch(`${API_URL}/user/${userId}`);
            if (!res.ok) throw new Error('Não foi possível carregar os dados do usuário.');
            const user = await res.json();
            const form = document.getElementById('admin-user-edit-form');
            form.dataset.targetUserId = userId;
            form.innerHTML = `<div class="row g-3">
                <div class="col-md-6">
                    <label class="form-label">Nome de Usuário</label>
                    <input type="text" id="admin-edit-username" class="form-control" value="${user.username}" required>
                </div>
                <div class="col-md-6">
                    <label class="form-label">E-mail</label>
                    <input type="email" id="admin-edit-email" class="form-control" value="${user.email || ''}" required>
                </div>
                <div class="col-md-6">
                    <label class="form-label">Cargo</label>
                    <input type="text" id="admin-edit-job-title" class="form-control" value="${user.job_title || ''}">
                </div>
                <div class="col-md-6">
                    <label class="form-label">Role (Permissão)</label>
                    <select id="admin-edit-role" class="form-select">
                        <option value="funcionario">Funcionário</option>
                        <option value="admin">Administrador</option>
                    </select>
                </div>
                <div id="admin-user-edit-error" class="error-message"></div>
            </div>`;
            form.elements['admin-edit-role'].value = user.role;
            adminUserEditModal.show();
        } catch (error) {
            alert(error.message);
        }
    }
    async function handleAdminEditUser(e) {
        e.preventDefault();
        const form = e.target;
        const targetUserId = parseInt(form.dataset.targetUserId);
        const errorEl = document.getElementById('admin-user-edit-error');
        errorEl.textContent = '';
        const email = form.elements['admin-edit-email'].value.trim();
        if (!validateEmailFormat(email)) {
            errorEl.textContent = 'O formato do e-mail é inválido.';
            return;
        }
        const updatedData = {
            username: form.elements['admin-edit-username'].value.trim(),
            email: email,
            job_title: form.elements['admin-edit-job-title'].value.trim(),
            role: form.elements['admin-edit-role'].value,
            acting_user_id: currentUser.id
        };
        try {
            const response = await fetch(`${API_URL}/user/${targetUserId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updatedData)
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Erro ao atualizar usuário');
            adminUserEditModal.hide();
            renderView('ssap');
        } catch (error) {
            errorEl.textContent = error.message;
        }
    }
    async function handleAdminImpersonate(targetUserId, username) {
        const confirmationText = `Você está prestes a iniciar uma sessão como '${username}'. Suas ações serão registradas como se fossem dele. Deseja continuar?`;
        if (!confirm(confirmationText)) return;
        try {
            localStorage.setItem('originalAdminSession', JSON.stringify(currentUser));
            const resToken = await fetch(`${API_URL}/admin/impersonate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    admin_user_id: currentUser.id,
                    target_user_id: targetUserId
                })
            });
            const dataToken = await resToken.json();
            if (!resToken.ok) throw new Error(dataToken.error || 'Falha ao iniciar impersonação');
            const resLogin = await fetch(`${API_URL}/impersonate/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: dataToken.token })
            });
            const dataLogin = await resLogin.json();
            if (!resLogin.ok) throw new Error(dataLogin.error || 'Falha ao logar como usuário');
            startSession(dataLogin.user);
        } catch (error) {
            alert(`Erro na impersonação: ${error.message}`);
            localStorage.removeItem('originalAdminSession');
        }
    }
    async function handleOpenCommentsModal(taskId, commentButton) {
        document.getElementById('comment-task-id').value = taskId;
        if (commentButton) {
            const badge = commentButton.querySelector('.notification-badge');
            if (badge) {
                badge.remove();
            }
            try {
                await fetch(`${API_URL}/tasks/${taskId}/mark-as-read`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: currentUser.id })
                });
            } catch (err) {
                console.error("Falha ao marcar tarefa como lida", err);
            }
        }
        await renderComments(taskId); 
        commentsModal.show();
    }
    async function renderComments(taskId) {
        try {
            const res = await fetch(`${API_URL}/tasks/${taskId}/comments`);
            if (!res.ok) throw new Error('Não foi possível carregar os comentários.');
            const comments = await res.json();
            const listEl = document.getElementById('comments-list');
            listEl.innerHTML = comments.length === 0 ? '<p class="text-muted text-center">Nenhum comentário ainda.</p>' : '';
            comments.forEach(c => listEl.innerHTML += `<div class="comment"><p class="mb-1"><strong>${c.username}:</strong> ${c.text}</p><small class="text-muted">${new Date(c.timestamp).toLocaleString('pt-BR')}</small></div>`);
            listEl.scrollTop = listEl.scrollHeight;
        } catch (error) {
            alert(error.message);
        }
    }
    async function handleAddComment(e) {
        e.preventDefault();
        const taskId = parseInt(document.getElementById('comment-task-id').value);
        const text = document.getElementById('comment-input').value.trim();
        if (!text) return;
        try {
            const res = await fetch(`${API_URL}/tasks/${taskId}/comments`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUser.id, text })
            });
            if (!res.ok) throw new Error((await res.json()).error || 'Erro ao adicionar comentário');
            document.getElementById('comment-input').value = '';
            await renderComments(taskId);
            await fetchAndRenderTasks();
        } catch (error) {
            alert(`Erro: ${error.message}`);
        }
    }
    async function handleSendChatMessage(e) {
        e.preventDefault();
        const input = document.getElementById('chat-input');
        const text = input.value.trim();
        if (!text) return;
        try {
            const res = await fetch(`${API_URL}/chat/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUser.id, text })
            });
            if (!res.ok) throw new Error((await res.json()).error || 'Erro ao enviar mensagem');
            input.value = '';
            await renderChatMessages(); 
        } catch (error) {
            alert(`Erro: ${error.message}`);
        }
    }
    async function renderChatMessages() {
        await markChatAsRead();
        try {
            const cacheBuster = `?_=${new Date().getTime()}`;
            const res = await fetch(`${API_URL}/chat/messages${cacheBuster}`);
            if (!res.ok) throw new Error('Não foi possível carregar mensagens do chat.');
            const messages = await res.json();
            const messagesEl = document.getElementById('chat-messages');
            messagesEl.innerHTML = '';
            messages.forEach(msg => messagesEl.innerHTML += `<div class="p-2"><strong>${msg.username}:</strong> ${msg.text}</div>`);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        } catch (error) {
            alert(error.message);
        }
    }
    (function handleCookieConsent() {
        const banner = document.getElementById('cookie-consent-banner');
        const acceptBtn = document.getElementById('cookie-consent-btn');
        if (localStorage.getItem('cookie_consent') === 'true') {
            return;
        }
        setTimeout(() => {
            if(banner) banner.classList.add('show');
        }, 500);
        if(acceptBtn) {
            acceptBtn.addEventListener('click', () => {
                if(banner) banner.classList.remove('show');
                localStorage.setItem('cookie_consent', 'true');
            });
        }
    })();
    async function renderDpoView() {
        mainContent.innerHTML = `
            <div class="content-header">
                <h2>Central de Privacidade (DPO)</h2>
            </div>
            <div class="card">
                <div class="card-body">
                    <p class="text-muted">Abaixo estão as solicitações de privacidade enviadas pelos usuários.</p>
                    <div id="dpo-requests-container">
                        <div class="text-center p-5"><div class="spinner-border text-primary" role="status"></div></div>
                    </div>
                </div>
            </div>`;
        const container = document.getElementById('dpo-requests-container');
        try {
            const response = await fetch(`${API_URL}/admin/dpo-requests?admin_user_id=${currentUser.id}`);
            if (!response.ok) throw new Error((await response.json()).error || 'Não foi possível carregar as solicitações.');
            const requests = await response.json();
            if (requests.length === 0) {
                container.innerHTML = '<p class="text-center text-muted">Nenhuma solicitação de DPO encontrada.</p>';
                return;
            }
            let html = '<div class="list-group">';
            requests.forEach(req => {
                const createdAt = new Date(req.created_at).toLocaleString('pt-BR');
                let responseHtml = '';
                let extraInfoHtml = '';
                const requestTypesMap = {
                    'access': 'Solicitação de Acesso',
                    'correction': 'Solicitação de Correção',
                    'anonymization': 'Solicitação de Anonimização (Manual)',
                    'anonymization_request': 'Solicitação de Anonimização (Iniciada pelo Usuário)',
                    'question': 'Dúvida Geral'
                };
                const requestTypeDisplay = requestTypesMap[req.request_type] || req.request_type;
                if (req.request_type === 'anonymization_request' || req.request_type === 'anonymization') {
                    if (req.scheduled_for) {
                        const scheduledDate = new Date(req.scheduled_for).toLocaleString('pt-BR');
                        extraInfoHtml = `<p class="mb-2 text-danger"><strong><i class="bi bi-alarm-fill"></i> Anonimização Agendada para:</strong> ${scheduledDate}</p>`;
                    }
                    if (req.status === 'pending') {
                        responseHtml = `
                            <div class="mt-3">
                                <button class="btn btn-danger w-100" data-action="execute-anonymization" data-id="${req.id}" data-username="${req.user_username}">
                                    <i class="bi bi-shield-x"></i> Executar Anonimização Agora
                                </button>
                                <p class="text-muted small mt-1">Atenção: Esta ação é imediata, irreversível e irá anonimizar a conta do usuário ${req.user_username}.</p>
                            </div>
                        `;
                    } else {
                        const respondedAt = new Date(req.responded_at).toLocaleString('pt-BR');
                        responseHtml = `
                            <div class="mt-3 p-3 bg-light border rounded">
                                <h6 class="text-success"><i class="bi bi-check-circle-fill"></i> Processado por: ${req.admin_username || 'Admin'} em ${respondedAt}</h6>
                                <p class="mb-0">${req.response_text}</p>
                            </div>
                        `;
                    }
                } else if (req.status === 'answered') {
                    const respondedAt = new Date(req.responded_at).toLocaleString('pt-BR');
                    responseHtml = `
                        <div class="mt-3 p-3 bg-light border rounded">
                            <h6 class="text-success">Respondido por: ${req.admin_username || 'Admin'} em ${respondedAt}</h6>
                            <p class="mb-0">${req.response_text}</p>
                        </div>
                    `;
                } else {
                    responseHtml = `
                        <form class="dpo-response-form mt-3" data-request-id="${req.id}">
                            <div class="mb-2">
                                <label class="form-label fw-bold">Responder à solicitação:</label>
                                <textarea class="form-control" rows="3" name="response_text" required></textarea>
                            </div>
                            <button type="submit" class="btn btn-primary btn-sm">Enviar Resposta</button>
                        </form>
                    `;
                }
                html += `
                    <div class="list-group-item list-group-item-action flex-column align-items-start mb-3 border">
                        <div class="d-flex w-100 justify-content-between">
                            <h5 class="mb-1">${requestTypeDisplay}</h5>
                            <small class="text-muted">${createdAt}</small>
                        </div>
                        <p class="mb-1"><strong>De:</strong> ${req.user_username}</p>
                        <p class="mb-2"><strong>Mensagem:</strong> ${req.message_text}</p>
                        ${extraInfoHtml} <div class="d-flex justify-content-between align-items-center">
                            <span class="badge bg-${req.status === 'pending' ? 'warning text-dark' : 'success'}">
                                ${req.status === 'pending' ? 'Pendente' : (req.request_type.includes('anonymization') ? 'Processado' : 'Respondido')}
                            </span>
                            <button class="btn btn-outline-danger btn-sm" data-action="delete" data-id="${req.id}" title="Excluir Solicitação">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                        ${responseHtml}
                    </div>
                `;
            });
            html += '</div>';
            container.innerHTML = html;
            container.addEventListener('submit', handleDpoResponseSubmit);
            container.addEventListener('click', handleDpoViewClick);
        } catch (error) {
            container.innerHTML = `<p class="text-danger text-center">${error.message}</p>`;
        }
    }
    function handleDpoViewClick(e) {
        const deleteButton = e.target.closest('button[data-action="delete"]');
        if (deleteButton) {
            e.preventDefault();
            const requestId = deleteButton.dataset.id;
            handleAdminDeleteDpoRequest(requestId);
            return;
        }
        const executeButton = e.target.closest('button[data-action="execute-anonymization"]');
        if (executeButton) {
            e.preventDefault();
            const requestId = executeButton.dataset.id;
            const username = executeButton.dataset.username;
            handleAdminExecuteAnonymization(requestId, username);
            return;
        }
    }
    function handleAdminExecuteAnonymization(requestId, username) {
        const confirmationText = `Você confirma a EXECUÇÃO da anonimização para o usuário '${username}' (Solicitação ID ${requestId})? Esta ação é imediata e não pode ser desfeita.`;
        document.getElementById('confirmation-modal-body').textContent = confirmationText;
        const confirmBtn = document.getElementById('confirm-action-btn');
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        newConfirmBtn.addEventListener('click', async () => {
            try {
                const res = await fetch(`${API_URL}/admin/execute-anonymization`, { 
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        admin_user_id: currentUser.id,
                        request_id: parseInt(requestId)
                    })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Não foi possível executar a anonimização.');
                confirmationModal.hide();
                alert(data.message || 'Usuário anonimizado com sucesso.');
                renderView('dpo');
            } catch (err) {
                alert(err.message);
                confirmationModal.hide();
            }
        }, { once: true });
        confirmationModal.show();
    }
    async function handleDpoResponseSubmit(e) {
        if (!e.target.classList.contains('dpo-response-form')) {
            return;
        }
        e.preventDefault();
        const form = e.target;
        const requestId = form.dataset.requestId;
        const responseText = form.elements['response_text'].value;
        const submitButton = form.querySelector('button[type="submit"]');
        submitButton.disabled = true;
        submitButton.textContent = 'Enviando...';
        try {
            const response = await fetch(`${API_URL}/admin/dpo-request/${requestId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    admin_user_id: currentUser.id,
                    response_text: responseText
                })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Erro ao enviar resposta.');
            renderView('dpo');
        } catch (error) {
            alert(`Erro: ${error.message}`);
            submitButton.disabled = false;
            submitButton.textContent = 'Enviar Resposta';
        }
    }
    async function loadMyDpoRequests() {
        const container = document.getElementById('my-dpo-requests-list');
        if (!container) return; 
        try {
            const response = await fetch(`${API_URL}/user/dpo-requests?user_id=${currentUser.id}`);
            if (!response.ok) throw new Error('Não foi possível carregar suas solicitações.');
            const requests = await response.json();
            if (requests.length === 0) {
                container.innerHTML = '<p class="text-center text-muted small m-0">Você ainda não fez nenhuma solicitação.</p>';
                return;
            }
            let html = '<div class="list-group list-group-flush">';
            requests.forEach(req => {
                const createdAt = new Date(req.created_at).toLocaleString('pt-BR');
                let responseHtml = '';
                const requestTypesMap = {
                    'access': 'Solicitação de Acesso',
                    'correction': 'Solicitação de Correção',
                    'anonymization': 'Solicitação de Anonimização',
                    'anonymization_request': 'Solicitação de Anonimização',
                    'question': 'Dúvida Geral'
                };
                const requestTypeDisplay = requestTypesMap[req.request_type] || req.request_type;
                if (req.request_type === 'anonymization_request' || req.request_type === 'anonymization') {
                    if (req.status === 'pending' && req.scheduled_for) {
                        const scheduledDate = new Date(req.scheduled_for).toLocaleDateString('pt-BR');
                        responseHtml = `
                            <div class="mt-2">
                                <span class="badge bg-warning text-dark">Pendente</span>
                                <p class="small text-muted mb-0 mt-1">Sua conta está agendada para anonimização em: <strong>${scheduledDate}</strong>.</p>
                            </div>
                        `;
                    } else if (req.status === 'answered') {
                        responseHtml = `<div class="mt-2"><span class="badge bg-success">Processado</span></div>`;
                    }
                } else if (req.status === 'answered') {
                    const respondedAt = new Date(req.responded_at).toLocaleString('pt-BR');
                    responseHtml = `
                        <div class="mt-2 p-2 bg-light border rounded" style="font-size: 0.9rem;">
                            <strong class="text-success">Resposta do DPO (${req.admin_username || 'Admin'} em ${respondedAt}):</strong>
                            <p class="mb-0 mt-1">${req.response_text}</p>
                        </div>
                    `;
                } else {
                     responseHtml = `
                        <div class="mt-2">
                            <span class="badge bg-warning text-dark">Pendente</span>
                        </div>
                     `;
                }
                html += `
                    <div class="list-group-item px-0 py-3">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1">${requestTypeDisplay}</h6>
                            <small class="text-muted">${createdAt}</small>
                        </div>
                        <p class="mb-1 text-muted small"><strong>Sua Mensagem:</strong> ${req.message_text}</p>
                        ${responseHtml}
                    </div>
                `;
            });
            html += '</div>';
            container.innerHTML = html;
        } catch (error) {
            container.innerHTML = `<p class="text-danger small">${error.message}</p>`;
        }
    }
    async function loadMyActivityLog() {
        const container = document.getElementById('user-activity-log-container');
        if (!container) return; 
        try {
            const response = await fetch(`${API_URL}/user/my-activity-log?user_id=${currentUser.id}`);
            if (!response.ok) throw new Error('Não foi possível carregar seu histórico de conclusões.');
            const logs = await response.json();
            if (logs.length === 0) {
                container.innerHTML = '<p class="text-center text-muted small m-0">Nenhuma atividade de conclusão registrada.</p>';
                return;
            }
            let tableHtml = `
                <table class="table table-striped table-hover user-activity-log-table">
                    <thead class="table-light">
                        <tr>
                            <th scope="col">Ação</th>
                            <th scope="col">Data e Hora</th>
                        </tr>
                    </thead>
                    <tbody>`;
            logs.forEach(log => {
                const timestamp = new Date(log.timestamp).toLocaleString('pt-BR');
                tableHtml += `
                    <tr>
                        <td>${log.action_text}</td>
                        <td>${timestamp}</td>
                    </tr>`;
            });
            tableHtml += `</tbody></table>`;
            container.innerHTML = tableHtml;
        } catch (error) {
            container.innerHTML = `<p class="text-danger small">${error.message}</p>`;
        }
    }
    function handleAdminDeleteDpoRequest(requestId) {
        const confirmationText = 'Tem certeza que deseja EXCLUIR permanentemente esta solicitação DPO? Esta ação não pode ser desfeita.';
        document.getElementById('confirmation-modal-body').textContent = confirmationText;
        const confirmBtn = document.getElementById('confirm-action-btn');
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        newConfirmBtn.addEventListener('click', async () => {
            try {
                const res = await fetch(`${API_URL}/admin/dpo-request/${requestId}`, { 
                    method: 'DELETE', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ admin_user_id: currentUser.id })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Não foi possível excluir a solicitação.');
                confirmationModal.hide();
                renderView('dpo');
            } catch (err) {
                alert(err.message);
                confirmationModal.hide();
            }
        }, { once: true });
        confirmationModal.show();
    }
    function handleAdminPurgeChat() {
        const confirmationText = 'ATENÇÃO: Você confirma a exclusão permanente de todas as mensagens do chat? Esta ação é irreversível.';
        document.getElementById('confirmation-modal-body').textContent = confirmationText;
        const confirmBtn = document.getElementById('confirm-action-btn');
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        newConfirmBtn.addEventListener('click', async () => {
            try {
                const res = await fetch(`${API_URL}/admin/chat/purge`, { 
                    method: 'DELETE', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ admin_user_id: currentUser.id })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Não foi possível limpar o chat.');
                confirmationModal.hide();
                alert(data.message || 'Histórico de chat limpo com sucesso.');
                const chatMessagesEl = document.getElementById('chat-messages');
                if (chatMessagesEl) {
                    chatMessagesEl.innerHTML = '';
                }
            } catch (err) {
                alert(err.message);
                confirmationModal.hide();
            }
        }, { once: true });
        confirmationModal.show();
    }
    function handleAdminPurgeLog() {
        const confirmationText = 'ATENÇÃO: Você confirma a exclusão permanente de todo o Log de Atividades? Esta ação é irreversível.';
        document.getElementById('confirmation-modal-body').textContent = confirmationText;
        const confirmBtn = document.getElementById('confirm-action-btn');
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        newConfirmBtn.addEventListener('click', async () => {
            try {
                const res = await fetch(`${API_URL}/admin/activity-log/purge`, { 
                    method: 'DELETE', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ admin_user_id: currentUser.id })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Não foi possível limpar o log.');
                confirmationModal.hide();
                alert(data.message || 'Log de Atividades limpo com sucesso.');
                renderView('log');
            } catch (err) {
                alert(err.message);
                confirmationModal.hide();
            }
        }, { once: true });
        confirmationModal.show();
    }
    async function renderCategoryManagementView() {
        mainContent.innerHTML = `
            <div class="content-header">
                <h2>Gerenciar Categorias (Pastas)</h2>
            </div>
            <div class="row">
                <div class="col-lg-4">
                    <div class="card">
                        <div class="card-header"><h5 id="category-form-title" class="mb-0">Adicionar Nova Categoria</h5></div>
                        <div class="card-body">
                            <form id="category-form">
                                <input type="hidden" id="category-form-id" value="">
                                <div class="mb-3">
                                    <label for="category-name" class="form-label">Nome da Categoria</label>
                                    <input type="text" id="category-name" class="form-control" required>
                                </div>
                                <div class="mb-3">
                                    <label for="category-description" class="form-label">Descrição (Opcional)</label>
                                    <textarea id="category-description" class="form-control" rows="3"></textarea>
                                </div>
                                <div id="category-form-error" class="error-message"></div>
                                <div class="d-flex justify-content-end gap-2">
                                    <button type="button" id="category-form-cancel" class="btn btn-secondary" style="display: none;">Cancelar</button>
                                    <button type="submit" class="btn btn-primary">Salvar</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
                <div class="col-lg-8">
                    <div class="card">
                        <div class="card-header"><h5 class="mb-0">Categorias Existentes</h5></div>
                        <div class="card-body">
                            <div id="category-list-container">
                                <div class="text-center p-5"><div class="spinner-border text-primary" role="status"></div></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.getElementById('category-form').addEventListener('submit', handleAdminSaveCategory);
        document.getElementById('category-form-cancel').addEventListener('click', resetCategoryForm);
        document.getElementById('category-list-container').addEventListener('click', handleCategoryListClick);
        loadCategories();
    }
    async function loadCategories() {
        const container = document.getElementById('category-list-container');
        if (!container) return;
        try {
            const res = await fetch(`${API_URL}/categories`);
            if (!res.ok) throw new Error('Não foi possível carregar as categorias.');
            const categories = await res.json();
            if (categories.length === 0) {
                container.innerHTML = '<p class="text-muted text-center">Nenhuma categoria encontrada.</p>';
                return;
            }
            let tableHtml = `
                <table class="table table-hover">
                    <thead class="table-light">
                        <tr>
                            <th>Nome</th>
                            <th>Descrição</th>
                            <th>Tarefas</th>
                            <th>Usuários</th>
                            <th class="text-end">Ações</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            categories.forEach(cat => {
                const safeName = cat.name.replace(/"/g, '&quot;');
                const safeDescription = (cat.description || '').replace(/"/g, '&quot;');
                tableHtml += `
                    <tr>
                        <td class="fw-bold">${cat.name}</td>
                        <td class="text-muted small">${cat.description || 'N/A'}</td>
                        <td class="text-center">${cat.task_count || 0}</td>
                        <td class="text-center">${cat.user_count || 0}</td>
                        <td class="actions-cell" style="text-align: right; min-width: 160px;">
                            <button class="btn btn-sm btn-outline-info" data-action="users" data-id="${cat.id}" data-name="${safeName}" title="Gerenciar Usuários">
                                <i class="bi bi-people-fill"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-primary" data-action="edit" data-id="${cat.id}" 
                                    data-name="${safeName}" data-description="${safeDescription}" title="Editar">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" data-action="delete" data-id="${cat.id}" 
                                    data-name="${safeName}" data-taskcount="${cat.task_count || 0}" title="Excluir">
                                <i class="bi bi-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
            });
            tableHtml += '</tbody></table>';
            container.innerHTML = tableHtml;
        } catch (error) {
            container.innerHTML = `<p class="text-danger text-center">${error.message}</p>`;
        }
    }
    function handleCategoryListClick(e) {
        const button = e.target.closest('button[data-action]');
        if (!button) return;
        const action = button.dataset.action;
        const id = button.dataset.id;
        const name = button.dataset.name;
        if (action === 'edit') {
            document.getElementById('category-form-title').textContent = `Editar Categoria: ${name}`;
            document.getElementById('category-form-id').value = id;
            document.getElementById('category-name').value = name;
            document.getElementById('category-description').value = button.dataset.description;
            document.getElementById('category-form-cancel').style.display = 'inline-block';
            document.querySelector('#category-form button[type="submit"]').textContent = 'Salvar Alterações';
            document.getElementById('category-name').focus();
        }
        if (action === 'delete') {
            const taskCount = button.dataset.taskcount;
            handleAdminDeleteCategory(id, name, taskCount);
        }
        if (action === 'users') {
            handleOpenCategoryUsersModal(id, name);
        }
    }
    function resetCategoryForm() {
        document.getElementById('category-form-title').textContent = 'Adicionar Nova Categoria';
        document.getElementById('category-form').reset();
        document.getElementById('category-form-id').value = '';
        document.getElementById('category-form-cancel').style.display = 'none';
        document.querySelector('#category-form button[type="submit"]').textContent = 'Salvar';
        document.getElementById('category-form-error').textContent = '';
    }
    async function handleAdminSaveCategory(e) {
        e.preventDefault();
        const form = e.target;
        const categoryId = form.elements['category-form-id'].value;
        const name = form.elements['category-name'].value.trim();
        const description = form.elements['category-description'].value.trim();
        const errorEl = document.getElementById('category-form-error');
        errorEl.textContent = '';
        const payload = {
            admin_user_id: currentUser.id,
            name: name,
            description: description
        };
        let url = `${API_URL}/admin/categories`;
        let method = 'POST';
        if (categoryId) {
            url = `${API_URL}/admin/categories/${categoryId}`;
            method = 'PUT';
        }
        try {
            const res = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Erro ao salvar categoria.');
            resetCategoryForm();
            loadCategories();
        } catch (error) {
            errorEl.textContent = error.message;
        }
    }
    function handleAdminDeleteCategory(id, name, taskCount) {
        let confirmationText = `Tem certeza que deseja excluir a categoria '${name}'? `;
        if (taskCount > 0) {
            confirmationText += `Isso afetará ${taskCount} tarefa(s), que ficarão "Sem Categoria".`;
        } else {
            confirmationText += `Nenhuma tarefa será afetada.`;
        }
        confirmationText += " Esta ação é irreversível.";
        document.getElementById('confirmation-modal-body').textContent = confirmationText;
        const confirmBtn = document.getElementById('confirm-action-btn');
        const newConfirmBtn = confirmBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        newConfirmBtn.addEventListener('click', async () => {
            try {
                const res = await fetch(`${API_URL}/admin/categories/${id}`, { 
                    method: 'DELETE', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ admin_user_id: currentUser.id })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Não foi possível excluir a categoria.');
                confirmationModal.hide();
                loadCategories();
            } catch (err) {
                alert(err.message);
                confirmationModal.hide();
            }
        }, { once: true });
        confirmationModal.show();
    }
    async function updateDpoBadge() {
        if (!currentUser || currentUser.role !== 'admin' || currentUser.impersonating) {
            return;
        }
        try {
            const cacheBuster = `&_=${new Date().getTime()}`;
            const res = await fetch(`${API_URL}/admin/dpo-pending-count?admin_user_id=${currentUser.id}${cacheBuster}`);
            const dpoBadge = document.getElementById('dpo-notification-badge');
            if (!dpoBadge) return;
            if (res.ok) {
                const data = await res.json();
                const isDpoViewActive = document.querySelector(`#sidebar .components li[data-view="dpo"]`)?.classList.contains('active');
                if (data.pendingCount > 0 && !isDpoViewActive) {
                    dpoBadge.textContent = data.pendingCount;
                    dpoBadge.style.display = 'flex';
                } else {
                    dpoBadge.style.display = 'none';
                }
            } else {
                dpoBadge.style.display = 'none';
            }
        } catch (e) {
            const dpoBadge = document.getElementById('dpo-notification-badge');
            if (dpoBadge) dpoBadge.style.display = 'none';
        }
    }
    async function initializeNotificationState() {
        setInterval(pollForNotifications, 5000); 
        pollForNotifications();
    }
    async function pollForNotifications() {
        if (!currentUser) return; 
        const cacheBuster = `&_=${new Date().getTime()}`;
        try {
            const res = await fetch(`${API_URL}/chat/unread-count?user_id=${currentUser.id}${cacheBuster}`);
            if (res.ok) {
                const data = await res.json();
                if (data.unreadCount > 0) {
                    const chatWindow = document.getElementById('chat-window');
                    const isChatOpen = window.getComputedStyle(chatWindow).display === 'flex';
                    if (isChatOpen) {
                        await renderChatMessages();
                    } else {
                        document.getElementById('chat-notification-badge').style.display = 'block';
                    }
                } else {
                     document.getElementById('chat-notification-badge').style.display = 'none';
                }
            }
        } catch(e) { /* Falha silenciosamente */ }
    }
    async function markChatAsRead() {
        document.getElementById('chat-notification-badge').style.display = 'none';
        try {
            await fetch(`${API_URL}/chat/mark-as-read`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUser.id })
            });
        } catch (e) {
            console.error("Falha ao marcar chat como lido.", e);
        }
    }
    async function populateDashboardCategoryFilter() {
        const selectElement = document.getElementById('category-filter-select');
        if (!selectElement) return;
        try {
            const res = await fetch(`${API_URL}/categories`);
            if (!res.ok) throw new Error('Falha ao buscar categorias para o filtro');
            const categories = await res.json();
            categories.forEach(cat => {
                selectElement.innerHTML += `<option value="${cat.id}">${cat.name}</option>`;
            });
            selectElement.value = currentCategoryFilter;
        } catch (error) {
            console.error(error.message);
        }
    }
    function handleCategoryFilterChange(e) {
        currentCategoryFilter = e.target.value;
        renderTasks(); 
        const adminCategorySelect = document.getElementById('task-category');
        if (adminCategorySelect) {
            if (currentCategoryFilter !== 'all' && currentCategoryFilter !== 'none') {
                adminCategorySelect.value = currentCategoryFilter;
            } else {
                adminCategorySelect.value = "";
            }
        }
    }
    async function handleOpenAssignCategoriesModal(userId, username) {
        document.getElementById('assign-categories-username').textContent = username;
        document.getElementById('assign-categories-userid').value = userId;
        const listContainer = document.getElementById('assign-categories-list');
        listContainer.innerHTML = '<div class="text-center p-3"><div class="spinner-border spinner-border-sm text-primary" role="status"></div></div>';
        assignCategoriesModal.show();
        try {
            const resAll = await fetch(`${API_URL}/categories`);
            if (!resAll.ok) throw new Error('Falha ao buscar lista de categorias.');
            const allCategories = await resAll.json();
            const resUser = await fetch(`${API_URL}/admin/user/${userId}/categories?admin_user_id=${currentUser.id}`);
            if (!resUser.ok) throw new Error('Falha ao buscar categorias do usuário.');
            const userCategoryIds = await resUser.json();
            if (allCategories.length === 0) {
                listContainer.innerHTML = '<p class="text-muted text-center">Nenhuma categoria cadastrada. Crie categorias na tela "Categorias" primeiro.</p>';
                return;
            }
            let html = '';
            allCategories.forEach(cat => {
                const isChecked = userCategoryIds.includes(cat.id);
                html += `
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" value="${cat.id}" id="cat-${cat.id}" 
                               name="category_ids" ${isChecked ? 'checked' : ''}>
                        <label class="form-check-label" for="cat-${cat.id}">
                            <strong>${cat.name}</strong>
                        </label>
                    </div>
                `;
            });
            listContainer.innerHTML = html;
        } catch (error) {
            document.getElementById('assign-categories-error').textContent = error.message;
        }
    }
    async function handleAdminSaveUserCategories(e) {
        e.preventDefault();
        const form = e.target;
        const userId = form.elements['assign-categories-userid'].value;
        const errorEl = document.getElementById('assign-categories-error');
        errorEl.textContent = '';
        const checkedBoxes = form.querySelectorAll('input[name="category_ids"]:checked');
        const selectedCategoryIds = Array.from(checkedBoxes).map(cb => parseInt(cb.value));
        const payload = {
            admin_user_id: currentUser.id,
            category_ids: selectedCategoryIds
        };
        try {
            const res = await fetch(`${API_URL}/admin/user/${userId}/categories`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Erro ao salvar permissões.');
            assignCategoriesModal.hide();
        } catch (error) {
            errorEl.textContent = error.message;
        }
    }
    async function handleOpenCategoryUsersModal(categoryId, categoryName) {
        document.getElementById('manage-category-name').textContent = categoryName;
        document.getElementById('manage-category-id').value = categoryId;
        const listContainer = document.getElementById('manage-category-users-list');
        listContainer.innerHTML = '<div class="text-center p-3"><div class="spinner-border spinner-border-sm text-primary" role="status"></div></div>';
        manageCategoryUsersModal.show();
        try {
            const res = await fetch(`${API_URL}/admin/category/${categoryId}/users?admin_user_id=${currentUser.id}`);
            if (!res.ok) throw new Error('Falha ao buscar lista de usuários.');
            const allUsers = await res.json();
            if (allUsers.length === 0) {
                listContainer.innerHTML = '<p class="text-muted text-center">Nenhum funcionário cadastrado no sistema.</p>';
                return;
            }
            let html = '';
            allUsers.forEach(user => {
                html += `
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" value="${user.id}" id="user-${user.id}" 
                               name="user_ids" ${user.is_associated ? 'checked' : ''}>
                        <label class="form-check-label" for="user-${user.id}">
                            <strong>${user.username}</strong> <span class="text-muted small">(${user.job_title || 'Funcionário'})</span>
                        </label>
                    </div>
                `;
            });
            listContainer.innerHTML = html;
        } catch (error) {
            document.getElementById('manage-category-users-error').textContent = error.message;
        }
    }
    async function handleAdminSaveCategoryUsers(e) {
        e.preventDefault();
        const form = e.target;
        const categoryId = form.elements['manage-category-id'].value;
        const errorEl = document.getElementById('manage-category-users-error');
        errorEl.textContent = '';
        const checkedBoxes = form.querySelectorAll('input[name="user_ids"]:checked');
        const selectedUserIds = Array.from(checkedBoxes).map(cb => parseInt(cb.value));
        const payload = {
            admin_user_id: currentUser.id,
            user_ids: selectedUserIds
        };
        try {
            const res = await fetch(`${API_URL}/admin/category/${categoryId}/users`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Erro ao salvar permissões.');
            manageCategoryUsersModal.hide();
            if (document.getElementById('category-list-container')) {
                 loadCategories();
            }
        } catch (error) {
            errorEl.textContent = error.message;
        }
    }
    
    // --- ================================== ---
    // --- ATUALIZAÇÃO: Novas Funções 2FA (Handlers)
    // --- ================================== ---

    /**
     * Etapa 1: Inicia a configuração do 2FA
     */
    async function handleEnable2FA() {
        try {
            const res = await fetch(`${API_URL}/user/totp-setup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUser.id })
            });
            
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Erro ao iniciar configuração 2FA.');
            
            // Temos o URI do QR Code (data.provisioning_uri)
            initializeModalsAndChat();
            
            // Limpa o estado anterior
            document.getElementById('setup-2fa-form').reset();
            document.getElementById('setup-2fa-error').textContent = '';
            document.getElementById('setup-2fa-secret').textContent = data.secret; // Mostra a chave secreta
            
            // Gera o QR Code
            const qrContainer = document.getElementById('setup-2fa-qr-code');
            qrContainer.innerHTML = ''; // Limpa o QR anterior
            try {
                // Verifica se a biblioteca qrcode foi carregada
                if (typeof qrcode === 'undefined') {
                    throw new Error('Biblioteca QR Code não foi carregada.');
                }
                const qr = qrcode(0, 'M'); // (typeNumber 0 = auto-detect size, 'M' = error correction level)
                qr.addData(data.provisioning_uri);
                qr.make();
                qrContainer.innerHTML = qr.createImgTag(5); // (cell_size = 5px)
            } catch (qrError) {
                console.error("Erro ao gerar QR Code:", qrError);
                qrContainer.innerHTML = '<p class="text-danger">Erro ao gerar QR Code. Tente usar a chave secreta manual.</p>';
            }
            
            setup2faModal.show();
            
        } catch (error) {
            alert(error.message);
        }
    }
    
    /**
     * Etapa 2: Verifica o código 2FA do usuário para ativar
     */
    async function handleVerify2FA(e) {
        e.preventDefault();
        const err = document.getElementById('setup-2fa-error');
        const code = document.getElementById('setup-2fa-code').value;
        err.textContent = '';
        
        try {
            const res = await fetch(`${API_URL}/user/totp-verify-setup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUser.id, totp_code: code })
            });
            
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Erro ao verificar código.');
            
            // Sucesso!
            setup2faModal.hide();
            alert('Autenticação de Dois Fatores (2FA) foi ativada com sucesso!');
            loadProfileData(); // Recarrega o card de perfil
            
        } catch (error) {
            err.textContent = error.message;
        }
    }
    
    /**
     * Desativa o 2FA
     */
    async function handleDisable2FA(e) {
        e.preventDefault();
        const err = document.getElementById('disable-2fa-error');
        const password = document.getElementById('disable-2fa-password').value;
        err.textContent = '';
        
        try {
             const res = await fetch(`${API_URL}/user/totp-disable`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: currentUser.id, password: password })
            });
            
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Erro ao desativar 2FA.');
            
            // Sucesso!
            disable2faModal.hide();
            alert('Autenticação de Dois Fatores (2FA) foi desativada.');
            loadProfileData(); // Recarrega o card de perfil
            
        } catch (error) {
            err.textContent = error.message;
        }
    }

});
