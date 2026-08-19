import os

# Credenciais de acesso ao MySQL.
# Prefira definir estes valores como variáveis de ambiente em produção.
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "root"),
    "database": os.environ.get("DB_NAME", "controle_acesso"),
}
