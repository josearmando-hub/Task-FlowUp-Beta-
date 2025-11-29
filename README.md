# Task FlowUp

![Logo do Task FlowUp](image-2.1.png)

Uma plataforma SaaS de gerenciamento de tarefas focada em segurança, produtividade e conformidade com a LGPD.

O Task FlowUp é uma aplicação Full-Stack robusta projetada para equipes que necessitam de controle granular sobre tarefas e comunicação. Diferente de to-do lists comuns, este projeto implementa uma arquitetura de segurança corporativa, utilizando JWT (JSON Web Tokens), autenticação de dois fatores (2FA) e um módulo dedicado à Lei Geral de Proteção de Dados.

A interface segue a tendência de design Neobrutalista, oferecendo alto contraste, acessibilidade e uma estética moderna.

🛡️ Destaques de Segurança & Arquitetura
O diferencial do Task FlowUp é a engenharia de segurança aplicada no backend:

Autenticação via JWT: O sistema é stateless. O login gera um token assinado (HS256) com validade de 24 horas, armazenado no cliente e enviado via header Authorization: Bearer.

Criptografia de Senha: Utiliza PBKDF2-HMAC-SHA256 com 250.000 iterações e Salts únicos por usuário.

2FA (TOTP): Suporte nativo a autenticação de dois fatores (compatível com Google Authenticator/Authy), gerando QR Codes no frontend.

LGPD & Privacy by Design:

Direito ao Esquecimento: Módulo DPO dedicado.

Anonimização: Dados de usuários excluídos são anonimizados (ex: usuario_anonimizado_ID) em vez de deletados, preservando a integridade referencial dos relatórios e logs.

RBAC (Role-Based Access Control): Controle de acesso granular onde administradores definem quais categorias de tarefas cada funcionário pode visualizar.

✨ Funcionalidades
👤 Para Todos os Usuários
Dashboard Interativo: Filtros por "Minhas Tarefas", "Atrasadas" e busca em tempo real.

Gestão de Tarefas: Criar, editar, comentar e concluir tarefas.

Chat em Tempo Real: Comunicação global com a equipe com notificações de mensagens não lidas.

Perfil Seguro: Alteração de senha, ativação de 2FA e solicitações ao DPO.

👮 Para Administradores (Admin Panel)
Gestão de Usuários (SSAP): CRUD completo de usuários e definição de cargos.

Gestão de Categorias: Criação de "pastas" de tarefas e atribuição de permissões de visualização para funcionários específicos.

Auditoria:

Impersonação (Ghost Login): O admin pode visualizar o sistema como se fosse um funcionário específico para debugging.

Log de Atividades: Registro imutável de ações críticas (logins, deleções, resets).

Central DPO: Painel para responder e executar solicitações de privacidade e exclusão de contas.

🛠️ Tech Stack
Backend
Linguagem: Python 3.9+

Framework: Flask

Auth: PyJWT (JSON Web Tokens)

Database: MySQL (via flask_mysqldb)

Security: hashlib (PBKDF2), pyotp (2FA), secrets

Frontend
Core: Vanilla JavaScript (ES6+)

Styling: CSS3 (Neobrutalism) + Bootstrap 5

Libraries: qrcode.js (Geração de QR Code no cliente)

🚀 Instalação e Configuração
1. Pré-requisitos
Python 3.x

MySQL Server

Git

2. Configuração do Banco de Dados
Crie um banco de dados chamado task_flowup.

Nota: Como o projeto utiliza SQL puro, você precisará criar as tabelas manualmente. Abaixo está o esquema sugerido baseado no código:

<details> <summary>📂 Clique para ver o SQL de Criação das Tabelas</summary>

SQL

CREATE DATABASE task_flowup;
USE task_flowup;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(255) NOT NULL,
    role ENUM('admin', 'funcionario') NOT NULL,
    job_title VARCHAR(100),
    needs_password_reset BOOLEAN DEFAULT 0,
    is_totp_enabled BOOLEAN DEFAULT 0,
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
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (category_id) REFERENCES task_categories(id)
);

CREATE TABLE tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    priority INT,
    due_date DATE,
    completed BOOLEAN DEFAULT 0,
    creator_id INT,
    assigned_to_id INT,
    category_id INT,
    created_at DATETIME,
    FOREIGN KEY (creator_id) REFERENCES users(id),
    FOREIGN KEY (assigned_to_id) REFERENCES users(id),
    FOREIGN KEY (category_id) REFERENCES task_categories(id)
);

CREATE TABLE task_comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT,
    user_id INT,
    text TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
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
    text TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE activity_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action_text TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dpo_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    request_type VARCHAR(50),
    message_text TEXT,
    status VARCHAR(50),
    response_text TEXT,
    responded_by_id INT,
    created_at DATETIME,
    responded_at DATETIME,
    scheduled_for DATETIME
);
</details>

3. Configuração do Backend
Clone o repositório e instale as dependências:

Bash

git clone https://github.com/seu-usuario/task-flowup.git
cd task-flowup
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install Flask Flask-MySQLdb flask-cors pyotp pyjwt
Configure as variáveis de ambiente (ou edite o app.py para desenvolvimento):

Linux/Mac:

Bash

export MYSQL_PASSWORD="sua_senha_root"
export SECRET_KEY="chave_super_secreta_para_jwt"
export ADMIN_KEY="chave_para_criar_primeiro_admin"
Windows (PowerShell):

PowerShell

$env:MYSQL_PASSWORD="sua_senha_root"
$env:SECRET_KEY="chave_super_secreta_para_jwt"
$env:ADMIN_KEY="chave_para_criar_primeiro_admin"
Execute o servidor:

Bash

python app.py
O servidor rodará em http://127.0.0.1:5001.

4. Execução do Frontend
Basta abrir o arquivo index.html no seu navegador. Não é necessário um servidor web separado para desenvolvimento, pois o script.js faz chamadas diretas (CORS habilitado) para a API local.

🎨 Design System
O projeto utiliza um design system customizado baseado em Neobrutalismo:

Fonte: Poppins (Google Fonts)

Cores Primárias:

Verde: #10b981 (Ação/Sucesso)

Azul: #0ea5e9 (Informação/Secundário)

Fundo: #e0ffff (Ciano Claro)

Estilo: Bordas pretas de 2px, sombras sólidas (hard shadows) e alto contraste.

📄 Licença
Este projeto é de código aberto e está disponível sob a licença MIT.
