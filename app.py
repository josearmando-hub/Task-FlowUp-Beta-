from flask import Flask, request, jsonify
from flask_mysqldb import MySQL
import hashlib
import os 
import secrets
from flask_cors import CORS
from datetime import date, datetime, timedelta 
import pyotp 
import jwt
from functools import wraps

app = Flask(__name__)
CORS(app)

# --- Configurações do banco de dados MySQL ---
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', 'Foda12345')
app.config['MYSQL_DB'] = 'task_flowup'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# --- CONFIGURAÇÃO NOVA: Chave Secreta para o JWT ---
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sua_chave_secreta_jwt_super_segura_123')

ADMIN_REGISTRATION_KEY = os.environ.get('ADMIN_KEY', 'admin-secret-key')

if app.config['MYSQL_PASSWORD'] == 'Foda12345' or ADMIN_REGISTRATION_KEY == 'admin-secret-key':
    print("="*50)
    print("AVISO DE SEGURANÇA: Você está usando senhas/chaves padrão.")
    print("Em produção, defina as variáveis de ambiente MYSQL_PASSWORD, ADMIN_KEY e SECRET_KEY.")
    print("="*50)

mysql = MySQL(app)

impersonation_tokens = {}


# --- ================================== ---
# --- Hashing de Senha (Mantido) ---
# --- ================================== ---
def create_salt():
    return os.urandom(16).hex()

def hash_password_legacy(password, salt):
    salted_password = password.encode('utf-8') + salt.encode('utf-8')
    return hashlib.sha256(salted_password).hexdigest()

def hash_password(password, salt_hex):
    salt_bytes = bytes.fromhex(salt_hex)
    password_bytes = password.encode('utf-8')
    
    dk = hashlib.pbkdf2_hmac(
        'sha256',
        password_bytes,
        salt_bytes,
        250000 
    )
    return dk.hex()
# --- Fim das Funções de Criptografia ---


# --- Funções Auxiliares ---
def log_activity(user_id, action_text):
    if not user_id:
        return
    try:
        cursor = mysql.connection.cursor()
        cursor.execute(
            "INSERT INTO activity_log (user_id, action_text) VALUES (%s, %s)",
            (user_id, action_text)
        )
        mysql.connection.commit()
        cursor.close()
    except Exception as e:
        print(f"Erro ao registrar atividade: {e}")

# Helper para verificar admin baseado no objeto do usuário atual (do token)
def is_admin_check(user):
    return user and user['role'] == 'admin'

# --- NOVO: Gerador de Token ---
def generate_jwt_token(user_id):
    expiration = datetime.utcnow() + timedelta(hours=24) # Token válido por 24 horas
    token = jwt.encode({
        'user_id': user_id,
        'exp': expiration
    }, app.config['SECRET_KEY'], algorithm="HS256")
    return token

# --- NOVO: Decorator JWT Blindado (Correção do erro 401) ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # O token deve vir no header Authorization: Bearer <token>
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith("Bearer "):
                try:
                    token = auth_header.split(" ")[1]
                except IndexError:
                    return jsonify({'error': 'Token malformado!'}), 401
        
        if not token:
            return jsonify({'error': 'Token ausente!'}), 401
        
        try:
            # Tenta decodificar
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            user_id = data['user_id']
            
            # Verifica se o usuário ainda existe no banco e pega dados atualizados
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT id, username, email, role, job_title, totp_secret, chat_last_read_at FROM users WHERE id = %s", (user_id,))
            current_user = cursor.fetchone()
            cursor.close()

            if not current_user:
                return jsonify({'error': 'Usuário inválido ou não encontrado!'}), 401
                
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expirado!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token inválido!'}), 401
        except Exception as e:
            print(f"Erro de Token Genérico: {e}") 
            return jsonify({'error': 'Token inválido.'}), 401

        # Injeta o usuário atual na função da rota
        return f(current_user, *args, **kwargs)
    
    return decorated


# --- Rotas de Autenticação ---
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username, password, role, email = data.get('username'), data.get('password'), data.get('role'), data.get('email')
    job_title = data.get('job_title') or 'Funcionário' 
    admin_key_received = data.get('adminKey')
    consent = data.get('consent') 
    
    if role == 'admin' and admin_key_received != ADMIN_REGISTRATION_KEY:
        return jsonify({'error': 'Chave de administrador incorreta.'}), 403
    
    if not consent:
        return jsonify({'error': 'Você deve aceitar os termos de privacidade para se registrar.'}), 400
        
    if not all([username, password, role]):
        return jsonify({'error': 'Dados obrigatórios ausentes.'}), 400
    
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'Este nome de usuário já existe.'}), 409
    
    if email:
        cursor.execute("SELECT email FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            return jsonify({'error': 'Este e-mail já está em uso.'}), 409
            
    salt = create_salt()
    password_hash = hash_password(password, salt)
    needs_password_reset = (role == 'funcionario')
    
    cursor.execute(
        "INSERT INTO users (username, password_hash, salt, role, email, needs_password_reset, job_title) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (username, password_hash, salt, role, email, needs_password_reset, job_title)
    )
    mysql.connection.commit()
    
    new_user_id = cursor.lastrowid
    log_activity(new_user_id, f"se registrou no sistema como {role}.")
    
    cursor.close()
    return jsonify({'message': 'Usuário registrado com sucesso.'}), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username, password = data.get('username'), data.get('password')
    cursor = mysql.connection.cursor()
    
    cursor.execute(
        "SELECT id, username, password_hash, salt, role, email, needs_password_reset, job_title, is_totp_enabled "
        "FROM users WHERE username = %s", 
        (username,)
    )
    user_row = cursor.fetchone()
    cursor.close()

    if not user_row:
        return jsonify({'error': 'Usuário não encontrado.'}), 404

    new_hash_attempt = hash_password(password, user_row['salt'])
    
    if new_hash_attempt == user_row['password_hash']:
        pass
    
    elif hash_password_legacy(password, user_row['salt']) == user_row['password_hash']:
        print(f"ATENÇÃO: Migrando hash de senha para o usuário ID: {user_row['id']}")
        try:
            upgrade_cursor = mysql.connection.cursor()
            upgrade_cursor.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (new_hash_attempt, user_row['id'])
            )
            mysql.connection.commit()
            upgrade_cursor.close()
        except Exception as e:
            print(f"ERRO: Falha ao migrar hash da senha para o usuário ID {user_row['id']}: {e}")
            mysql.connection.rollback()
    
    else:
        return jsonify({'error': 'Senha incorreta.'}), 401
    
    if user_row['is_totp_enabled']:
        return jsonify({'2fa_required': True}), 200

    # ALTERAÇÃO JWT: Gera o token
    token = generate_jwt_token(user_row['id'])

    user_data = {
        'id': user_row['id'],
        'username': user_row['username'],
        'email': user_row['email'],
        'role': user_row['role'],
        'jobTitle': user_row['job_title'],
        'needsPasswordReset': bool(user_row['needs_password_reset'])
    }
    
    log_activity(user_data['id'], f"fez login.")

    # ALTERAÇÃO JWT: Retorna o token no JSON
    return jsonify({'message': 'Login bem-sucedido.', 'user': user_data, 'token': token}), 200

    #login 2AF corrigido
@app.route('/api/login/2fa', methods=['POST'])
def login_2fa():
    data = request.json
    username = data.get('username')
    totp_code = data.get('totp_code')

    if not username or not totp_code:
        return jsonify({'error': 'Nome de usuário e código 2FA são obrigatórios.'}), 400

    cursor = mysql.connection.cursor()
    cursor.execute(
        "SELECT id, username, role, email, needs_password_reset, job_title, totp_secret "
        "FROM users WHERE username = %s", (username,)
    )
    user_row = cursor.fetchone()

    if not user_row:
        cursor.close()
        return jsonify({'error': 'Usuário não encontrado.'}), 404
    
    if not user_row['totp_secret']:
        cursor.close()
        return jsonify({'error': '2FA não está configurado para este usuário.'}), 400

    totp = pyotp.TOTP(user_row['totp_secret'])
    if not totp.verify(totp_code):
        cursor.close()
        return jsonify({'error': 'Código 2FA inválido.'}), 401

    cursor.close()

    # ALTERAÇÃO JWT: Gera o token
    token = generate_jwt_token(user_row['id'])

    user_data = {
        'id': user_row['id'],
        'username': user_row['username'],
        'email': user_row['email'],
        'role': user_row['role'],
        'jobTitle': user_row['job_title'],
        'needsPasswordReset': bool(user_row['needs_password_reset'])
    }
    
    log_activity(user_data['id'], f"fez login com 2FA.")
    # ALTERAÇÃO JWT: Retorna o token
    return jsonify({'message': 'Login 2FA bem-sucedido.', 'user': user_data, 'token': token}), 200


@app.route('/api/forgot-password', methods=['POST'])
def forgot_password():
    email = request.json.get('email')
    if not email:
        return jsonify({'error': 'O e-mail é obrigatório.'}), 400

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, salt FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if user:
        temp_password = secrets.token_hex(8)
        password_hash = hash_password(temp_password, user['salt'])
        cursor.execute(
            "UPDATE users SET password_hash = %s, needs_password_reset = 1 WHERE id = %s",
            (password_hash, user['id'])
        )
        mysql.connection.commit()
        log_activity(user['id'], "solicitou uma redefinição de senha.")
        
    cursor.close()
    return jsonify({
        'message': 'Se existir uma conta com este e-mail, as instruções de redefinição foram processadas.'
    })


@app.route('/api/user/reset-password', methods=['POST'])
@token_required # ALTERAÇÃO JWT
def reset_password(current_user):
    data = request.json
    # ALTERAÇÃO JWT: Usa current_user['id'] em vez do body
    user_id = current_user['id'] 
    new_password = data.get('newPassword')

    if not new_password:
        return jsonify({'error': 'Dados incompletos.'}), 400
        
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT salt FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        return jsonify({'error': 'Usuário não encontrado.'}), 404

    password_hash = hash_password(new_password, user['salt'])
    cursor.execute(
        "UPDATE users SET password_hash = %s, needs_password_reset = 0 WHERE id = %s",
        (password_hash, user_id)
    )
    mysql.connection.commit()
    cursor.close()
    
    log_activity(user_id, "redefiniu sua senha após login forçado.")
    
    return jsonify({'message': 'Senha atualizada com sucesso.'})


@app.route('/api/user/change-password', methods=['POST'])
@token_required # ALTERAÇÃO JWT
def change_password(current_user):
    data = request.json
    # ALTERAÇÃO JWT: Usa current_user['id']
    user_id = current_user['id']
    old_password, new_password = data.get('oldPassword'), data.get('newPassword')

    if not all([old_password, new_password]):
        return jsonify({'error': 'Dados incompletos.'}), 400
        
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT password_hash, salt FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        return jsonify({'error': 'Usuário não encontrado.'}), 404
        
    is_new_hash_match = hash_password(old_password, user['salt']) == user['password_hash']
    is_legacy_hash_match = hash_password_legacy(old_password, user['salt']) == user['password_hash']
    
    if not is_new_hash_match and not is_legacy_hash_match:
        cursor.close()
        return jsonify({'error': 'Senha antiga incorreta.'}), 401
    
    new_password_hash = hash_password(new_password, user['salt'])
    cursor.execute(
        "UPDATE users SET password_hash = %s, needs_password_reset = 0 WHERE id = %s",
        (new_password_hash, user_id)
    )
    mysql.connection.commit()
    cursor.close()
    
    log_activity(user_id, "alterou sua senha através do perfil.")
    
    return jsonify({'message': 'Senha atualizada com sucesso.'})


# --- ================================================ ---
# --- Rota de Auto-Exclusão (Solicitação)
# --- ================================================ ---
@app.route('/api/user/delete-self', methods=['POST'])
@token_required # ALTERAÇÃO JWT
def delete_self_account(current_user):
    # ALTERAÇÃO JWT: Usa current_user['id']
    user_id = current_user['id']
    
    cursor = mysql.connection.cursor()
    try:
        # Verifica se já existe uma solicitação pendente
        cursor.execute(
            "SELECT id FROM dpo_requests WHERE user_id = %s AND request_type = 'anonymization_request' AND status = 'pending'",
            (user_id,)
        )
        if cursor.fetchone():
            cursor.close()
            return jsonify({'message': 'Você já possui uma solicitação de exclusão pendente.'}), 200

        # Define a data de agendamento (7 dias a partir de agora)
        scheduled_date = datetime.now() + timedelta(days=7)
        message_text = "Solicitação de exclusão de conta iniciada pelo usuário. Agendada para execução em 7 dias."
        request_type = "anonymization_request" # Tipo interno mantido
        
        # Insere a solicitação de DPO
        cursor.execute(
            """INSERT INTO dpo_requests (user_id, request_type, message_text, status, created_at, scheduled_for) 
               VALUES (%s, %s, %s, 'pending', NOW(), %s)""",
            (user_id, request_type, message_text, scheduled_date)
        )
        mysql.connection.commit()
        
        log_activity(user_id, f"solicitou a exclusão da própria conta, agendada para {scheduled_date.strftime('%Y-%m-%d')}.")
        
        cursor.close()
        return jsonify({'message': 'Solicitação de exclusão recebida. Sua conta será excluída em 7 dias. Você pode cancelar esta solicitação entrando em contato com o DPO.'}), 200
        
    except Exception as e:
        mysql.connection.rollback()
        cursor.close()
        print(f"Erro ao solicitar exclusão: {e}") 
        return jsonify({'error': f'Erro ao processar solicitação: {str(e)}'}), 500


# --- Rotas de Usuário ---
@app.route('/api/user/<int:user_id>', methods=['GET'])
@token_required # ALTERAÇÃO JWT
def get_user_details(current_user, user_id):
    # Segurança: Apenas o próprio usuário ou Admin pode ver os detalhes
    if current_user['id'] != user_id and not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403

    cursor = mysql.connection.cursor()
    
    cursor.execute(
        "SELECT id, username, email, role, job_title, is_totp_enabled "
        "FROM users WHERE id = %s", 
        (user_id,)
    )
    user = cursor.fetchone()
    cursor.close()
    
    if not user:
        return jsonify({'error': 'Usuário não encontrado.'}), 404
    
    user['is_totp_enabled'] = bool(user['is_totp_enabled'])
    
    return jsonify(user)


@app.route('/api/user/<int:user_id>', methods=['PUT'])
@token_required # ALTERAÇÃO JWT
def update_user_profile(current_user, user_id):
    data = request.json
    # ALTERAÇÃO JWT: ID de quem está agindo vem do token
    acting_user_id = current_user['id']
    
    if acting_user_id != user_id and not is_admin_check(current_user):
        return jsonify({'error': 'Permissão negada.'}), 403

    new_username = data.get('username')
    new_email = data.get('email')
    new_job_title = data.get('job_title') 
    
    if not new_username or not new_email:
        return jsonify({'error': 'Nome de usuário e e-mail são obrigatórios.'}), 400

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s", (new_username, user_id))
    if cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'Este nome de usuário já está em uso.'}), 409
    
    cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (new_email, user_id))
    if cursor.fetchone():
        cursor.close()
        return jsonify({'error': 'Este e-mail já está em uso.'}), 409

    if is_admin_check(current_user) and 'role' in data:
        new_role = data.get('role')
        if new_role not in ['admin', 'funcionario']:
            return jsonify({'error': 'Role inválido.'}), 400
        cursor.execute(
            "UPDATE users SET username = %s, email = %s, job_title = %s, role = %s WHERE id = %s", 
            (new_username, new_email, new_job_title, new_role, user_id)
        )
    else:
        cursor.execute(
            "UPDATE users SET username = %s, email = %s, job_title = %s WHERE id = %s", 
            (new_username, new_email, new_job_title, user_id)
        )
    
    mysql.connection.commit()
    
    cursor.execute("SELECT id, username, email, role, job_title FROM users WHERE id = %s", (user_id,))
    updated_user = cursor.fetchone()
    cursor.close()
    
    if acting_user_id == user_id:
        log_activity(acting_user_id, f"atualizou seu próprio perfil.")
    else:
        log_activity(acting_user_id, f"atualizou o perfil do usuário {updated_user['username']} (ID: {user_id}).")
    
    return jsonify({'message': 'Perfil atualizado com sucesso.', 'user': updated_user})


@app.route('/api/users/employees', methods=['GET'])
@token_required # ALTERAÇÃO JWT
def get_employees(current_user):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, username, email, job_title FROM users WHERE role = 'funcionario' ORDER BY username ASC")
    employees = cursor.fetchall()
    cursor.close()
    return jsonify(employees)


# --- ROTA DE ANÁLISE ---
@app.route('/api/analytics', methods=['GET'])
@token_required # ALTERAÇÃO JWT
def get_analytics(current_user):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM tasks")
    total_tasks = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE completed = 1")
    completed_tasks = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE completed = 0")
    pending_tasks = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE completed = 0 AND due_date < CURDATE()")
    overdue_tasks = cursor.fetchone()['total']
    query = """
        SELECT u.username, COUNT(t.id) as task_count
        FROM tasks t
        JOIN users u ON t.assigned_to_id = u.id
        WHERE u.role = 'funcionario'
        GROUP BY u.username
        ORDER BY task_count DESC
        LIMIT 1
    """
    cursor.execute(query)
    top_user = cursor.fetchone()
    cursor.close()
    analytics_data = {
        "totalTasks": total_tasks,
        "completedTasks": completed_tasks,
        "pendingTasks": pending_tasks,
        "overdueTasks": overdue_tasks,
        "topUser": top_user if top_user else {"username": "N/A", "task_count": 0}
    }
    return jsonify(analytics_data)


# --- ROTAS DE TAREFAS ---

@app.route('/api/tasks', methods=['GET', 'POST'])
@token_required # ALTERAÇÃO JWT
def tasks(current_user):
    cursor = mysql.connection.cursor()
    
    if request.method == 'GET':
        # ALTERAÇÃO JWT: Usa o ID do token por padrão, mas permite consultar outro se for admin
        user_id = current_user['id']
        requested_user_id = request.args.get('user_id')
        
        # Mantém a lógica: Se for admin e pediu um ID específico, usa ele.
        # Se requested_user_id for '0', significa "todas as tarefas" (lógica do seu front)
        if is_admin_check(current_user) and requested_user_id and requested_user_id != '0':
             try:
                user_id = int(requested_user_id)
             except:
                pass
        elif requested_user_id == '0':
             user_id = 0 
        
        # Recupera role do usuário alvo (se mudou)
        user_role = current_user['role']
        if user_id != current_user['id'] and user_id != 0:
             cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
             u = cursor.fetchone()
             if u: user_role = u['role']
        
        query = """
            SELECT 
                t.*, 
                u_creator.username AS creator_name, 
                u_assignee.username AS assignee_name, 
                tc.name AS category_name,
                COUNT(tc_comments.id) AS comment_count,
                (
                    SELECT COUNT(tc_unread.id)
                    FROM task_comments tc_unread
                    LEFT JOIN task_read_timestamps trt ON trt.task_id = tc_unread.task_id AND trt.user_id = %s
                    WHERE tc_unread.task_id = t.id
                    AND (trt.last_read_at IS NULL OR tc_unread.timestamp > trt.last_read_at)
                ) AS unread_comment_count
            FROM tasks t
            LEFT JOIN users u_creator ON t.creator_id = u_creator.id
            LEFT JOIN users u_assignee ON t.assigned_to_id = u_assignee.id
            LEFT JOIN task_categories tc ON t.category_id = tc.id
            LEFT JOIN task_comments tc_comments ON t.id = tc_comments.task_id
        """
        
        params = [current_user['id']] # Unread sempre relativo a quem está vendo (token owner)

        if user_role == 'funcionario' and user_id != 0:
            query += """
                LEFT JOIN user_categories uc ON t.category_id = uc.category_id
                WHERE (uc.user_id = %s OR t.category_id IS NULL)
            """
            params.append(user_id) 

        query += """
            GROUP BY t.id, tc.name
            ORDER BY t.completed ASC, t.priority ASC, t.due_date ASC
        """
        
        cursor.execute(query, tuple(params)) 
        
        tasks_list = cursor.fetchall()
        cursor.close()
        for task in tasks_list:
            for key, value in task.items():
                if isinstance(value, (datetime, date)): task[key] = value.isoformat()
        return jsonify(tasks_list)
    
    if request.method == 'POST':
        data = request.json
        # ALTERAÇÃO JWT: O criador é o usuário do token
        creator_id = current_user['id']
        assigned_to_id = data.get('assigned_to_id') or None
        due_date = data.get('due_date') or None
        created_at_time = datetime.now()
        
        category_id = data.get('category_id') or None
        
        cursor.execute(
            "INSERT INTO tasks (title, description, priority, due_date, creator_id, assigned_to_id, created_at, category_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", 
            (data.get('title'), data.get('description'), data.get('priority'), due_date, creator_id, assigned_to_id, created_at_time, category_id)
        )
        mysql.connection.commit()
        cursor.close()
        log_activity(creator_id, f"criou a tarefa: '{data.get('title')}'")
        return jsonify({'message': 'Tarefa criada com sucesso.'}), 201


@app.route('/api/tasks/<int:task_id>', methods=['GET', 'PUT', 'DELETE'])
@token_required # ALTERAÇÃO JWT
def manage_task(current_user, task_id):
    cursor = mysql.connection.cursor()
    if request.method == 'GET':
        cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
        task = cursor.fetchone()
        cursor.close()
        if task:
            for key, value in task.items():
                if isinstance(value, (datetime, date)): task[key] = value.isoformat()
            return jsonify(task)
        return jsonify({'error': 'Tarefa não encontrada.'}), 404

    try:
        cursor.execute("SELECT title FROM tasks WHERE id = %s", (task_id,))
        task = cursor.fetchone()
        current_title = task['title'] if task else "Tarefa Desconhecida"
    except Exception as e:
        print(f"Erro ao buscar título da tarefa {task_id}: {e}")
        current_title = "Tarefa Desconhecida"


    if request.method == 'PUT':
        data = request.json
        # ALTERAÇÃO JWT: O ator é o usuário do token
        acting_user_id = current_user['id']
        
        if 'completed' not in data and not is_admin_check(current_user):
            cursor.close()
            return jsonify({'error': 'Permissão negada. Apenas administradores podem editar tarefas.'}), 403
        
        if 'completed' in data:
            cursor.execute("UPDATE tasks SET completed = %s WHERE id = %s", (data['completed'], task_id))
            action_text = "concluiu" if data['completed'] else "reabriu"
            log_activity(acting_user_id, f"{action_text} a tarefa: '{current_title}'")
        else:
            assigned_to_id = data.get('assigned_to_id') or None
            due_date = data.get('due_date') or None
            new_title = data.get('title')
            
            category_id = data.get('category_id') or None
            
            cursor.execute(
                "UPDATE tasks SET title = %s, description = %s, priority = %s, due_date = %s, assigned_to_id = %s, category_id = %s WHERE id = %s",
                (new_title, data.get('description'), data.get('priority'), due_date, assigned_to_id, category_id, task_id)
            )
            log_activity(acting_user_id, f"editou a tarefa '{current_title}' (novo título: '{new_title}')")
            
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': f'Tarefa {task_id} atualizada.'})

    if request.method == 'DELETE':
        # ALTERAÇÃO JWT: O ator é o usuário do token
        acting_user_id = current_user['id']

        if not is_admin_check(current_user):
            cursor.close()
            return jsonify({'error': 'Permissão negada. Apenas administradores podem excluir tarefas.'}), 403
        
        try:
            cursor.execute("DELETE FROM task_read_timestamps WHERE task_id = %s", (task_id,))
        except Exception as e:
            print(f"Aviso: falha ao limpar 'task_read_timestamps' para tarefa {task_id}: {e}")

        cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
        mysql.connection.commit()
        cursor.close()
        
        log_activity(acting_user_id, f"excluiu a tarefa: '{current_title}'")
        return jsonify({'message': f'Tarefa {task_id} deletada.'})


@app.route('/api/tasks/<int:task_id>/mark-as-read', methods=['POST'])
@token_required # ALTERAÇÃO JWT
def mark_task_as_read(current_user, task_id):
    # ALTERAÇÃO JWT: Usa ID do token
    user_id = current_user['id']
    
    cursor = mysql.connection.cursor()
    now = datetime.now()
    
    try:
        cursor.execute(
            """
            INSERT INTO task_read_timestamps (user_id, task_id, last_read_at)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE last_read_at = %s
            """,
            (user_id, task_id, now, now)
        )
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Tarefa marcada como lida.'}), 200
    except Exception as e:
        mysql.connection.rollback()
        cursor.close()
        print(f"Erro ao marcar tarefa como lida: {e}")
        return jsonify({'error': 'Erro ao marcar tarefa como lida.'}), 500


# --- Rotas de Comentários ---
@app.route('/api/tasks/<int:task_id>/comments', methods=['GET', 'POST'])
@token_required # ALTERAÇÃO JWT
def comments(current_user, task_id):
    cursor = mysql.connection.cursor()
    if request.method == 'GET':
        cursor.execute("SELECT tc.*, u.username FROM task_comments tc JOIN users u ON tc.user_id = u.id WHERE tc.task_id = %s ORDER BY tc.timestamp ASC", (task_id,))
        comments_list = cursor.fetchall()
        cursor.close()
        for comment in comments_list:
            if isinstance(comment.get('timestamp'), datetime): comment['timestamp'] = comment['timestamp'].isoformat()
        return jsonify(comments_list)
    
    if request.method == 'POST':
        data = request.json
        # ALTERAÇÃO JWT: Usa ID do token
        user_id = current_user['id']
        text = data.get('text')
        cursor.execute("INSERT INTO task_comments (task_id, user_id, text) VALUES (%s, %s, %s)", (task_id, user_id, text))
        mysql.connection.commit()
        cursor.close()
        log_activity(user_id, f"comentou na tarefa ID {task_id}: '{text[:30]}...'")
        return jsonify({'message': 'Comentário adicionado.'}), 201


# --- Rotas de Chat ---
@app.route('/api/chat/messages', methods=['GET', 'POST'])
@token_required # ALTERAÇÃO JWT
def chat_messages(current_user):
    cursor = mysql.connection.cursor()
    if request.method == 'GET':
        cursor.execute("SELECT cm.*, u.username, u.role FROM chat_messages cm JOIN users u ON cm.user_id = u.id ORDER BY cm.timestamp ASC")
        messages = cursor.fetchall()
        cursor.close()
        for msg in messages:
            if isinstance(msg.get('timestamp'), datetime): msg['timestamp'] = msg['timestamp'].isoformat()
        return jsonify(messages)
    
    if request.method == 'POST':
        data = request.json
        # ALTERAÇÃO JWT: Usa ID do token
        user_id = current_user['id']
        cursor.execute("INSERT INTO chat_messages (user_id, text) VALUES (%s, %s)", (user_id, data.get('text')))
        mysql.connection.commit()
        
        try:
            cursor.execute("UPDATE users SET chat_last_read_at = NOW() WHERE id = %s", (user_id,))
            mysql.connection.commit()
        except Exception as e:
            print(f"Erro ao atualizar chat_last_read_at ao enviar mensagem: {e}")
            mysql.connection.rollback()
            
        cursor.close()
        return jsonify({'message': 'Mensagem enviada.'}), 201


@app.route('/api/chat/unread-count', methods=['GET'])
@token_required # ALTERAÇÃO JWT
def get_chat_unread_count(current_user):
    # ALTERAÇÃO JWT: Usa ID do token
    user_id = current_user['id']

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT chat_last_read_at FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        last_read = user['chat_last_read_at'] if (user and user['chat_last_read_at']) else datetime.now()

        cursor.execute(
            """SELECT COUNT(id) as unreadCount 
               FROM chat_messages 
               WHERE timestamp > %s""",
            (last_read,)
        )
        result = cursor.fetchone()
        cursor.close()
        
        return jsonify(result), 200
        
    except Exception as e:
        cursor.close()
        print(f"Erro ao buscar contagem de não lidos: {e}")
        return jsonify({'error': 'Erro ao buscar contagem de não lidos.'}), 500


@app.route('/api/chat/mark-as-read', methods=['POST'])
@token_required # ALTERAÇÃO JWT
def mark_chat_as_read(current_user):
    # ALTERAÇÃO JWT: Usa ID do token
    user_id = current_user['id']

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("UPDATE users SET chat_last_read_at = NOW() WHERE id = %s", (user_id,))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': 'Chat marcado como lido.'}), 200
    except Exception as e:
        mysql.connection.rollback()
        cursor.close()
        print(f"Erro ao marcar chat como lido: {e}")
        return jsonify({'error': 'Erro ao marcar chat como lido.'}), 500


@app.route('/api/admin/chat/purge', methods=['DELETE'])
@token_required # ALTERAÇÃO JWT
def admin_purge_chat(current_user):
    # ALTERAÇÃO JWT: Usa ID do token
    admin_id = current_user['id']
    
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403
        
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("TRUNCATE TABLE chat_messages")
        mysql.connection.commit()
        cursor.close()
        
        log_activity(admin_id, "executou a limpeza (PURGE) de todas as mensagens do chat.")
        return jsonify({'message': 'Histórico de chat limpo com sucesso.'}), 200
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Erro ao limpar o chat: {e}")
        return jsonify({'error': 'Erro ao limpar o chat.'}), 500


@app.route('/api/admin/activity-log/purge', methods=['DELETE'])
@token_required # ALTERAÇÃO JWT
def admin_purge_activity_log(current_user):
    # ALTERAÇÃO JWT: Usa ID do token
    admin_id = current_user['id']
    
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403
        
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("TRUNCATE TABLE activity_log")
        mysql.connection.commit()
        cursor.close()
        
        log_activity(admin_id, "executou a limpeza (PURGE) de todo o Log de Atividades.")
        return jsonify({'message': 'Log de Atividades limpo com sucesso.'}), 200
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Erro ao limpar o Log de Atividades: {e}")
        return jsonify({'error': 'Erro ao limpar o Log de Atividades.'}), 500


# --- ROTA DE LOG DE ATIVIDADES ---
@app.route('/api/activity-log', methods=['GET'])
@token_required # ALTERAÇÃO JWT
def get_activity_log(current_user):
    cursor = mysql.connection.cursor()
    query = """
        SELECT a.id, a.action_text, a.timestamp, u.username
        FROM activity_log a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.timestamp DESC
        LIMIT 50
    """
    cursor.execute(query)
    logs = cursor.fetchall()
    cursor.close()
    
    for log_entry in logs:
        if isinstance(log_entry.get('timestamp'), datetime):
            log_entry['timestamp'] = log_entry['timestamp'].isoformat()
        if not log_entry['username']:
            log_entry['username'] = "[Usuário Deletado]"
            
    return jsonify(logs)


@app.route('/api/user/my-activity-log', methods=['GET'])
@token_required # ALTERAÇÃO JWT
def get_user_activity_log(current_user):
    # ALTERAÇÃO JWT: Usa ID do token
    user_id = current_user['id']
        
    cursor = mysql.connection.cursor()
    try:
        query = """
            SELECT id, action_text, timestamp
            FROM activity_log
            WHERE user_id = %s
            AND action_text LIKE 'concluiu a tarefa%%'
            ORDER BY timestamp DESC
            LIMIT 100
        """
        cursor.execute(query, (user_id,))
        logs = cursor.fetchall()
        cursor.close()
        
        for log_entry in logs:
            if isinstance(log_entry.get('timestamp'), datetime):
                log_entry['timestamp'] = log_entry['timestamp'].isoformat()
                
        return jsonify(logs), 200
        
    except Exception as e:
        cursor.close()
        print(f"Erro ao buscar log de atividades do usuário: {e}")
        return jsonify({'error': 'Erro ao buscar seu log de atividades.'}), 500


# --- ROTAS SSAP (Admin User Management) ---
@app.route('/api/admin/users', methods=['GET'])
@token_required # ALTERAÇÃO JWT
def admin_get_all_users(current_user):
    # ALTERAÇÃO JWT: Usa current_user para checar admin
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado. Requer privilégios de administrador.'}), 403
        
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, username, email, role, job_title, needs_password_reset FROM users ORDER BY username ASC")
    users = cursor.fetchall()
    cursor.close()
    return jsonify(users)

@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
@token_required # ALTERAÇÃO JWT
def admin_delete_user(current_user, user_id):
    # ALTERAÇÃO JWT: Usa ID do token
    admin_id = current_user['id']
    
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403
    if admin_id == user_id:
        return jsonify({'error': 'Você não pode deletar a si mesmo.'}), 400

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            return jsonify({'error': 'Usuário não encontrado.'}), 404
        
        cursor.execute("DELETE FROM user_categories WHERE user_id = %s", (user_id,))
        
        cursor.execute("DELETE FROM task_read_timestamps WHERE user_id = %s", (user_id,))
        cursor.execute("UPDATE tasks SET creator_id = NULL WHERE creator_id = %s", (user_id,))
        cursor.execute("UPDATE tasks SET assigned_to_id = NULL WHERE assigned_to_id = %s", (user_id,))
        cursor.execute("DELETE FROM task_comments WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM chat_messages WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM activity_log WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        
        mysql.connection.commit()
        cursor.close()
        
        log_activity(admin_id, f"deletou o usuário {user['username']} (ID: {user_id}).")
        return jsonify({'message': 'Usuário deletado com sucesso.'})
        
    except Exception as e:
        mysql.connection.rollback()
        cursor.close()
        print(f"Erro ao deletar usuário: {e}")
        return jsonify({'error': f'Erro de banco de dados: {str(e)}'}), 500


@app.route('/api/admin/force-reset-password', methods=['POST'])
@token_required # ALTERAÇÃO JWT
def admin_force_reset_password(current_user):
    data = request.json
    # ALTERAÇÃO JWT: Usa ID do token
    admin_id = current_user['id']
    target_user_id = data.get('target_user_id')
    
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT salt, username FROM users WHERE id = %s", (target_user_id,))
    user = cursor.fetchone()
    if not user:
        return jsonify({'error': 'Usuário não encontrado.'}), 404
        
    temp_password = secrets.token_hex(8)
    password_hash = hash_password(temp_password, user['salt'])
    
    cursor.execute(
        "UPDATE users SET password_hash = %s, needs_password_reset = 1 WHERE id = %s",
        (password_hash, target_user_id)
    )
    mysql.connection.commit()
    cursor.close()
    
    log_activity(admin_id, f"forçou a redefinição de senha para o usuário {user['username']} (ID: {target_user_id}).")
    
    return jsonify({
        'message': f"Redefinição de senha forçada para {user['username']}. O usuário deverá criar uma nova senha no próximo login."
    })


# --- ROTAS DE CATEGORIAS ---

@app.route('/api/categories', methods=['GET'])
@token_required # ALTERAÇÃO JWT
def get_categories(current_user):
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT 
                tc.id, tc.name, tc.description, 
                (SELECT COUNT(t.id) FROM tasks t WHERE t.category_id = tc.id) as task_count,
                (SELECT COUNT(uc.user_id) FROM user_categories uc WHERE uc.category_id = tc.id) as user_count
            FROM task_categories tc 
            ORDER BY tc.name ASC
        """)
        categories = cursor.fetchall()
        cursor.close()
        return jsonify(categories)
    except Exception as e:
        print(f"Erro ao buscar categorias: {e}")
        return jsonify({'error': 'Erro ao buscar categorias.'}), 500

@app.route('/api/admin/categories', methods=['POST'])
@token_required # ALTERAÇÃO JWT
def create_category(current_user):
    data = request.json
    # ALTERAÇÃO JWT: Usa ID do token
    admin_id = current_user['id']
    name = data.get('name')
    
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403
    if not name:
        return jsonify({'error': 'O nome da categoria é obrigatório.'}), 400
        
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO task_categories (name, description) VALUES (%s, %s)", 
                       (name, data.get('description')))
        mysql.connection.commit()
        
        new_category_id = cursor.lastrowid
        cursor.close()
        
        log_activity(admin_id, f"criou a categoria: '{name}' (ID: {new_category_id})")
        return jsonify({'message': 'Categoria criada com sucesso.', 'id': new_category_id}), 201
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': f'Erro ao criar categoria: {str(e)}'}), 500

@app.route('/api/admin/categories/<int:category_id>', methods=['PUT'])
@token_required # ALTERAÇÃO JWT
def update_category(current_user, category_id):
    data = request.json
    # ALTERAÇÃO JWT: Usa ID do token
    admin_id = current_user['id']
    name = data.get('name')
    
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403
    if not name:
        return jsonify({'error': 'O nome é obrigatório.'}), 400

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE task_categories SET name = %s, description = %s WHERE id = %s", 
                       (name, data.get('description'), category_id))
        mysql.connection.commit()
        cursor.close()
        log_activity(admin_id, f"atualizou a categoria ID {category_id} (Novo nome: {name})")
        return jsonify({'message': 'Categoria atualizada com sucesso.'})
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': f'Erro ao atualizar categoria: {str(e)}'}), 500

@app.route('/api/admin/categories/<int:category_id>', methods=['DELETE'])
@token_required # ALTERAÇÃO JWT
def delete_category(current_user, category_id):
    # ALTERAÇÃO JWT: Usa ID do token
    admin_id = current_user['id']
    
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403

    try:
        cursor = mysql.connection.cursor()
        
        cursor.execute("DELETE FROM user_categories WHERE category_id = %s", (category_id,))
        cursor.execute("DELETE FROM task_categories WHERE id = %s", (category_id,))
        mysql.connection.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            return jsonify({'error': 'Categoria não encontrada.'}), 404
            
        cursor.close()
        log_activity(admin_id, f"deletou a categoria ID {category_id}.")
        return jsonify({'message': 'Categoria deletada com sucesso.'})
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': f'Erro ao deletar categoria: {str(e)}'}), 500


# --- ASSOCIAÇÃO DE CATEGORIAS (Admin) ---

@app.route('/api/admin/user/<int:user_id>/categories', methods=['GET'])
@token_required # ALTERAÇÃO JWT
def get_user_categories(current_user, user_id):
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403
        
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT category_id FROM user_categories WHERE user_id = %s", (user_id,))
        category_ids = [row['category_id'] for row in cursor.fetchall()]
        cursor.close()
        return jsonify(category_ids)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/user/<int:user_id>/categories', methods=['PUT'])
@token_required # ALTERAÇÃO JWT
def set_user_categories(current_user, user_id):
    data = request.json
    # ALTERAÇÃO JWT: Usa ID do token
    admin_id = current_user['id']
    category_ids = data.get('category_ids', []) 

    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("DELETE FROM user_categories WHERE user_id = %s", (user_id,))
        
        if category_ids:
            values_to_insert = [(user_id, cat_id) for cat_id in category_ids]
            query = "INSERT INTO user_categories (user_id, category_id) VALUES (%s, %s)"
            cursor.executemany(query, values_to_insert)
            
        mysql.connection.commit()
        cursor.close()
        
        log_activity(admin_id, f"atualizou as categorias para o usuário ID {user_id}.")
        return jsonify({'message': 'Categorias do usuário atualizadas com sucesso.'})
    except Exception as e:
        mysql.connection.rollback()
        cursor.close()
        return jsonify({'error': f'Erro ao atualizar categorias: {str(e)}'}), 500


@app.route('/api/admin/category/<int:category_id>/users', methods=['GET'])
@token_required # ALTERAÇÃO JWT
def get_category_users(current_user, category_id):
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403
        
    try:
        cursor = mysql.connection.cursor()
        query = """
            SELECT 
                u.id, 
                u.username,
                u.job_title,
                (uc.user_id IS NOT NULL) AS is_associated
            FROM users u
            LEFT JOIN user_categories uc ON u.id = uc.user_id AND uc.category_id = %s
            WHERE u.role = 'funcionario'
            ORDER BY u.username ASC
        """
        cursor.execute(query, (category_id,))
        users_list = cursor.fetchall()
        
        for user in users_list:
            user['is_associated'] = bool(user['is_associated'])
            
        cursor.close()
        return jsonify(users_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/category/<int:category_id>/users', methods=['PUT'])
@token_required # ALTERAÇÃO JWT
def set_category_users(current_user, category_id):
    data = request.json
    # ALTERAÇÃO JWT: Usa ID do token
    admin_id = current_user['id']
    user_ids = data.get('user_ids', []) 

    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("DELETE FROM user_categories WHERE category_id = %s", (category_id,))
        
        if user_ids:
            values_to_insert = [(user_id, category_id) for user_id in user_ids]
            query = "INSERT INTO user_categories (user_id, category_id) VALUES (%s, %s)"
            cursor.executemany(query, values_to_insert)
            
        mysql.connection.commit()
        cursor.close()
        
        log_activity(admin_id, f"atualizou os usuários para a categoria ID {category_id}.")
        return jsonify({'message': 'Usuários da categoria atualizados com sucesso.'})
    except Exception as e:
        mysql.connection.rollback()
        cursor.close()
        return jsonify({'error': f'Erro ao atualizar usuários da categoria: {str(e)}'}), 500


# --- ================================================ ---
# --- ROTAS DA CENTRAL DE PRIVACIDADE (DPO)
# --- ================================================ ---
@app.route('/api/dpo-request', methods=['POST'])
@token_required # ALTERAÇÃO JWT
def submit_dpo_request(current_user):
    data = request.json
    # ALTERAÇÃO JWT: Usa ID do token
    user_id = current_user['id']
    request_type = data.get('request_type')
    message = data.get('message_text')
    
    if not all([request_type, message]):
        return jsonify({'error': 'Dados incompletos.'}), 400
        
    try:
        scheduled_date = None
        if request_type == 'anonymization':
            cursor_check = mysql.connection.cursor()
            cursor_check.execute(
                "SELECT id FROM dpo_requests WHERE user_id = %s AND request_type = 'anonymization_request' AND status = 'pending'",
                (user_id,)
            )
            if cursor_check.fetchone():
                cursor_check.close()
                return jsonify({'message': 'Você já possui uma solicitação de exclusão pendente.'}), 200
            cursor_check.close()
            
            request_type = 'anonymization_request' 
            scheduled_date = datetime.now() + timedelta(days=7)
            message = f"[Solicitação manual do usuário] {message}"

        cursor = mysql.connection.cursor()
        cursor.execute(
            """INSERT INTO dpo_requests (user_id, request_type, message_text, status, created_at, scheduled_for) 
               VALUES (%s, %s, %s, 'pending', NOW(), %s)""",
            (user_id, request_type, message, scheduled_date)
        )
        mysql.connection.commit()
        
        log_activity(user_id, f"enviou uma solicitação de DPO do tipo '{request_type}'.")
        return jsonify({'message': 'Sua solicitação foi enviada ao DPO com sucesso.'}), 201
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Erro ao salvar solicitação DPO: {e}")
        return jsonify({'error': 'Erro ao processar sua solicitação.'}), 500

@app.route('/api/admin/dpo-requests', methods=['GET'])
@token_required # ALTERAÇÃO JWT
def get_dpo_requests(current_user):
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403
        
    cursor = mysql.connection.cursor()
    
    query = """
        SELECT r.id, r.request_type, r.message_text, r.status, r.created_at, r.response_text, r.responded_at, r.scheduled_for,
               u.username AS user_username, a.username AS admin_username
        FROM dpo_requests r
        LEFT JOIN users u ON r.user_id = u.id 
        LEFT JOIN users a ON r.responded_by_id = a.id
        ORDER BY r.status ASC, r.created_at DESC
    """
    
    cursor.execute(query)
    requests_list = cursor.fetchall()
    cursor.close()
    
    for req in requests_list:
        if isinstance(req.get('created_at'), datetime): req['created_at'] = req['created_at'].isoformat()
        if isinstance(req.get('responded_at'), datetime): req['responded_at'] = req['responded_at'].isoformat()
        if isinstance(req.get('scheduled_for'), datetime): req['scheduled_for'] = req['scheduled_for'].isoformat()
            
    return jsonify(requests_list)

@app.route('/api/admin/dpo-pending-count', methods=['GET'])
@token_required # ALTERAÇÃO JWT
def get_dpo_pending_count(current_user):
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403
        
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT COUNT(id) as pendingCount FROM dpo_requests WHERE status = 'pending'")
        result = cursor.fetchone()
        cursor.close()
        return jsonify(result), 200
        
    except Exception as e:
        cursor.close()
        print(f"Erro ao contar DPO pendentes: {e}")
        return jsonify({'error': 'Erro ao contar solicitações.'}), 500

@app.route('/api/admin/dpo-request/<int:req_id>', methods=['PUT'])
@token_required # ALTERAÇÃO JWT
def respond_dpo_request(current_user, req_id):
    data = request.json
    # ALTERAÇÃO JWT: Usa ID do token
    admin_id = current_user['id']
    response_text = data.get('response_text')
    
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403
    if not response_text:
        return jsonify({'error': 'O texto de resposta é obrigatório.'}), 400
        
    try:
        cursor = mysql.connection.cursor()
        
        cursor.execute("SELECT request_type FROM dpo_requests WHERE id = %s", (req_id,))
        req = cursor.fetchone()
        
        if req and req['request_type'] == 'anonymization_request':
            cursor.close()
            return jsonify({'error': 'Este tipo de solicitação deve ser executada, não respondida.'}), 400
            
        cursor.execute(
            """UPDATE dpo_requests 
               SET status = 'answered', 
                   response_text = %s, 
                   responded_by_id = %s, 
                   responded_at = NOW()
               WHERE id = %s""",
            (response_text, admin_id, req_id)
        )
        mysql.connection.commit()
        cursor.close()
        
        log_activity(admin_id, f"respondeu à solicitação DPO ID {req_id}.")
        return jsonify({'message': 'Resposta enviada com sucesso.'}), 200
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Erro ao responder solicitação DPO: {e}")
        return jsonify({'error': 'Erro ao salvar resposta.'}), 500


@app.route('/api/admin/dpo-request/<int:req_id>', methods=['DELETE'])
@token_required # ALTERAÇÃO JWT
def admin_delete_dpo_request(current_user, req_id):
    # ALTERAÇÃO JWT: Usa ID do token
    admin_id = current_user['id']
    
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403
        
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("DELETE FROM dpo_requests WHERE id = %s", (req_id,))
        mysql.connection.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            return jsonify({'error': 'Solicitação não encontrada.'}), 404
            
        cursor.close()
        log_activity(admin_id, f"deletou a solicitação DPO ID {req_id}.")
        return jsonify({'message': 'Solicitação DPO deletada com sucesso.'}), 200
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Erro ao deletar solicitação DPO: {e}")
        return jsonify({'error': 'Erro ao deletar solicitação.'}), 500


@app.route('/api/user/dpo-requests', methods=['GET'])
@token_required # ALTERAÇÃO JWT
def get_user_dpo_requests(current_user):
    # ALTERAÇÃO JWT: Usa ID do token
    user_id = current_user['id']
    
    cursor = mysql.connection.cursor()
    query = """
        SELECT r.id, r.request_type, r.message_text, r.status, r.created_at, 
               r.response_text, r.responded_at, r.scheduled_for, a.username AS admin_username
        FROM dpo_requests r
        LEFT JOIN users a ON r.responded_by_id = a.id
        WHERE r.user_id = %s
        ORDER BY r.created_at DESC
    """
    cursor.execute(query, (user_id,))
    requests_list = cursor.fetchall()
    cursor.close()
    
    for req in requests_list:
        if isinstance(req.get('created_at'), datetime): req['created_at'] = req['created_at'].isoformat()
        if isinstance(req.get('responded_at'), datetime): req['responded_at'] = req['responded_at'].isoformat()
        if isinstance(req.get('scheduled_for'), datetime): req['scheduled_for'] = req['scheduled_for'].isoformat()
            
    return jsonify(requests_list)


# --- ================================================ ---
# --- Rota de Execução de Exclusão - TEXTO AJUSTADO
# --- ================================================ ---
@app.route('/api/admin/execute-anonymization', methods=['POST'])
@token_required # ALTERAÇÃO JWT
def admin_execute_anonymization(current_user):
    data = request.json
    # ALTERAÇÃO JWT: Usa ID do token
    admin_id = current_user['id']
    request_id = data.get('request_id')
    
    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403
        
    cursor = mysql.connection.cursor()
    try:
        # 1. Encontra a solicitação e o ID do usuário alvo
        cursor.execute(
            "SELECT user_id, status FROM dpo_requests WHERE id = %s AND request_type = 'anonymization_request'", 
            (request_id,)
        )
        dpo_req = cursor.fetchone()
        
        if not dpo_req:
            cursor.close()
            return jsonify({'error': 'Solicitação de exclusão não encontrada.'}), 404
            
        if dpo_req['status'] == 'answered':
            cursor.close()
            return jsonify({'error': 'Esta solicitação já foi executada.'}), 400
            
        user_id_to_delete = dpo_req['user_id']
        
        # 2. Lógica de segurança (ex: último admin)
        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id_to_delete,))
        user = cursor.fetchone()
        if user and user['role'] == 'admin':
            cursor.execute("SELECT COUNT(*) as admin_count FROM users WHERE role = 'admin'")
            admin_count = cursor.fetchone()['admin_count']
            if admin_count <= 1:
                cursor.close()
                return jsonify({'error': 'Execução falhou: Este é o único administrador.'}), 403

        # 3. Executa a anonimização (Ainda tecnicamente anonimização para não quebrar chaves estrangeiras)
        anon_username = f"usuario_anonimizado_{user_id_to_delete}"
        anon_email = f"deleted_{user_id_to_delete}@taskflow.up"
        null_salt = create_salt() 
        null_pass = hash_password(secrets.token_hex(32), null_salt)
        
        cursor.execute(
            """UPDATE users 
               SET username = %s, email = %s, job_title = 'Ex-Funcionário', 
                   password_hash = %s, salt = %s, needs_password_reset = 1,
                   is_totp_enabled = 0, totp_secret = NULL
               WHERE id = %s""",
            (anon_username, anon_email, null_pass, null_salt, user_id_to_delete)
        )
        
        cursor.execute("UPDATE task_comments SET text = '[comentário removido pelo usuário]' WHERE user_id = %s", (user_id_to_delete,))
        cursor.execute("UPDATE chat_messages SET text = '[mensagem removido pelo usuário]' WHERE user_id = %s", (user_id_to_delete,))
        cursor.execute("DELETE FROM task_read_timestamps WHERE user_id = %s", (user_id_to_delete,))
        
        cursor.execute("DELETE FROM user_categories WHERE user_id = %s", (user_id_to_delete,))
        
        # 4. Atualiza a solicitação DPO para "answered" - VISUAL AJUSTADO: "exclusão"
        response_text = f"Conta excluída com sucesso pelo Admin ID {admin_id}."
        cursor.execute(
            """UPDATE dpo_requests 
               SET status = 'answered', response_text = %s, responded_by_id = %s, responded_at = NOW()
               WHERE id = %s""",
            (response_text, admin_id, request_id)
        )
        
        mysql.connection.commit()
        
        # VISUAL AJUSTADO: "exclusão"
        log_activity(admin_id, f"executou a exclusão para o usuário ID {user_id_to_delete} (Solicitação DPO ID {request_id}).") 
        
        cursor.close()
        # VISUAL AJUSTADO: "exclusão"
        return jsonify({'message': 'Conta excluída com sucesso.'}), 200
        
    except Exception as e:
        mysql.connection.rollback()
        cursor.close()
        print(f"Erro ao executar exclusão: {e}") 
        return jsonify({'error': f'Erro ao processar exclusão: {str(e)}'}), 500


# --- ROTAS DE IMPERSONAÇÃO (SSO) ---
@app.route('/api/admin/impersonate', methods=['POST'])
@token_required # ALTERAÇÃO JWT
def admin_impersonate_start(current_user):
    data = request.json
    # ALTERAÇÃO JWT: Usa ID do token
    admin_id = current_user['id']
    target_user_id = data.get('target_user_id')

    if not is_admin_check(current_user):
        return jsonify({'error': 'Acesso negado.'}), 403
    if admin_id == target_user_id:
        return jsonify({'error': 'Você não pode impersonar a si mesmo.'}), 400

    token = secrets.token_hex(32)
    impersonation_tokens[token] = {
        'admin_id': admin_id,
        'target_user_id': target_user_id,
        'expires_at': datetime.now().timestamp() + 60
    }
    
    log_activity(admin_id, f"iniciou uma sessão de impersonação para o usuário ID {target_user_id}.")
    
    return jsonify({'token': token})

@app.route('/api/impersonate/login', methods=['POST'])
def impersonate_login():
    token = request.json.get('token')
    
    if not token or token not in impersonation_tokens:
        return jsonify({'error': 'Token de impersonação inválido ou expirado.'}), 403
        
    token_data = impersonation_tokens.pop(token) 
    
    if datetime.now().timestamp() > token_data['expires_at']:
        return jsonify({'error': 'Token de impersonação expirado.'}), 403

    target_user_id = token_data['target_user_id']
    admin_id = token_data['admin_id']
    
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, username, email, role, job_title FROM users WHERE id = %s", (target_user_id,))
    user_row = cursor.fetchone()
    cursor.close()
    
    if not user_row:
        return jsonify({'error': 'Usuário alvo não encontrado.'}), 404

    # ALTERAÇÃO JWT: Gera token para o alvo
    jwt_token = generate_jwt_token(target_user_id)

    user_data = {
        'id': user_row['id'],
        'username': user_row['username'],
        'email': user_row['email'],
        'role': user_row['role'],
        'jobTitle': user_row['job_title'],
        'needsPasswordReset': False,
        'impersonating': True,
        'original_admin_id': admin_id
    }
    
    # ALTERAÇÃO JWT: Retorna o token
    return jsonify({'message': 'Impersonação bem-sucedida.', 'token': jwt_token, 'user': user_data}), 200


# --- Rotas 2FA ---

@app.route('/api/user/totp-setup', methods=['POST'])
@token_required # ALTERAÇÃO JWT
def totp_setup(current_user):
    # ALTERAÇÃO JWT: Usa ID do token
    user_id = current_user['id']

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT username, email FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        return jsonify({'error': 'Usuário não encontrado.'}), 404

    secret = pyotp.random_base32()
    
    cursor.execute("UPDATE users SET totp_secret = %s, is_totp_enabled = 0 WHERE id = %s", (secret, user_id))
    mysql.connection.commit()
    cursor.close()

    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user['email'] or user['username'], 
        issuer_name="Task FlowUp"
    )
    
    return jsonify({
        'message': 'Segredo 2FA gerado. Por favor, verifique.',
        'secret': secret,
        'provisioning_uri': provisioning_uri
    }), 200

@app.route('/api/user/totp-verify-setup', methods=['POST'])
@token_required # ALTERAÇÃO JWT
def totp_verify_setup(current_user):
    data = request.json
    # ALTERAÇÃO JWT: Usa ID do token
    user_id = current_user['id']
    totp_code = data.get('totp_code')

    if not totp_code:
        return jsonify({'error': 'Código 2FA é obrigatório.'}), 400
    
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT totp_secret FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user or not user['totp_secret']:
        cursor.close()
        return jsonify({'error': 'Segredo 2FA não encontrado. Tente a configuração novamente.'}), 404
    
    totp = pyotp.TOTP(user['totp_secret'])
    if not totp.verify(totp_code):
        cursor.close()
        return jsonify({'error': 'Código 2FA inválido.'}), 401
    
    cursor.execute("UPDATE users SET is_totp_enabled = 1 WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cursor.close()
    
    log_activity(user_id, "ativou o 2FA em sua conta.")
    return jsonify({'message': '2FA ativado com sucesso!'}), 200

@app.route('/api/user/totp-disable', methods=['POST'])
@token_required # ALTERAÇÃO JWT
def totp_disable(current_user):
    data = request.json
    # ALTERAÇÃO JWT: Usa ID do token
    user_id = current_user['id']
    password = data.get('password')

    if not password:
        return jsonify({'error': 'Senha é obrigatória.'}), 400

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT password_hash, salt FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        return jsonify({'error': 'Usuário não encontrado.'}), 404
    
    is_new_hash_match = hash_password(password, user['salt']) == user['password_hash']
    is_legacy_hash_match = hash_password_legacy(password, user['salt']) == user['password_hash']

    if not is_new_hash_match and not is_legacy_hash_match:
        cursor.close()
        return jsonify({'error': 'Senha incorreta.'}), 401

    cursor.execute("UPDATE users SET is_totp_enabled = 0, totp_secret = NULL WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cursor.close()
    
    log_activity(user_id, "desativou o 2FA em sua conta.")
    return jsonify({'message': '2FA desativado com sucesso.'}), 200


if __name__ == '__main__':
    is_debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=is_debug, port=5001)
