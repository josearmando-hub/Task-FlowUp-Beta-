# Task FlowUp

![Logo do Task FlowUp](image-2.1.png)

O Task FlowUp** é uma plataforma SaaS *full-stack* para gerenciamento de tarefas e equipes. O projeto combina uma interface moderna e de alto contraste (Neobrutalismo) com um backend robusto em Flask, focado em segurança (JWT, 2FA, Hashing) e conformidade com a LGPD.

---

## 🎨 Design System

A interface segue uma estética **Neobrutalista**, caracterizada por:
* **Alto Contraste:** Cores vibrantes (`#10b981` Verde, `#0ea5e9` Azul, `#e0ffff` Ciano) sobre fundos claros.
* **Elementos Sólidos:** Bordas pretas espessas (`2px solid #111`), sombras duras e tipografia forte (Poppins).
* **Responsividade:** Layout flexível com sidebar colapsável e adaptação para dispositivos móveis.

---

## 🚀 Funcionalidades Principais

### 🔐 Segurança Avançada
* **Autenticação JWT:** O sistema utiliza **JSON Web Tokens (JWT)** para gerenciar sessões de forma segura e stateless.
* **Hashing Robusto:** Senhas são armazenadas utilizando **PBKDF2-HMAC-SHA256** com 250.000 iterações e Salt único por usuário.
* **Autenticação de Dois Fatores (2FA):** Suporte completo para TOTP (Google Authenticator/Authy).
* **Proteção de Admin:** Registro de administradores protegido por chave secreta de ambiente (`ADMIN_KEY`).

### 📋 Gestão de Tarefas & Equipes
* **CRUD Completo:** Criação, edição, exclusão e conclusão de tarefas com prioridades e prazos.
* **Categorias (RBAC):** Sistema de permissões onde tarefas são organizadas em categorias; funcionários só acessam tarefas das categorias às quais foram vinculados.
* **Colaboração:** Comentários em tarefas e chat global em tempo real com notificações de não lidos.
* **Analytics:** Dashboard com métricas de produtividade e ranking de funcionários.

### 🛡️ Conformidade & LGPD (Privacidade)
* **Central DPO:** Interface dedicada para o Encarregado de Dados gerenciar solicitações de titulares.
* **Anonimização de Dados:** O sistema permite a exclusão de contas através de anonimização (substituindo dados pessoais por *placeholders* como `usuario_anonimizado_ID`), preservando a integridade histórica dos logs e tarefas sem manter PII (Informação Pessoal Identificável).
* **Logs de Auditoria:** Registro imutável de ações críticas (logins, exclusões, edições).

---

## 🛠️ Tecnologias Utilizadas

### Backend
* **Python 3.9+**
* **Flask:** API RESTful.
* **Flask-MySQLdb:** Conexão com banco de dados.
* **PyJWT:** Geração e validação de tokens JWT.
* **PyOTP:** Geração de códigos 2FA.
* **Hashlib:** Criptografia de senhas.

### Frontend
* **JavaScript (Vanilla ES6+):** Lógica SPA (Single Page Application) sem frameworks pesados.
* **Bootstrap 5:** Grid system e componentes base.
* **CSS3:** Estilização customizada (Neobrutalism).
* **Fetch API:** Comunicação assíncrona com o backend.

---

## ⚙️ Instalação e Configuração

### 1. Pré-requisitos
* Python 3.x
* MySQL Server (Rodando localmente ou remotamente)

### 2. Configuração do Banco de Dados
Crie um banco de dados chamado `task_flowup` e execute o seguinte script SQL para criar as tabelas necessárias (baseado na estrutura do `app.py`):

```sql
CREATE DATABASE IF NOT EXISTS task_flowup;
USE task_flowup;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(255) NOT NULL,
    role ENUM('admin', 'funcionario') NOT NULL,
    job_title VARCHAR(100),
    needs_password_reset TINYINT(1) DEFAULT 0,
    is_totp_enabled TINYINT(1) DEFAULT 0,
    totp_secret VARCHAR(255),
    chat_last_read_at DATETIME
);

CREATE TABLE task_categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE user_categories (
    user_id INT,
    category_id INT,
    PRIMARY KEY (user_id, category_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES task_categories(id) ON DELETE CASCADE
);

CREATE TABLE tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    priority INT DEFAULT 3, -- 1: Alta, 2: Média, 3: Baixa
    due_date DATE,
    completed TINYINT(1) DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    creator_id INT,
    assigned_to_id INT,
    category_id INT,
    FOREIGN KEY (category_id) REFERENCES task_categories(id) ON DELETE SET NULL
);

CREATE TABLE task_comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    user_id INT,
    text TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE task_read_timestamps (
    user_id INT,
    task_id INT,
    last_read_at DATETIME,
    PRIMARY KEY (user_id, task_id)
);

CREATE TABLE chat_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    text TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE activity_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action_text VARCHAR(255) NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dpo_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    request_type VARCHAR(50) NOT NULL,
    message_text TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    response_text TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    responded_at DATETIME,
    responded_by_id INT,
    scheduled_for DATETIME
);
3. Configuração do Backend
Clone o repositório.

Instale as dependências:

Bash

pip install Flask Flask-MySQLdb flask-cors pyotp pyjwt
Configure as variáveis de ambiente (Windows PowerShell):

PowerShell

$env:MYSQL_PASSWORD = "sua_senha_mysql"
$env:ADMIN_KEY = "admin-secret-key"       # Chave para criar conta Admin
$env:SECRET_KEY = "sua_jwt_secret_key"    # Chave para assinar tokens JWT
(No Linux/Mac use export VAR="valor")

Execute a aplicação:

Bash

python app.py
4. Execução do Frontend
Basta abrir o arquivo index.html em seu navegador.

Certifique-se de que o backend está rodando na porta 5001.

O arquivo script.js já aponta para http://127.0.0.1:5001/api.

📂 Estrutura de Arquivos
app.py: Servidor Flask, lógica de negócios, rotas da API e segurança.

index.html: Estrutura HTML única (SPA), contendo todos os Modais e Views.

script.js: Lógica do Frontend, gerenciamento de estado, chamadas fetch e manipulação do DOM.

style.css: Definições de estilo CSS global e tema Neobrutalista.

image.png: Logo da aplicação.

⚠️ Notas Importantes
Primeiro Acesso: Para criar o primeiro usuário Administrador, selecione "Administrador" no formulário de registro e insira a chave definida em ADMIN_KEY (Padrão: admin-secret-key).

JWT: O token tem validade de 24 horas. Se expirar, o frontend redirecionará automaticamente para o login.
