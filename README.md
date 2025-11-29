# Task FlowUp

![Logo do Task FlowUp](image-2.1.png)

O Task FlowUp é uma aplicação full-stack completa para gerenciamento de tarefas, projetada como uma plataforma interna (SaaS) para equipes. Ele fornece ferramentas robustas para gerenciamento de projetos, comunicação de equipe e monitoramento de produtividade, com um forte foco em segurança e conformidade com a LGPD.
A versão atual passou por uma reformulação na arquitetura de autenticação, abandonando sessões de servidor em favor de JWT (JSON Web Tokens), tornando a API totalmente stateless. A interface mantém o design Neobrutalista, agora com um fundo ciano vibrante (#e0ffff), bordas sólidas e sombras nítidas.
🚀 Principais Funcionalidades
A plataforma é dividida por níveis de permissão (Administrador e Funcionário) e utiliza uma arquitetura segura baseada em tokens.
1. Autenticação e Segurança (JWT & 2FA)
Autenticação Stateless (JWT): O login gera um JSON Web Token assinado com uma SECRET_KEY. O frontend armazena este token e o envia no cabeçalho Authorization: Bearer em cada requisição.
Hashing de Senha Robusto: Utiliza PBKDF2-HMAC-SHA256 com 250.000 iterações e um salt criptográfico exclusivo. O sistema migra automaticamente hashes legados (SHA256) no login.
Autenticação de Dois Fatores (2FA): Suporte completo a TOTP (Google Authenticator/Authy). O fluxo de login detecta se o 2FA está ativo e exige o token JWT temporário + código 2FA.
Chave de Administrador: O registro de contas de admin é protegido por uma chave secreta (ADMIN_REGISTRATION_KEY).
Validação de Frontend: Feedback visual imediato sobre a força da senha.
2. Gestão de Tarefas e Produtividade
Dashboard Interativo: Criação, edição e exclusão de tarefas com prioridades (Alta, Média, Baixa).
Filtros Avançados: Filtragem por status (Minhas, Atrasadas, Concluídas) e por Categoria.
Comentários e Rastreamento de Leitura: Sistema de comentários em tempo real. A aplicação rastreia o timestamp da última leitura de cada usuário, exibindo badges de notificação ("não lidos") nos cards das tarefas.
Painel "Vencendo em Breve": Alertas visuais para tarefas que vencem nos próximos 7 dias.
3. Organização por Categorias (RBAC Granular)
Gestão de Categorias: Admins podem criar pastas/categorias (ex: "Marketing", "TI").
Associação Usuário-Categoria: O sistema permite definir quais funcionários acessam quais categorias. Isso isola informações, garantindo que usuários vejam apenas tarefas pertinentes ao seu departamento (ou tarefas públicas sem categoria).
4. Painel de Administração (SSAP)
Gerenciamento Total de Usuários: Edição de dados, reset forçado de senha e exclusão lógica.
Impersonação de Usuário (Troca de Token): O admin pode gerar um token de impersonação para "logar como" um funcionário e visualizar a interface exatamente como ele.
Logs de Auditoria e Chat: Visualização e ferramentas de limpeza (purge) para o histórico de chat e logs de atividades do sistema.
5. Conformidade com LGPD (Central DPO)
Fluxo de Solicitação: Usuários podem abrir chamados para o DPO (Encarregado de Dados) diretamente pelo perfil.
Badge de Notificação DPO: O menu lateral alerta o admin sobre novas solicitações de privacidade pendentes.
Anonimização de Dados: Ao excluir um usuário (ou atender uma solicitação de exclusão), o sistema executa uma rotina de anonimização:
Substitui PII (Nome, Email) por strings genéricas (ex: usuario_anonimizado_ID).
Remove dados sensíveis (senhas, segredos 2FA).
Censura conteúdos de comentários e chat antigos.
Preserva a integridade referencial do banco de dados (ID e contagem de tarefas).
6. Comunicação
Chat da Equipe: Chat persistente integrado.
Polling Inteligente: O frontend verifica periodicamente novas mensagens e atualiza o contador de notificações no ícone do chat.
🛠️ Pilha de Tecnologia (Stack)
Backend (app.py)
Linguagem: Python 3.9+
Framework: Flask
Autenticação: PyJWT (JSON Web Tokens)
2FA: pyotp
Banco de Dados: MySQL (via Flask-MySQLdb)
CORS: Flask-CORS (Permite que o frontend rode separado do backend, se necessário)
Frontend (index.html, script.js, style.css)
Lógica: Vanilla JavaScript (ES6+) com fetch API customizado para injeção de Headers JWT.
Estilo: CSS3 Neobrutalista (var(--primary-color): #10b981, Background: #e0ffff).
Framework UI: Bootstrap 5.3.2.
Libs Auxiliares: qrcode.min.js (Geração de QR Code para 2FA).
🔧 Instalação e Execução
1. Pré-requisitos
Python 3.x
MySQL Server
Pip (Gerenciador de pacotes Python)
2. Configuração do Banco de Dados
Para configurar o banco de dados, utilize o arquivo schema.sql fornecido no repositório. Ele contém todos os comandos necessários para criar o banco task_flowup e as tabelas.
Opção A: Via Linha de Comando
mysql -u seu_usuario -p < schema.sql
Após digitar o comando, insira sua senha do MySQL quando solicitado.
Opção B: Via MySQL Workbench ou DBeaver
Abra sua ferramenta de banco de dados.
Abra o arquivo schema.sql.
Execute o script completo (ícone de raio ou F5).
3. Configuração do Backend
Crie um ambiente virtual e instale as dependências:
Configure as variáveis de ambiente (ou edite os valores padrão no topo do app.py para teste):
MYSQL_PASSWORD: Senha do banco de dados (Padrão no código: Foda12345).
ADMIN_KEY: Chave para registrar novos admins (Padrão: admin-secret-key).
SECRET_KEY: Chave para assinatura dos tokens JWT (Padrão: sua_chave_secreta_jwt...).
4. Execução
O servidor Flask rodará em http://127.0.0.1:5001.
Abra o arquivo index.html no seu navegador. Não é necessário um servidor web para o frontend, pois ele consome a API diretamente via CORS, mas usar algo como "Live Server" (VS Code) é recomendado.
⚠️ Notas de Produção
Chaves Secretas: Nunca use as chaves padrão em produção. Defina variáveis de ambiente seguras.
HTTPS: Como o sistema utiliza JWT e transfere senhas, o uso de HTTPS é obrigatório em ambientes reais para evitar ataques Man-in-the-Middle.
CORS: A configuração atual (CORS(app)) permite qualquer origem. Em produção, restrinja para o domínio onde o index.html estiver hospedado.
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
pip install Flask Flask-MySQLdb flask-cors pyotp pyjwt
