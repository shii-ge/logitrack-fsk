from flask import Flask, render_template, redirect, url_for, flash, request
from datetime import datetime
import pymysql
from config import DB_CONFIG

app = Flask(__name__)
app.secret_key = "troque-esta-chave-em-producao"


def get_connection():
    """Abre uma nova conexão com o banco MySQL (controle_acesso)."""
    return pymysql.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )

# ---------------------------------------------------------------------------
# Página inicial: "Em progresso" -> para cada leitor, funcionários cujo
# último registro (uid + leitor) tem status = TRUE (entrada ainda aberta)
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.nome AS funcionario, l.nome AS posto, r.timestamp AS desde
                FROM registros r
                INNER JOIN (
                    SELECT uid, leitor_id, MAX(id) AS ultimo_id
                    FROM registros
                    GROUP BY uid, leitor_id
                ) u ON u.uid = r.uid AND u.leitor_id = r.leitor_id AND u.ultimo_id = r.id
                LEFT JOIN funcionario f ON f.id = r.funcionario_id
                LEFT JOIN leitor l ON l.id = r.leitor_id
                WHERE r.status = TRUE
                ORDER BY l.nome, r.timestamp
                """
            )
            abertos = cursor.fetchall()
    finally:
        conn.close()

    # Agrupa por posto (leitor) -> [{"nome":..., "desde": "HH:MM"}]
    postos = {}
    for r in abertos:
        posto = r["posto"] or "Leitor sem nome"
        desde = r["desde"]
        desde_fmt = desde.strftime("%H:%M") if isinstance(desde, datetime) else str(desde)
        nome = r["funcionario"] or "Desconhecido"
        postos.setdefault(posto, []).append({"nome": nome, "desde": desde_fmt})

    return render_template("index.html", postos=postos)


# ---------------------------------------------------------------------------
# Operadores: lista a tabela funcionario (inclui os criados automaticamente
# pelo trigger como "pendente" quando um uid desconhecido é lido)
# ---------------------------------------------------------------------------
@app.route("/operadores")
def operadores():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, nome, uid, pendente FROM funcionario ORDER BY pendente DESC, nome"
            )
            funcionarios = cursor.fetchall()
    finally:
        conn.close()

    return render_template("operadores.html", funcionarios=funcionarios)


@app.route("/operadores/<int:funcionario_id>")
def perfil_funcionario(funcionario_id):
    """Perfil do funcionário: mostra um gráfico com os tempos entre pares
    de ENTRADA (status=1) e SAÍDA (status=0) encontrados na tabela registros.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, nome, uid FROM funcionario WHERE id = %s", (funcionario_id,))
            funcionario = cursor.fetchone()
            if not funcionario:
                flash("Funcionário não encontrado.", "info")
                return redirect(url_for("operadores"))

            cursor.execute(
                """
                SELECT r.timestamp, r.status
                FROM registros r
                WHERE r.funcionario_id = %s
                ORDER BY r.timestamp ASC, r.id ASC
                """,
                (funcionario_id,),
            )
            registros = cursor.fetchall()
    finally:
        conn.close()

    # Monta sessões: emparelha um status=1 (entrada) com o próximo status=0 (saída)
    from datetime import timedelta

    sessions = []
    start = None
    for r in registros:
        ts = r.get('timestamp')
        status = bool(r.get('status'))
        if status and start is None:
            start = ts
        elif (not status) and start is not None:
            # Encontrou saída para a entrada anterior
            delta = ts - start
            seconds = delta.total_seconds() if hasattr(delta, 'total_seconds') else 0
            hours = seconds / 3600.0
            sessions.append({
                'start': start,
                'end': ts,
                'seconds': seconds,
                'hours': hours,
            })
            start = None
        # Ignora outros padrões (saídas sem entrada, entradas consecutivas sem saída)

    labels = [s['start'].strftime('%d/%m %H:%M') for s in sessions]
    values = [round(s['hours'], 3) for s in sessions]

    return render_template('perfil.html', funcionario=funcionario, sessions=sessions, labels=labels, values=values)



@app.route("/operadores/<int:funcionario_id>/editar", methods=["POST"])
def editar_funcionario(funcionario_id):
    """Botão verde (lápis): salva as alterações feitas no modal de edição.
    Editar um cadastro também o tira do estado 'pendente'."""
    novo_nome = request.form.get("nome", "").strip()
    novo_uid = request.form.get("uid", "").strip()

    if not novo_nome or not novo_uid:
        flash("Nome e UID são obrigatórios.", "info")
        return redirect(url_for("operadores"))

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE funcionario SET nome = %s, uid = %s, pendente = FALSE WHERE id = %s",
                (novo_nome, novo_uid, funcionario_id),
            )
        flash("Funcionário atualizado.", "success")
    finally:
        conn.close()
    return redirect(url_for("operadores"))


@app.route("/operadores/<int:funcionario_id>/excluir", methods=["POST"])
def excluir_funcionario(funcionario_id):
    """Botão vermelho: remove o funcionário (registros ficam com funcionario_id = NULL)."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM funcionario WHERE id = %s", (funcionario_id,))
        flash("Funcionário excluído.", "info")
    finally:
        conn.close()
    return redirect(url_for("operadores"))


# ---------------------------------------------------------------------------
# Leitores: lista a tabela leitor (inclui os criados automaticamente pelo
# trigger como "pendente" quando um leitor_id desconhecido envia leitura)
# ---------------------------------------------------------------------------
@app.route("/leitores")
def leitores():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, nome, pendente FROM leitor ORDER BY pendente DESC, id"
            )
            leitores = cursor.fetchall()
    finally:
        conn.close()

    return render_template("leitores.html", leitores=leitores)


@app.route("/leitores/<int:leitor_id>/editar", methods=["POST"])
def editar_leitor(leitor_id):
    """Botão verde (lápis): salva as alterações feitas no modal de edição."""
    novo_nome = request.form.get("nome", "").strip()

    if not novo_nome:
        flash("Nome é obrigatório.", "info")
        return redirect(url_for("leitores"))

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE leitor SET nome = %s, pendente = FALSE WHERE id = %s",
                (novo_nome, leitor_id),
            )
        flash("Leitor atualizado.", "success")
    finally:
        conn.close()
    return redirect(url_for("leitores"))


@app.route("/leitores/<int:leitor_id>/excluir", methods=["POST"])
def excluir_leitor(leitor_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM leitor WHERE id = %s", (leitor_id,))
        flash("Leitor excluído.", "info")
    finally:
        conn.close()
    return redirect(url_for("leitores"))


# ---------------------------------------------------------------------------
# Registros: histórico completo da tabela registros, com nomes de
# funcionário e leitor já resolvidos via JOIN
# ---------------------------------------------------------------------------
@app.route("/registros")
def registros():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.id, r.uid, r.timestamp, r.status,
                       f.nome AS funcionario, f.pendente AS funcionario_pendente,
                       l.nome AS leitor
                FROM registros r
                LEFT JOIN funcionario f ON f.id = r.funcionario_id
                LEFT JOIN leitor l ON l.id = r.leitor_id
                ORDER BY r.timestamp DESC, r.id DESC
                LIMIT 200
                """
            )
            historico = cursor.fetchall()
    finally:
        conn.close()

    return render_template("registros.html", historico=historico)


if __name__ == "__main__":
    app.run(debug=True)
