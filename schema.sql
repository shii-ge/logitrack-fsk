CREATE DATABASE IF NOT EXISTS controle_acesso
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

USE controle_acesso;

CREATE TABLE funcionario (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    nome      VARCHAR(100) NOT NULL,
    uid       VARCHAR(30)  NOT NULL,
    pendente  BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE KEY uk_funcionario_uid (uid)
) ENGINE=InnoDB;

CREATE TABLE leitor (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    nome      VARCHAR(100) NOT NULL,
    pendente  BOOLEAN NOT NULL DEFAULT FALSE
) ENGINE=InnoDB;

CREATE TABLE registros (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    uid             VARCHAR(30) NOT NULL,
    funcionario_id  INT NULL,
    leitor_id       INT NOT NULL,
    timestamp       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status          BOOLEAN NOT NULL DEFAULT TRUE, -- TRUE = iniciou período (entrada), FALSE = encerrou período (saída) no leitor

    CONSTRAINT fk_registros_leitor
        FOREIGN KEY (leitor_id) REFERENCES leitor(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_registros_funcionario
        FOREIGN KEY (funcionario_id) REFERENCES funcionario(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    KEY idx_registros_uid (uid),
    KEY idx_registros_timestamp (timestamp)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Trigger: trg_registros_before_insert
--
-- Ao inserir um novo registro (basta informar uid, leitor_id e,
-- opcionalmente, timestamp):
--
--   1) Busca o funcionário correspondente ao uid lido. Se não existir
--      nenhum cadastro com esse uid, CRIA automaticamente um novo
--      funcionário com nome placeholder e pendente = TRUE, e vincula
--      o registro a ele. Isso permite identificar depois, em uma tela
--      administrativa, quem passou o cartão mas ainda não tem nome
--      cadastrado (basta então UPDATE funcionario SET nome = '...',
--      pendente = FALSE WHERE id = ...).
--
--   2) Faz o mesmo para o leitor: se o leitor_id enviado no registro
--      não existir na tabela leitor, cria automaticamente um leitor
--      com esse mesmo id, nome placeholder e pendente = TRUE.
--
--   3) Calcula o status alternando entre entrada/saída, olhando o
--      último registro salvo para o MESMO uid no MESMO leitor:
--        - Se não existe leitura anterior nesse leitor -> status = TRUE
--          (iniciou o período / entrada)
--        - Se a última leitura foi TRUE (entrada) -> nova = FALSE (saída)
--        - Se a última leitura foi FALSE (saída)   -> nova = TRUE (entrada)
--
--      Qualquer valor de status enviado pela aplicação na inserção é
--      sobrescrito por esse cálculo, garantindo consistência mesmo se
--      o app não controlar esse estado.
-- ---------------------------------------------------------------------
DELIMITER $$

CREATE TRIGGER trg_registros_before_insert
BEFORE INSERT ON registros
FOR EACH ROW
BEGIN
    DECLARE v_funcionario_id INT DEFAULT NULL;
    DECLARE v_leitor_existe  INT DEFAULT NULL;
    DECLARE v_ultimo_status  BOOLEAN DEFAULT NULL;

    -- Busca o funcionário correspondente ao UID lido
    SELECT id INTO v_funcionario_id
    FROM funcionario
    WHERE uid = NEW.uid
    LIMIT 1;

    -- Se não encontrou, cria um funcionário pendente automaticamente
    IF v_funcionario_id IS NULL THEN
        INSERT INTO funcionario (nome, uid, pendente)
        VALUES (CONCAT('Pendente - ', NEW.uid), NEW.uid, TRUE);

        SET v_funcionario_id = LAST_INSERT_ID();
    END IF;

    SET NEW.funcionario_id = v_funcionario_id;

    -- Verifica se o leitor informado existe
    SELECT id INTO v_leitor_existe
    FROM leitor
    WHERE id = NEW.leitor_id
    LIMIT 1;

    -- Se não existe, cria o leitor pendente automaticamente com o
    -- mesmo id enviado pelo dispositivo (idLeitor)
    IF v_leitor_existe IS NULL THEN
        INSERT INTO leitor (id, nome, pendente)
        VALUES (NEW.leitor_id, CONCAT('Leitor ', NEW.leitor_id, ' (pendente)'), TRUE);
    END IF;

    -- Busca o último status registrado para esse UID neste leitor
    SELECT status INTO v_ultimo_status
    FROM registros
    WHERE uid = NEW.uid
      AND leitor_id = NEW.leitor_id
    ORDER BY timestamp DESC, id DESC
    LIMIT 1;

    IF v_ultimo_status IS NULL THEN
        SET NEW.status = TRUE;             -- primeira leitura nesse leitor = entrada
    ELSE
        SET NEW.status = NOT v_ultimo_status; -- alterna entrada/saída
    END IF;
END$$

DELIMITER ;

-- ---------------------------------------------------------------------
-- Dados de exemplo (opcional) - remova ou ajuste conforme necessário
-- ---------------------------------------------------------------------
-- INSERT INTO leitor (id, nome) VALUES (1, 'Entrada Principal');
-- INSERT INTO funcionario (nome, uid) VALUES ('João Silva', '04 A1 B2 3C');

-- Exemplo de inserção (não é preciso informar funcionario_id nem status,
-- o trigger cuida disso):
-- INSERT INTO registros (uid, leitor_id) VALUES ('04 A1 B2 3C', 1);