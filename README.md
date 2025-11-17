# Task FlowUp

![Logo do Task FlowUp](imagem-2.0.png)

O **Task FlowUp** é uma aplicação full-stack completa para gerenciamento de tarefas, projetada como uma plataforma interna (SaaS) para equipes. Ele fornece ferramentas robustas para gerenciamento de projetos, comunicação de equipe e monitoramento de produtividade, com um forte foco em segurança (2FA, Hashing PBKDF2) e conformidade com a LGPD.

A aplicação utiliza um design **Neobrutalista**, focado em alto contraste, bordas sólidas e sombras nítidas para uma interface de usuário moderna e acessível.

---

## 🚀 Principais Funcionalidades

A plataforma é dividida por níveis de permissão (Administrador e Funcionário), oferecendo um conjunto de recursos que vão desde o gerenciamento básico de tarefas até ferramentas avançadas de auditoria e segurança.

### 1. Autenticação e Segurança (Foco Principal)

* **Hashing de Senha Robusto:** Utiliza **PBKDF2-HMAC-SHA256** com 250.000 iterações e um `salt` criptográfico exclusivo para cada usuário.
* **Migração de Hash:** O sistema detecta e migra automaticamente hashes de senha legados (SHA256 simples) para o novo formato PBKDF2 no momento do login.
* **Autenticação de Dois Fatores (2FA):** Os usuários podem habilitar o 2FA (baseado em TOTP) em seus perfis, exigindo um código de aplicativo (como Google Authenticator) no login.
* **Chave de Administrador:** O registro de contas de `admin` é protegido por uma chave secreta (`ADMIN_REGISTRATION_KEY`) definida no ambiente do servidor.
* **Validação de Frontend:** Feedback em tempo real no formulário de registro sobre a força da senha (requisitos de maiúsculas, minúsculas, números e símbolos).

### 2. Gestão de Tarefas (CRUD)

* **Dashboard Completo:** Criação, edição e exclusão de tarefas.
* **Atribuição e Detalhes:** Tarefas incluem prioridade, prazo e usuário atribuído.
* **Comentários por Tarefa:** Cada tarefa possui uma seção de comentários.
* **Notificações de Leitura:** O sistema rastreia quais comentários o usuário ainda não leu em cada tarefa, exibindo um contador no card.
* **Filtros e Busca:** O dashboard permite filtrar tarefas (Todas, Minhas, Atrasadas) e fazer busca em tempo real.
* **Painel "Vencendo em Breve":** Um painel de destaque mostra tarefas que vencem nos próximos 7 dias.

### 3. Controle de Acesso e Categorias (RBAC)

* **Gerenciamento de Categorias:** Administradores podem criar, editar e excluir "Categorias" (como pastas) para organizar tarefas.
* **Controle de Acesso (M2M):** Administradores podem definir **quais funcionários** têm permissão para ver **quais categorias**.
* **Visão Segura:** Funcionários só podem visualizar tarefas que (1) pertencem a uma categoria à qual têm acesso, ou (2) não possuem categoria (consideradas "públicas").

### 4. Painel de Administração (SSAP)

* **Gerenciamento de Usuários (SSAP):** Uma visão (`/api/admin/users`) que permite ao admin ver, editar e excluir qualquer usuário do sistema.
* **Impersonação de Usuário:** O admin pode "logar como" um funcionário para ver a plataforma de sua perspectiva, ideal para auditoria de permissões ou suporte.
* **Redefinição de Senha Forçada:** O admin pode forçar qualquer usuário a redefinir sua senha no próximo login.
* **Log de Atividades:** Um log de auditoria detalhado registra ações importantes (logins, criação de tarefas, exclusão de usuários, etc.).
* **Limpeza de Dados (Purge):** Funções perigosas para limpar permanentemente todo o histórico de chat ou o log de atividades.

### 5. Conformidade com LGPD (Central DPO)

* **Canal do Titular:** Usuários podem, de seus perfis, abrir solicitações formais ao DPO (Encarregado de Proteção de Dados) para "acesso", "correção" ou "exclusão" de dados.
* **Central DPO (Admin):** Admins têm uma visão dedicada para gerenciar e responder a todas as solicitações de LGPD, com um contador de pendências na sidebar.
* **Fluxo de Auto-Exclusão:** Quando um usuário solicita a exclusão da própria conta, o sistema agenda automaticamente uma **anonimização** para 7 dias.
* **Anonimização (Não Exclusão):** A exclusão de um usuário (seja pelo admin ou auto-solicitada) não é um `DELETE` destrutivo. O sistema **anonimiza** os dados (ex: `username` vira `usuario_anonimizado_123`), preservando a integridade de registros históricos (tarefas, comentários) sem manter dados pessoais identificáveis (PII).

### 6. Comunicação

* **Chat Global:** Um chat em tempo real disponível para todos os usuários da organização.
* **Notificações de Chat:** Um ícone de notificação indica novas mensagens não lidas no chat.

---

## 🛠️ Pilha de Tecnologia (Stack)

### Backend (app.py)

* **Framework:** Flask
* **Banco de Dados:** MySQL (via `Flask-MySQLdb`)
* **Segurança (2FA):** `pyotp`
* **Segurança (Hashing):** `hashlib` (PBKDF2)
* **API:** RESTful, com CORS habilitado (`Flask-CORS`)

### Frontend (script.js, index.html)

* **Lógica:** JavaScript Puro (Vanilla ES6+)
* **Estrutura:** HTML5
* **Estilo:** CSS3 com design Neobrutalista
* **UI (Componentes):** Bootstrap 5
* **QR Code (2FA):** `qrcode.min.js`

### Banco de Dados (Não fornecido)

* **Tipo:** MySQL
* **Observação:** O schema do banco de dados (`schema.sql`) não foi fornecido. Ele deve ser criado manualmente com base nas consultas SQL presentes em `app.py`.

---

## 🔧 Instalação e Execução

Siga estes passos para configurar e rodar o projeto localmente.

### 1. Pré-requisitos

* Python 3.9+
* Servidor de banco de dados MySQL (ou MariaDB)
* `pip` (gerenciador de pacotes do Python)

### 2. Configuração do Banco de Dados

1.  Acesse seu cliente MySQL.
2.  Crie o banco de dados para a aplicação:
    ```sql
    CREATE DATABASE task_flowup CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    ```
3.  **Etapa Crítica:** Você deve criar manualmente todas as tabelas (ex: `users`, `tasks`, `task_categories`, `dpo_requests`, `activity_log`, etc.) com base nas consultas SQL encontradas em `app.py`.

### 3. Configuração do Backend (Flask)

1.  Crie e ative um ambiente virtual:
    ```bash
    python -m venv venv
    source venv/bin/activate  # (ou venv\Scripts\activate no Windows)
    ```
2.  Instale as dependências do Python:
    ```bash
    pip install Flask Flask-MySQLdb flask-cors pyotp
    ```
3.  Defina as variáveis de ambiente necessárias para o `app.py`:
    * `MYSQL_PASSWORD`: A senha do seu banco de dados.
    * `ADMIN_KEY`: A chave secreta para registro de admins (ex: `admin-secret-key-123`).

    *No Linux/macOS:*
    ```bash
    export MYSQL_PASSWORD="sua_senha_mysql"
    export ADMIN_KEY="sua_chave_admin_secreta"
    ```
    *No Windows (PowerShell):*
    ```powershell
    $env:MYSQL_PASSWORD = "sua_senha_mysql"
    $env:ADMIN_KEY = "sua_chave_admin_secreta"
    ```
4.  Execute o servidor Flask (ele rodará na porta `5001`):
    ```bash
    python app.py
    ```

### 4. Execução do Frontend

1.  Garanta que todos os arquivos (`index.html`, `script.js`, `style.css`, `image.png`) estejam na mesma pasta.
2.  **Abra o arquivo `index.html` diretamente no seu navegador** (ex: Google Chrome, Firefox).

O `script.js` está configurado para se comunicar automaticamente com a API em `http://127.0.0.1:5001`.

---

## 📂 Estrutura do Projeto
