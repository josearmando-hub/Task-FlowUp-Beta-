# Task FlowUp

![Logo do Task FlowUp](image-2.1.png)

O **Task FlowUp** é uma aplicação full-stack para gerenciamento de tarefas, projetada como uma plataforma interna (SaaS) para equipes. O sistema oferece ferramentas robustas para gestão de projetos, comunicação e monitoramento de produtividade, com foco prioritário em segurança (JWT, 2FA) e conformidade com a LGPD.

A interface utiliza um design **Neobrutalista**, caracterizado por alto contraste, bordas sólidas e sombras nítidas para garantir máxima legibilidade e uma estética moderna.

---

## 🚀 Funcionalidades do Sistema

A plataforma opera com níveis de permissão distintos (Administrador e Funcionário) e implementa uma arquitetura de segurança *stateless*.

### 1. Autenticação e Segurança (Atualizado com JWT)

* **Autenticação Stateless (JWT):** O sistema agora utiliza **JSON Web Tokens (JWT)** para gerenciar sessões. Ao fazer login, o backend emite um token assinado (válido por 24h) que o frontend armazena e anexa automaticamente ao cabeçalho `Authorization: Bearer` de cada requisição subsequente.
* **Tratamento de Sessão:** O frontend intercepta erros `401 Unauthorized` (token expirado) e realiza o logout automático do usuário para segurança.
* **Hashing de Senha:** Utiliza **PBKDF2-HMAC-SHA256** com salt exclusivo. Hashes legados são migrados automaticamente para o novo padrão no login.
* **Autenticação de Dois Fatores (2FA):** Suporte completo a TOTP (Google Authenticator/Authy). O login exige o token JWT *e* a validação do código 2FA se ativado.
* **Registro Seguro:** O cadastro de administradores é protegido por uma chave de API (`ADMIN_KEY`) definida no servidor.

### 2. Conformidade e LGPD (Novas Interfaces)

* **Consentimento e Transparência:**
    * **Modal de Termos:** Um modal detalhado de Termos de Serviço e Política de Privacidade é exibido no registro e acessível via rodapé.
    * **Banner de Cookies:** Um banner fixo solicita consentimento para armazenamento local na primeira visita, salvando a preferência do usuário.
* **Central DPO:** Usuários podem abrir solicitações formais (acesso, correção, exclusão) diretamente pela plataforma.
* **Direito ao Esquecimento:** Fluxo automatizado onde o usuário solicita a auto-exclusão, agendando uma anonimização dos dados para 7 dias.

### 3. Gestão de Tarefas e Acesso (RBAC)

* **Dashboard Interativo:** Filtragem em tempo real (Todas, Minhas, Atrasadas), busca por texto e painel de tarefas "Vencendo em Breve".
* **Categorias e Permissões:** Administradores criam categorias (ex: "Financeiro") e definem quais usuários têm acesso a elas. O backend filtra as tarefas para garantir que funcionários só vejam o que lhes é permitido.
* **Colaboração:** Sistema de comentários em tarefas com notificações de "não lido".

### 4. Painel Administrativo (SSAP)

* **Gestão de Usuários:** Edição completa de perfis, reset forçado de senhas e gerenciamento de associações a categorias.
* **Impersonação (Atualizada):** O admin pode "logar como" um funcionário para auditoria. O sistema agora gerencia tokens JWT duplos (admin original + usuário alvo) para permitir um retorno seguro à sessão administrativa.
* **Auditoria:** Logs de atividade detalhados e ferramentas de limpeza (purge) para chat e logs.

---

## 🛠️ Pilha de Tecnologia

### Backend (`app.py`)
* **Linguagem:** Python 3.9+
* **Framework:** Flask
* **Autenticação:** `PyJWT` (Novo), `pyotp` (2FA), `hashlib` (PBKDF2)
* **Banco de Dados:** MySQL (via `Flask-MySQLdb`)
* **API:** RESTful com CORS habilitado

### Frontend (`script.js`, `index.html`)
* **Lógica:** JavaScript (Vanilla ES6+)
* **Estilo:** CSS3 (Neobrutalismo)
* **UI Framework:** Bootstrap 5 (Modais e Grid)
* **Bibliotecas:** `qrcode.min.js` (Geração de QR Code para 2FA)

---

## 🔧 Instalação e Execução

Siga estes passos atualizados para configurar o ambiente com suporte a JWT.

### 1. Pré-requisitos

* Python 3.9+
* MySQL Server em execução
* `pip` instalado

### 2. Configuração do Backend

1.  Crie e ative seu ambiente virtual:
    ```bash
    python -m venv venv
    source venv/bin/activate  # (Linux/Mac)
    # ou venv\Scripts\activate (Windows)
    ```

2.  Instale as dependências (incluindo a nova lib `PyJWT`):
    ```bash
    pip install Flask Flask-MySQLdb flask-cors pyotp PyJWT
    ```

3.  **Variáveis de Ambiente (Crítico):**
    Você precisa definir a `SECRET_KEY` para assinar os tokens JWT, além das credenciais de banco e chave de admin.

    *No Linux/macOS:*
    ```bash
    export MYSQL_PASSWORD="sua_senha_mysql"
    export ADMIN_KEY="sua_chave_admin_secreta"
    export SECRET_KEY="sua_chave_jwt_super_segura_e_longa"
    ```

    *No Windows (PowerShell):*
    ```powershell
    $env:MYSQL_PASSWORD = "sua_senha_mysql"
    $env:ADMIN_KEY = "sua_chave_admin_secreta"
    $env:SECRET_KEY = "sua_chave_jwt_super_segura_e_longa"
    ```

4.  Inicie o servidor:
    ```bash
    python app.py
    ```
    O servidor rodará em `http://127.0.0.1:5001`.

### 3. Configuração do Banco de Dados

1.  Acesse seu MySQL e crie o banco:
    ```sql
    CREATE DATABASE task_flowup CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    ```
2.  **Importante:** Como o arquivo `schema.sql` não foi fornecido, as tabelas (`users`, `tasks`, `task_categories`, `dpo_requests`, etc.) devem ser criadas manualmente baseando-se nas queries SQL presentes no `app.py`.

### 4. Execução do Frontend

1.  Certifique-se de que `index.html`, `script.js`, `style.css` e `image.png` estão na mesma pasta.
2.  Abra o `index.html` no navegador.
3.  O frontend se conectará automaticamente à API local.

---

## 📂 Estrutura do Projeto
## 📂 Estrutura do Projetoomaticamente para o login.
