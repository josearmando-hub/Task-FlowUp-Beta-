-- 1. Apaga o banco de dados antigo (se existir) para começar do zero
DROP DATABASE IF EXISTS `task_flowup`;

-- 2. Cria o novo banco de dados limpo
CREATE DATABASE `task_flowup`;

-- 3. Seleciona o banco de dados para usar
USE `task_flowup`;

-- ==========================
-- TABELA: USERS (Precisa ser criada primeiro)
-- ==========================
CREATE TABLE `users` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `username` VARCHAR(80) NOT NULL UNIQUE,
  `email` VARCHAR(120) UNIQUE,
  `password_hash` VARCHAR(128) NOT NULL,
  `salt` VARCHAR(32) NOT NULL,
  `role` ENUM('admin', 'funcionario') NOT NULL DEFAULT 'funcionario',
  `needs_password_reset` BOOLEAN DEFAULT FALSE,
  `job_title` VARCHAR(100) DEFAULT 'Funcionário',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  -- ====================================================================
  -- >> LINHA NOVA ADICIONADA AQUI <<
  `chat_last_read_at` DATETIME DEFAULT CURRENT_TIMESTAMP
  -- ====================================================================

);

-- ==========================
-- TABELA: TASKS
-- ==========================
CREATE TABLE `tasks` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `title` VARCHAR(255) NOT NULL,
  `description` TEXT,
  `priority` INT NOT NULL DEFAULT 2,
  `due_date` DATE,
  `completed` BOOLEAN NOT NULL DEFAULT FALSE,
  `creator_id` INT,
  `assigned_to_id` INT DEFAULT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  -- Se o criador for deletado, a tarefa continua (SET NULL)
  FOREIGN KEY (`creator_id`) REFERENCES `users`(`id`) ON DELETE SET NULL, 
  FOREIGN KEY (`assigned_to_id`) REFERENCES `users`(`id`) ON DELETE SET NULL
);

-- ==========================
-- TABELA: TASK_COMMENTS
-- ==========================
CREATE TABLE `task_comments` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `task_id` INT NOT NULL,
  `user_id` INT NOT NULL,
  `text` TEXT NOT NULL,
  `timestamp` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  FOREIGN KEY (`task_id`) REFERENCES `tasks`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
);

-- ==========================
-- TABELA: CHAT_MESSAGES (Esta é a tabela do chat global)
-- ==========================
CREATE TABLE `chat_messages` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `text` TEXT NOT NULL,
  `timestamp` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
);

-- ==========================
-- TABELA: DPO_REQUESTS
-- ==========================
CREATE TABLE `dpo_requests` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT,
  `request_type` VARCHAR(50) NOT NULL,
  `message_text` TEXT NOT NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
  `created_at` DATETIME NOT NULL,
  
  `response_text` TEXT,
  `responded_by_id` INT,
  `responded_at` DATETIME,
  
  INDEX (`user_id`),
  INDEX (`status`),
  
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE SET NULL,
  FOREIGN KEY (`responded_by_id`) REFERENCES `users`(`id`) ON DELETE SET NULL
);

-- ==========================
-- TABELA: TASK_READ_TIMESTAMPS (Para "não lidos" das tarefas)
-- ==========================
CREATE TABLE `task_read_timestamps` (
  `user_id` INT NOT NULL,
  `task_id` INT NOT NULL,
  `last_read_at` DATETIME NOT NULL,
  
  PRIMARY KEY (`user_id`, `task_id`),
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`task_id`) REFERENCES `tasks`(`id`) ON DELETE CASCADE
);

-- ==========================
-- TABELA: ACTIVITY_LOG (Criada por último, pois depende de 'users')
-- ==========================
CREATE TABLE `activity_log` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT,
  `action_text` VARCHAR(255) NOT NULL,
  `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE SET NULL
);
