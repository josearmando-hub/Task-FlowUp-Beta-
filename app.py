from flask import Flask, request, jsonify
from flask_mysqldb import MySQL
import hashlib
import os 
import secrets
from flask_cors import CORS
from datetime import date, datetime, timedelta 
import pyotp # <-- ATUALIZAÇÃO: Importação necessária

app = Flask(__name__)
CORS(app)

# --- Configurações do banco de dados MySQL ---
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', 'Foda12345')
app.config['MYSQL_DB'] = 'task_flowup'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

ADMIN_REGISTRATION_KEY = os.environ.get('ADMIN_KEY', 'admin-secret-key')

if app.config['MYSQL_PASSWORD'] == 'Foda12345' or ADMIN_REGISTRATION_KEY == 'admin-secret-key':
    print("="*50)
    print("AVISO DE SEGURANÇA: Você está usando senhas/chaves padrão.")
    print("Em produção, defina as variáveis de ambiente MYSQL_PASSWORD e ADMIN_KEY.")
    print("="*50)

mysql = MySQL(app)

impersonation_tokens = {}


# --- ================================== ---
# --- Hashing de Senha ---
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

def is_admin(user_id):
    if not user_id:
        return False
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        if user and user['role'] == 'admin':
            return True
        return False
    except Exception as e:
        print(f"Erro ao verificar admin: {e}")
        return False


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
    
    # --- ATUALIZAÇÃO: Seleciona is_totp_enabled ---
    cursor.execute(
        "SELECT id, username, password_hash, salt, role, email, needs_password_reset, job_title, is_totp_enabled "
        "FROM users WHERE username = %s", 
        (username,)
    )
    user_row = cursor.fetchone()
    cursor.close()

    if not user_row:
        return jsonify({'error': 'Usuário não encontrado.'}), 404

    # --- Migração de Hash ---
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
    
    # --- ATUALIZAÇÃO: Checagem 2FA ---
    if user_row['is_totp_enabled']:
        # 2FA está ativo. Não logue o usuário, peça o código.
        return jsonify({'2fa_required': True}), 200
    # --- Fim da Atualização ---

    user_data = {
        'id': user_row['id'],
        'username': user_row['username'],
        'email': user_row['email'],
        'role': user_row['role'],
        'jobTitle': user_row['job_title'],
        'needsPasswordReset': bool(user_row['needs_password_reset'])
    }
    
    log_activity(user_data['id'], f"fez login.")

    return jsonify({'message': 'Login bem-sucedido.', 'user': user_data}), 200


# --- ================================== ---
# --- ATUALIZAÇÃO: Nova Rota de Login 2FA
# --- ================================== ---
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

    # Código 2FA válido, prossiga com o login
    cursor.close()
    user_data = {
        'id': user_row['id'],
        'username': user_row['username'],
        'email': user_row['email'],
        'role': user_row['role'],
        'jobTitle': user_row['job_title'],
        'needsPasswordReset': bool(user_row['needs_password_reset'])
    }
    
    log_activity(user_data['id'], f"fez login com 2FA.")
    return jsonify({'message': 'Login 2FA bem-sucedido.', 'user': user_data}), 200
# --- Fim da Nova Rota ---


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
def reset_password():
    data = request.json
    user_id, new_password = data.get('userId'), data.get('newPassword')

    if not all([user_id, new_password]):
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
def change_password():
    data = request.json
    user_id, old_password, new_password = data.get('userId'), data.get('oldPassword'), data.get('newPassword')

    if not all([user_id, old_password, new_password]):
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
# --- ATUALIZAÇÃO LGPD/TEXTO: Rota de Auto-Exclusão (Solicitação)
# --- ================================================ ---
@app.route('/api/user/delete-self', methods=['POST'])
def delete_self_account():
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'error': 'ID de usuário não fornecido.'}), 400
        
    cursor = mysql.connection.cursor()
    try:
        # Verifica se já existe uma solicitação pendente
        cursor.execute(
            "SELECT id FROM dpo_requests WHERE user_id = %s AND request_type = 'anonymization_request' AND status = 'pending'",
            (user_id,)
        )
        if cursor.fetchone():
            cursor.close()
            # ATUALIZAÇÃO DE TEXTO
            return jsonify({'message': 'Você já possui uma solicitação de exclusão pendente.'}), 200

        # Define a data de agendamento (7 dias a partir de agora)
        scheduled_date = datetime.now() + timedelta(days=7)
        # ATUALIZAÇÃO DE TEXTO (manter 'anonimização' para o DPO)
        message_text = "Solicitação de exclusão (anonimização) de conta iniciada pelo usuário. Agendada para execução em 7 dias."
        request_type = "anonymization_request" # Tipo interno, não mudar
        
        # Insere a solicitação de DPO
        cursor.execute(
            """INSERT INTO dpo_requests (user_id, request_type, message_text, status, created_at, scheduled_for) 
               VALUES (%s, %s, %s, 'pending', NOW(), %s)""",
            (user_id, request_type, message_text, scheduled_date)
        )
        mysql.connection.commit()
        
        # ATUALIZAÇÃO DE TEXTO
        log_activity(user_id, f"solicitou a exclusão (anonimização) da própria conta, agendada para {scheduled_date.strftime('%Y-%m-%d')}.")
        
        cursor.close()
        # ATUALIZAÇÃO DE TEXTO
        return jsonify({'message': 'Solicitação de exclusão recebida. Sua conta será excluída (anonimizada) em 7 dias. Você pode cancelar esta solicitação entrando em contato com o DPO.'}), 200
        
    except Exception as e:
        mysql.connection.rollback()
        cursor.close()
        print(f"Erro ao solicitar exclusão: {e}") # ATUALIZAÇÃO DE TEXTO
        return jsonify({'error': f'Erro ao processar solicitação: {str(e)}'}), 500
# --- Fim da Atualização ---


# --- Rotas de Usuário ---
@app.route('/api/user/<int:user_id>', methods=['GET'])
def get_user_details(user_id):
    cursor = mysql.connection.cursor()
    
    # --- ATUALIZAÇÃO: Seleciona is_totp_enabled ---
    cursor.execute(
        "SELECT id, username, email, role, job_title, is_totp_enabled "
        "FROM users WHERE id = %s", 
        (user_id,)
    )
    user = cursor.fetchone()
    cursor.close()
    
    if not user:
        return jsonify({'error': 'Usuário não encontrado.'}), 404
    
    # --- ATUALIZAÇÃO: Converte o booleano para o JS ---
    user['is_totp_enabled'] = bool(user['is_totp_enabled'])
    
    return jsonify(user)
# --- Fim da Atualização ---


@app.route('/api/user/<int:user_id>', methods=['PUT'])
def update_user_profile(user_id):
    data = request.json
    acting_user_id = data.get('acting_user_id')
    if not acting_user_id:
        return jsonify({'error': 'ID do usuário atuante é obrigatório.'}), 401
        
    if acting_user_id != user_id and not is_admin(acting_user_id):
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

    if is_admin(acting_user_id) and 'role' in data:
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
def get_employees():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, username, email, job_title FROM users WHERE role = 'funcionario' ORDER BY username ASC")
    employees = cursor.fetchall()
    cursor.close()
    return jsonify(employees)


# --- ROTA DE ANÁLISE ---
@app.route('/api/analytics', methods=['GET'])
def get_analytics():
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


# --- ================================== ---
# --- ROTAS DE TAREFAS (MODIFICADAS) ---
# --- ================================== ---

@app.route('/api/tasks', methods=['GET', 'POST'])
def tasks():
    cursor = mysql.connection.cursor()
    
    # --- LÓGICA DO GET MODIFICADA (PARA FILTRAGEM DE PERMISSÃO) ---
    if request.method == 'GET':
        user_id = request.args.get('user_id')
        user_role = 'funcionario' # Padrão
        
        if not user_id or user_id == '0':
            user_id = 0 # Define para a query de 'unread' funcionar
        else:
            # Se temos um user_id, vamos checar o 'role' dele
            try:
                user_id = int(user_id)
                cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if user:
                    user_role = user['role']
            except Exception as e:
                print(f"Erro ao checar role do usuário: {e}")
                # Mantém o role de funcionário por segurança
        
        
        # Query base (Admin vê tudo)
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
        
        params = [user_id] # Parâmetro para o sub-select de 'unread'

        # Se for funcionário, aplicamos o filtro de segurança
        if user_role == 'funcionario':
            query += """
                -- Filtro de permissão:
                -- Junta com user_categories ONDE (o usuário está na categoria E a tarefa também)
                -- OU a tarefa não tem categoria (category_id IS NULL), permitindo que todos vejam
                LEFT JOIN user_categories uc ON t.category_id = uc.category_id
                WHERE (uc.user_id = %s OR t.category_id IS NULL)
            """
            # Adiciona o user_id de novo, desta vez para o filtro de permissão
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
    
    # --- LÓGICA DO POST (MODIFICADA PARA CATEGORIA) ---
    if request.method == 'POST':
        data = request.json
        creator_id, assigned_to_id = data.get('creator_id'), data.get('assigned_to_id') or None
        due_date = data.get('due_date') or None
        created_at_time = datetime.now()
        
        # --- MODIFICADO ---
        category_id = data.get('category_id') or None
        
        # --- MODIFICADO --- Query atualizada
        cursor.execute(
            "INSERT INTO tasks (title, description, priority, due_date, creator_id, assigned_to_id, created_at, category_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", 
            (data.get('title'), data.get('description'), data.get('priority'), due_date, creator_id, assigned_to_id, created_at_time, category_id)
        )
        mysql.connection.commit()
        cursor.close()
        log_activity(creator_id, f"criou a tarefa: '{data.get('title')}'")
        return jsonify({'message': 'Tarefa criada com sucesso.'}), 201


@app.route('/api/tasks/<int:task_id>', methods=['GET', 'PUT', 'DELETE'])
def manage_task(task_id):
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
        acting_user_id = data.get('acting_user_id')
        
        if 'completed' not in data and not is_admin(acting_user_id):
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
            
            # --- MODIFICADO ---
            category_id = data.get('category_id') or None
            
            # --- MODIFICADO --- Query atualizada
            cursor.execute(
                "UPDATE tasks SET title = %s, description = %s, priority = %s, due_date = %s, assigned_to_id = %s, category_id = %s WHERE id = %s",
                (new_title, data.get('description'), data.get('priority'), due_date, assigned_to_id, category_id, task_id)
            )
            log_activity(acting_user_id, f"editou a tarefa '{current_title}' (novo título: '{new_title}')")
            
        mysql.connection.commit()
        cursor.close()
        return jsonify({'message': f'Tarefa {task_id} atualizada.'})

    if request.method == 'DELETE':
        data = request.json if request.is_json else {}
        acting_user_id = data.get('acting_user_id')

        if not is_admin(acting_user_id):
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


# --- ENDPOINT: Marcar Tarefa como Lida ---
@app.route('/api/tasks/<int:task_id>/mark-as-read', methods=['POST'])
def mark_task_as_read(task_id):
    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID é obrigatório.'}), 400
    
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
def comments(task_id):
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
        user_id = data.get('user_id')
        text = data.get('text')
        cursor.execute("INSERT INTO task_comments (task_id, user_id, text) VALUES (%s, %s, %s)", (task_id, user_id, text))
        mysql.connection.commit()
        cursor.close()
        log_activity(user_id, f"comentou na tarefa ID {task_id}: '{text[:30]}...'")
        return jsonify({'message': 'Comentário adicionado.'}), 201


# --- Rotas de Chat ---
@app.route('/api/chat/messages', methods=['GET', 'POST'])
def chat_messages():
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
        user_id = data.get('user_id')
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


# --- NOVAS ROTAS DE NOTIFICAÇÃO DO CHAT GLOBAL ---
@app.route('/api/chat/unread-count', methods=['GET'])
def get_chat_unread_count():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID é obrigatório.'}), 400

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
def mark_chat_as_read():
    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID é obrigatório.'}), 400

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


# --- ROTA DE ADMIN (PURGE CHAT) ---
@app.route('/api/admin/chat/purge', methods=['DELETE'])
def admin_purge_chat():
    data = request.json
    admin_id = data.get('admin_user_id')
    
    if not is_admin(admin_id):
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


# --- ATUALIZAÇÃO: Nova Rota (PURGE ACTIVITY LOG) ---
@app.route('/api/admin/activity-log/purge', methods=['DELETE'])
def admin_purge_activity_log():
    data = request.json
    admin_id = data.get('admin_user_id')
    
    if not is_admin(admin_id):
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
def get_activity_log():
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


# --- Rota de Log de Atividades (LGPD) ---
@app.route('/api/user/my-activity-log', methods=['GET'])
def get_user_activity_log():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'ID de usuário é obrigatório.'}), 400
        
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
def admin_get_all_users():
    admin_id = request.args.get('admin_user_id')
    if not is_admin(admin_id):
        return jsonify({'error': 'Acesso negado. Requer privilégios de administrador.'}), 403
        
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, username, email, role, job_title, needs_password_reset FROM users ORDER BY username ASC")
    users = cursor.fetchall()
    cursor.close()
    return jsonify(users)

@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
def admin_delete_user(user_id):
    data = request.json
    admin_id = data.get('admin_user_id')
    
    if not is_admin(admin_id):
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
        
        # --- MODIFICADO --- Adicionada limpeza da nova tabela de associação
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
def admin_force_reset_password():
    data = request.json
    admin_id = data.get('admin_user_id')
    target_user_id = data.get('target_user_id')
    
    if not is_admin(admin_id):
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


# --- ================================== ---
# --- ATUALIZAÇÃO: ROTAS DE CATEGORIAS (CRUD)
# --- ================================== ---

@app.route('/api/categories', methods=['GET'])
def get_categories():
    # Rota pública para todos os usuários logados verem as categorias
    try:
        cursor = mysql.connection.cursor()
        
        # --- ATUALIZAÇÃO: Adicionada contagem de tarefas e usuários ---
        cursor.execute("""
            SELECT 
                tc.id, tc.name, tc.description, 
                (SELECT COUNT(t.id) FROM tasks t WHERE t.category_id = tc.id) as task_count,
                (SELECT COUNT(uc.user_id) FROM user_categories uc WHERE uc.category_id = tc.id) as user_count
            FROM task_categories tc 
            ORDER BY tc.name ASC
        """)
        # --- FIM DA ATUALIZAÇÃO ---
        
        categories = cursor.fetchall()
        cursor.close()
        return jsonify(categories)
    except Exception as e:
        print(f"Erro ao buscar categorias: {e}")
        return jsonify({'error': 'Erro ao buscar categorias.'}), 500

@app.route('/api/admin/categories', methods=['POST'])
def create_category():
    data = request.json
    admin_id = data.get('admin_user_id')
    name = data.get('name')
    
    if not is_admin(admin_id):
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
def update_category(category_id):
    data = request.json
    admin_id = data.get('admin_user_id')
    name = data.get('name')
    
    if not is_admin(admin_id):
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
def delete_category(category_id):
    data = request.json if request.is_json else {}
    admin_id = data.get('admin_user_id') # O ID do admin pode vir no corpo
    
    # Se não estiver no corpo, tente pegar dos args (para testes)
    if not admin_id:
        admin_id = request.args.get('admin_user_id')

    if not is_admin(admin_id):
        return jsonify({'error': 'Acesso negado.'}), 403

    try:
        cursor = mysql.connection.cursor()
        
        # --- MODIFICADO --- Deleta primeiro as associações
        cursor.execute("DELETE FROM user_categories WHERE category_id = %s", (category_id,))
        # (A coluna 'category_id' na tabela 'tasks' será definida como NULL automaticamente)
        
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


# --- ================================== ---
# --- NOVO BLOCO: ASSOCIAÇÃO DE CATEGORIAS (Admin)
# --- ================================== ---

@app.route('/api/admin/user/<int:user_id>/categories', methods=['GET'])
def get_user_categories(user_id):
    # (O user_id vem da URL)
    # Precisamos verificar se quem *pergunta* é um admin
    
    acting_admin_id = request.args.get('admin_user_id')
    if not is_admin(acting_admin_id):
        return jsonify({'error': 'Acesso negado.'}), 403
        
    try:
        cursor = mysql.connection.cursor()
        # Pega apenas os IDs das categorias que o usuário já possui
        cursor.execute("SELECT category_id FROM user_categories WHERE user_id = %s", (user_id,))
        # Transforma a lista de dicts (ex: [{'category_id': 1}, ...]) em uma lista simples (ex: [1, 5, 7])
        category_ids = [row['category_id'] for row in cursor.fetchall()]
        cursor.close()
        return jsonify(category_ids)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/user/<int:user_id>/categories', methods=['PUT'])
def set_user_categories(user_id):
    data = request.json
    admin_id = data.get('admin_user_id')
    category_ids = data.get('category_ids', []) # Espera uma lista de IDs, ex: [1, 5, 7]

    if not is_admin(admin_id):
        return jsonify({'error': 'Acesso negado.'}), 403

    cursor = mysql.connection.cursor()
    try:
        # 1. Apaga todas as associações antigas deste usuário
        cursor.execute("DELETE FROM user_categories WHERE user_id = %s", (user_id,))
        
        # 2. Insere as novas associações (se a lista não estiver vazia)
        if category_ids:
            # Prepara os dados para uma inserção em massa
            # Transforma [1, 5, 7] em [(user_id, 1), (user_id, 5), (user_id, 7)]
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


# --- ================================== ---
# --- ATUALIZAÇÃO: NOVAS ROTAS DE ASSOCIAÇÃO (Inverso)
# --- ================================== ---

@app.route('/api/admin/category/<int:category_id>/users', methods=['GET'])
def get_category_users(category_id):
    """
    Busca todos os funcionários e indica quais estão associados a UMA categoria específica.
    """
    acting_admin_id = request.args.get('admin_user_id')
    if not is_admin(acting_admin_id):
        return jsonify({'error': 'Acesso negado.'}), 403
        
    try:
        cursor = mysql.connection.cursor()
        # Seleciona todos os funcionários (role='funcionario')
        # E usa um LEFT JOIN para verificar se eles estão na tabela de associação
        # para a categoria específica que estamos perguntando (category_id = %s)
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
        
        # Converte o 'is_associated' (0 ou 1) para booleano
        for user in users_list:
            user['is_associated'] = bool(user['is_associated'])
            
        cursor.close()
        return jsonify(users_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/category/<int:category_id>/users', methods=['PUT'])
def set_category_users(category_id):
    """
    Define quais usuários estão associados a UMA categoria específica.
    """
    data = request.json
    admin_id = data.get('admin_user_id')
    user_ids = data.get('user_ids', []) # Espera uma lista de IDs de *usuários*, ex: [1, 5, 7]

    if not is_admin(admin_id):
        return jsonify({'error': 'Acesso negado.'}), 403

    cursor = mysql.connection.cursor()
    try:
        # 1. Apaga todas as associações antigas DESTA CATEGORIA
        cursor.execute("DELETE FROM user_categories WHERE category_id = %s", (category_id,))
        
        # 2. Insere as novas associações (se a lista não estiver vazia)
        if user_ids:
            # Prepara os dados para inserção em massa
            # Transforma [1, 5, 7] em [(1, category_id), (5, category_id), (7, category_id)]
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
# --- ATUALIZAÇÃO LGPD/TEXTO: ROTAS DA CENTRAL DE PRIVACIDADE (DPO)
# --- ================================================ ---
@app.route('/api/dpo-request', methods=['POST'])
def submit_dpo_request():
    data = request.json
    user_id = data.get('acting_user_id')
    request_type = data.get('request_type')
    message = data.get('message_text')
    
    if not all([user_id, request_type, message]):
        return jsonify({'error': 'Dados incompletos.'}), 400
        
    try:
        scheduled_date = None
        # Se for uma solicitação de anonimização, agenda para 7 dias
        if request_type == 'anonymization':
            # Verifica se já existe uma solicitação pendente
            cursor_check = mysql.connection.cursor()
            cursor_check.execute(
                "SELECT id FROM dpo_requests WHERE user_id = %s AND request_type = 'anonymization_request' AND status = 'pending'",
                (user_id,)
            )
            if cursor_check.fetchone():
                cursor_check.close()
                # ATUALIZAÇÃO DE TEXTO
                return jsonify({'message': 'Você já possui uma solicitação de exclusão pendente.'}), 200
            cursor_check.close()
            
            request_type = 'anonymization_request' # Muda o tipo para ser específico
            scheduled_date = datetime.now() + timedelta(days=7)
            message = f"[Solicitação manual do usuário] {message}"

        cursor = mysql.connection.cursor()
        cursor.execute(
            """INSERT INTO dpo_requests (user_id, request_type, message_text, status, created_at, scheduled_for) 
               VALUES (%s, %s, %s, 'pending', NOW(), %s)""",
            (user_id, request_type, message, scheduled_date)
        )
        mysql.connection.commit()
        cursor.close()
        
        log_activity(user_id, f"enviou uma solicitação de DPO do tipo '{request_type}'.")
        return jsonify({'message': 'Sua solicitação foi enviada ao DPO com sucesso.'}), 201
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Erro ao salvar solicitação DPO: {e}")
        return jsonify({'error': 'Erro ao processar sua solicitação.'}), 500

@app.route('/api/admin/dpo-requests', methods=['GET'])
def get_dpo_requests():
    admin_id = request.args.get('admin_user_id')
    if not is_admin(admin_id):
        return jsonify({'error': 'Acesso negado.'}), 403
        
    cursor = mysql.connection.cursor()
    
    # --- INÍCIO DA CORREÇÃO ---
    # Alterado de "JOIN users u" para "LEFT JOIN users u"
    # Isso garante que as solicitações DPO de usuários deletados
    # (usuários "órfãos") ainda sejam listadas.
    query = """
        SELECT r.id, r.request_type, r.message_text, r.status, r.created_at, r.response_text, r.responded_at, r.scheduled_for,
               u.username AS user_username, a.username AS admin_username
        FROM dpo_requests r
        LEFT JOIN users u ON r.user_id = u.id 
        LEFT JOIN users a ON r.responded_by_id = a.id
        ORDER BY r.status ASC, r.created_at DESC
    """
    # --- FIM DA CORREÇÃO ---
    
    cursor.execute(query)
    requests_list = cursor.fetchall()
    cursor.close()
    
    for req in requests_list:
        if isinstance(req.get('created_at'), datetime): req['created_at'] = req['created_at'].isoformat()
        if isinstance(req.get('responded_at'), datetime): req['responded_at'] = req['responded_at'].isoformat()
        if isinstance(req.get('scheduled_for'), datetime): req['scheduled_for'] = req['scheduled_for'].isoformat()
            
    return jsonify(requests_list)

@app.route('/api/admin/dpo-pending-count', methods=['GET'])
def get_dpo_pending_count():
    admin_id = request.args.get('admin_user_id')
    if not is_admin(admin_id):
        return jsonify({'error': 'Acesso negado.'}), 403
        
    cursor = mysql.connection.cursor()
    try:
        # Esta contagem (sem JOIN) está correta.
        # Nós queremos contar solicitações órfãs.
        cursor.execute("SELECT COUNT(id) as pendingCount FROM dpo_requests WHERE status = 'pending'")
        result = cursor.fetchone()
        cursor.close()
        return jsonify(result), 200
        
    except Exception as e:
        cursor.close()
        print(f"Erro ao contar DPO pendentes: {e}")
        return jsonify({'error': 'Erro ao contar solicitações.'}), 500

@app.route('/api/admin/dpo-request/<int:req_id>', methods=['PUT'])
def respond_dpo_request(req_id):
    data = request.json
    admin_id = data.get('admin_user_id')
    response_text = data.get('response_text')
    
    if not is_admin(admin_id):
        return jsonify({'error': 'Acesso negado.'}), 403
    if not response_text:
        return jsonify({'error': 'O texto de resposta é obrigatório.'}), 400
        
    try:
        cursor = mysql.connection.cursor()
        
        cursor.execute("SELECT request_type FROM dpo_requests WHERE id = %s", (req_id,))
        req = cursor.fetchone()
        # ATUALIZAÇÃO DE TEXTO
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
def admin_delete_dpo_request(req_id):
    data = request.json
    admin_id = data.get('admin_user_id')
    
    if not is_admin(admin_id):
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
def get_user_dpo_requests():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'ID de usuário é obrigatório.'}), 400
    
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
# --- ATUALIZAÇÃO LGPD/TEXTO: Rota de Execução de Exclusão
# --- ================================================ ---
@app.route('/api/admin/execute-anonymization', methods=['POST'])
def admin_execute_anonymization():
    data = request.json
    admin_id = data.get('admin_user_id')
    request_id = data.get('request_id')
    
    if not is_admin(admin_id):
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
            # ATUALIZAÇÃO DE TEXTO
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

        # 3. Executa a anonimização
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
        
        # --- MODIFICADO --- Deleta associações de categoria
        cursor.execute("DELETE FROM user_categories WHERE user_id = %s", (user_id_to_delete,))
        
        # 4. Atualiza a solicitação DPO para "answered"
        # ATUALIZAÇÃO DE TEXTO
        response_text = f"Conta excluída (anonimizada) com sucesso pelo Admin ID {admin_id}."
        cursor.execute(
            """UPDATE dpo_requests 
               SET status = 'answered', response_text = %s, respondido_by_id = %s, responded_at = NOW()
               WHERE id = %s""",
            (response_text, admin_id, request_id)
        )
        
        mysql.connection.commit()
        
        # ATUALIZAÇÃO DE TEXTO
        log_activity(admin_id, f"executou a exclusão (anonimização) para o usuário ID {user_id_to_delete} (Solicitação DPO ID {request_id}).") 
        
        cursor.close()
        # ATUALIZAÇÃO DE TEXTO
        return jsonify({'message': 'Conta excluída (anonimizada) com sucesso.'}), 200
        
    except Exception as e:
        mysql.connection.rollback()
        cursor.close()
        print(f"Erro ao executar exclusão: {e}") # ATUALIZAÇÃO DE TEXTO
        return jsonify({'error': f'Erro ao processar exclusão: {str(e)}'}), 500
# --- Fim da Nova Rota ---


# --- ROTAS DE IMPERSONAÇÃO (SSO) ---
@app.route('/api/admin/impersonate', methods=['POST'])
def admin_impersonate_start():
    data = request.json
    admin_id = data.get('admin_user_id')
    target_user_id = data.get('target_user_id')

    if not is_admin(admin_id):
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
    
    return jsonify({'message': 'Impersonação bem-sucedida.', 'user': user_data}), 200


# --- ================================== ---
# --- ATUALIZAÇÃO: Novas Rotas 2FA
# --- ================================== ---

@app.route('/api/user/totp-setup', methods=['POST'])
def totp_setup():
    user_id = request.json.get('user_id')
    if not user_id:
        return jsonify({'error': 'ID de usuário é obrigatório.'}), 400

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT username, email FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.close()
        return jsonify({'error': 'Usuário não encontrado.'}), 404

    # Gera um novo segredo
    secret = pyotp.random_base32()
    
    # Salva o segredo no banco (ainda não está 'enabled')
    cursor.execute("UPDATE users SET totp_secret = %s, is_totp_enabled = 0 WHERE id = %s", (secret, user_id))
    mysql.connection.commit()
    cursor.close()

    # Gera o URI para o QR Code
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
def totp_verify_setup():
    data = request.json
    user_id = data.get('user_id')
    totp_code = data.get('totp_code')

    if not user_id or not totp_code:
        return jsonify({'error': 'ID de usuário e código 2FA são obrigatórios.'}), 400
    
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
    
    # Código válido! Ativa o 2FA
    cursor.execute("UPDATE users SET is_totp_enabled = 1 WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cursor.close()
    
    log_activity(user_id, "ativou o 2FA em sua conta.")
    return jsonify({'message': '2FA ativado com sucesso!'}), 200

@app.route('/api/user/totp-disable', methods=['POST'])
def totp_disable():
    data = request.json
    user_id = data.get('user_id')
    password = data.get('password')

    if not user_id or not password:
        return jsonify({'error': 'ID de usuário e senha são obrigatórios.'}), 400

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT password_hash, salt FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.close()
        return jsonify({'error': 'Usuário não encontrado.'}), 404
    
    # Verifica a senha do usuário
    is_new_hash_match = hash_password(password, user['salt']) == user['password_hash']
    is_legacy_hash_match = hash_password_legacy(password, user['salt']) == user['password_hash']

    if not is_new_hash_match and not is_legacy_hash_match:
        cursor.close()
        return jsonify({'error': 'Senha incorreta.'}), 401

    # Senha correta, desativa o 2FA
    cursor.execute("UPDATE users SET is_totp_enabled = 0, totp_secret = NULL WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cursor.close()
    
    log_activity(user_id, "desativou o 2FA em sua conta.")
    return jsonify({'message': '2FA desativado com sucesso.'}), 200
# --- Fim das Novas Rotas 2FA ---


if __name__ == '__main__':
    is_debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=is_debug, port=5001)
