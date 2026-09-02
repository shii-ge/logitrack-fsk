import re
import time
import logging
import serial
import mysql.connector
from mysql.connector import Error

# --- CONFIGURAÇÕES ---
# Ajuste para a sua porta (Ex: 'COM3' no Windows ou '/dev/ttyUSB0' no Linux)
PORTA_SERIAL = 'COM3'
BAUD_RATE = 115200

# Configurações do MySQL / MariaDB
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',  # Sua senha do banco de dados
    'database': 'controle_acesso'
}

# Tempo de espera antes de tentar reconectar (serial ou banco), em segundos
RETRY_DELAY = 5

# --- LOGGING ---
# Grava em arquivo (essencial para rodar em background, sem console visível)
# e também mostra no console, útil durante desenvolvimento/testes.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("monitor_serial.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# Expressão regular para validar o formato LEITURA;<idLeitor>;<uidHex>
padrao_leitura = re.compile(r"^LEITURA;(\d+);([0-9A-Fa-f]+)$")


def conectar_banco():
    """Tenta conectar ao MySQL. Retorna a conexão ou None se falhar."""
    try:
        conexao = mysql.connector.connect(**DB_CONFIG)
        log.info("Conectado ao MySQL.")
        return conexao
    except Error as e:
        log.error(f"Erro ao conectar ao MySQL: {e}")
        return None


def conectar_serial():
    """Tenta abrir a porta serial em loop até conseguir (ou até ser interrompido)."""
    while True:
        try:
            ser = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=1)
            log.info(f"Conectado à porta {PORTA_SERIAL} a {BAUD_RATE} baud.")
            return ser
        except Exception as e:
            log.warning(f"Falha ao abrir porta serial {PORTA_SERIAL}: {e}. "
                        f"Tentando novamente em {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)


def inserir_registro(conexao, id_leitor, uid_hex):
    """Insere a leitura no banco de dados. A Trigger faz todo o trabalho pesado."""
    try:
        cursor = conexao.cursor()

        # A trigger calcula automaticamente o status, cria funcionario e leitor se não existirem
        sql = "INSERT INTO registros (uid, leitor_id) VALUES (%s, %s)"
        cursor.execute(sql, (uid_hex, id_leitor))

        conexao.commit()
        cursor.close()

        log.info(f"Registrado com sucesso: Leitor ID = {id_leitor} | UID = {uid_hex}")
        return True
    except Error as e:
        log.error(f"Erro ao inserir registro no banco: {e}")
        try:
            conexao.rollback()
        except Error:
            pass
        return False


def main():
    log.info("--- Inicializando Monitor da Porta Serial ---")

    conexao_db = conectar_banco()  # se falhar aqui, seguimos mesmo assim: tentaremos de novo a cada leitura
    ser = conectar_serial()

    try:
        while True:
            try:
                # ser.readline() já respeita o timeout=1 definido acima:
                # bloqueia até 1s esperando dado, ou retorna vazio. Não é
                # necessário checar ser.in_waiting antes (evita busy-wait).
                linha = ser.readline().decode('utf-8', errors='ignore').strip()

                if not linha:
                    continue

                match = padrao_leitura.match(linha)
                if match:
                    id_leitor = int(match.group(1))
                    uid_hex = match.group(2).upper()

                    log.info(f"String recebida: {linha}")

                    # Garante que a conexão com o banco continue viva;
                    # se não conseguir reconectar, a leitura é registrada como perdida
                    # (mas o script continua rodando, sem cair).
                    if conexao_db is None or not conexao_db.is_connected():
                        conexao_db = conectar_banco()

                    if conexao_db:
                        inserir_registro(conexao_db, id_leitor, uid_hex)
                    else:
                        log.warning(f"Leitura perdida (banco indisponível): {linha}")
                else:
                    # Mensagens de inicialização do Arduino ou eventuais ruídos
                    log.info(f"Serial Log: {linha}")

            except serial.SerialException as e:
                # Cabo USB desconectado, porta sumiu, etc. Em vez de derrubar
                # o script inteiro, fecha a porta e tenta reabrir.
                log.warning(f"Erro na porta serial: {e}. Tentando reconectar...")
                try:
                    ser.close()
                except Exception:
                    pass
                ser = conectar_serial()

    except KeyboardInterrupt:
        log.info("Encerramento solicitado pelo usuário.")
    finally:
        try:
            if ser and ser.is_open:
                ser.close()
        except Exception:
            pass
        try:
            if conexao_db and conexao_db.is_connected():
                conexao_db.close()
        except Exception:
            pass
        log.info("Conexões encerradas.")


if __name__ == "__main__":
    main()
