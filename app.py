"""
API da Biblioteca
------------------
Backend em Flask + SQLite. Cria o banco de dados automaticamente
na primeira execução (arquivo biblioteca.db) e serve também o
front-end estático (pasta /static).

Inclui sistema de login por sessão:
- O primeiro usuário cadastrado se torna administrador automaticamente.
- Toda vez que alguém faz login, isso é registrado na tabela "acessos".
- Apenas administradores podem ver o histórico de acessos.

Como rodar:
    pip install -r requirements.txt
    python app.py

A aplicação fica disponível em http://localhost:5000
"""

import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from functools import wraps

from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "biblioteca.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")
CORS(app, supports_credentials=True)


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS livros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            autor TEXT NOT NULL,
            ano INTEGER,
            isbn TEXT,
            categoria TEXT NOT NULL DEFAULT 'Geral',
            quantidade_total INTEGER NOT NULL DEFAULT 1,
            quantidade_disponivel INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'leitor',
            criado_em TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS acessos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            data_hora TEXT NOT NULL,
            ip TEXT,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        );

        CREATE TABLE IF NOT EXISTS emprestimos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            livro_id INTEGER NOT NULL,
            usuario_id INTEGER,
            nome_leitor TEXT NOT NULL,
            data_emprestimo TEXT NOT NULL,
            data_prevista TEXT NOT NULL,
            data_devolucao TEXT,
            status TEXT NOT NULL DEFAULT 'emprestado',
            FOREIGN KEY (livro_id) REFERENCES livros (id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        );
        """
    )
    conn.commit()

    # Migração leve para bancos criados antes do sistema de login existir
    try:
        conn.execute("ALTER TABLE emprestimos ADD COLUMN usuario_id INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # coluna já existe

    # Semeia alguns livros de exemplo apenas se a tabela estiver vazia
    total = conn.execute("SELECT COUNT(*) AS n FROM livros").fetchone()["n"]
    if total == 0:
        exemplos = [
            ("Dom Casmurro", "Machado de Assis", 1899, "9788535910676", "Romance", 3),
            ("Grande Sertão: Veredas", "Guimarães Rosa", 1956, "9788501063702", "Romance", 2),
            ("A Hora da Estrela", "Clarice Lispector", 1977, "9788532508115", "Romance", 2),
            ("O Alienista", "Machado de Assis", 1882, "9788572327227", "Conto", 1),
            ("Capitães da Areia", "Jorge Amado", 1937, "9788535914735", "Romance", 2),
            ("Vidas Secas", "Graciliano Ramos", 1938, "9788520933523", "Romance", 1),
        ]
        conn.executemany(
            """INSERT INTO livros
               (titulo, autor, ano, isbn, categoria, quantidade_total, quantidade_disponivel)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [(t, a, ano, isbn, cat, q, q) for (t, a, ano, isbn, cat, q) in exemplos],
        )
        conn.commit()
    conn.close()


def numero_chamada(livro):
    """Gera um número de chamada (estilo catálogo) a partir da categoria e do autor."""
    base = abs(hash(livro["categoria"])) % 900 + 100  # 100-999
    sufixo = (livro["autor"].split()[-1][:3] if livro["autor"] else "GEN").upper()
    return f"{base}.{(livro['id'] * 7) % 90:02d} {sufixo}"


def livro_para_json(row):
    livro = dict(row)
    livro["numero_chamada"] = numero_chamada(livro)
    return livro


def usuario_para_json(row):
    return {"id": row["id"], "nome": row["nome"], "email": row["email"], "tipo": row["tipo"]}


# ---------------------------------------------------------------------------
# Autenticação - utilidades
# ---------------------------------------------------------------------------

def usuario_atual():
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return None
    conn = get_conn()
    row = conn.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    conn.close()
    return row


def login_required(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        if not usuario_atual():
            return jsonify({"erro": "É necessário estar logado"}), 401
        return f(*args, **kwargs)
    return decorada


def admin_required(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        usuario = usuario_atual()
        if not usuario:
            return jsonify({"erro": "É necessário estar logado"}), 401
        if usuario["tipo"] != "admin":
            return jsonify({"erro": "Apenas administradores podem acessar isso"}), 403
        return f(*args, **kwargs)
    return decorada


# ---------------------------------------------------------------------------
# Rotas - páginas estáticas (front-end)
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return send_from_directory(STATIC_DIR, "index.html")


# ---------------------------------------------------------------------------
# Rotas - Autenticação
# ---------------------------------------------------------------------------

@app.route("/api/auth/registrar", methods=["POST"])
def registrar():
    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""

    if not nome or not email or not senha:
        return jsonify({"erro": "Nome, e-mail e senha são obrigatórios"}), 400
    if "@" not in email or "." not in email:
        return jsonify({"erro": "Informe um e-mail válido"}), 400
    if len(senha) < 6:
        return jsonify({"erro": "A senha precisa ter ao menos 6 caracteres"}), 400

    conn = get_conn()
    existente = conn.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()
    if existente:
        conn.close()
        return jsonify({"erro": "Já existe uma conta com esse e-mail"}), 409

    total_usuarios = conn.execute("SELECT COUNT(*) AS n FROM usuarios").fetchone()["n"]
    tipo = "admin" if total_usuarios == 0 else "leitor"

    cur = conn.execute(
        "INSERT INTO usuarios (nome, email, senha_hash, tipo, criado_em) VALUES (?, ?, ?, ?, ?)",
        (nome, email, generate_password_hash(senha), tipo, datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    conn.commit()
    novo = conn.execute("SELECT * FROM usuarios WHERE id = ?", (cur.lastrowid,)).fetchone()

    # já loga automaticamente após o cadastro e registra o acesso
    session["usuario_id"] = novo["id"]
    conn.execute(
        "INSERT INTO acessos (usuario_id, data_hora, ip) VALUES (?, ?, ?)",
        (novo["id"], datetime.now(timezone.utc).isoformat(timespec="seconds"), request.remote_addr),
    )
    conn.commit()
    conn.close()
    return jsonify(usuario_para_json(novo)), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    dados = request.get_json(silent=True) or {}
    email = (dados.get("email") or "").strip().lower()
    senha = dados.get("senha") or ""

    conn = get_conn()
    usuario = conn.execute("SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()
    if not usuario or not check_password_hash(usuario["senha_hash"], senha):
        conn.close()
        return jsonify({"erro": "E-mail ou senha incorretos"}), 401

    session["usuario_id"] = usuario["id"]
    conn.execute(
        "INSERT INTO acessos (usuario_id, data_hora, ip) VALUES (?, ?, ?)",
        (usuario["id"], datetime.now(timezone.utc).isoformat(timespec="seconds"), request.remote_addr),
    )
    conn.commit()
    conn.close()
    return jsonify(usuario_para_json(usuario))


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me", methods=["GET"])
def me():
    usuario = usuario_atual()
    if not usuario:
        return jsonify({"erro": "Não autenticado"}), 401
    return jsonify(usuario_para_json(usuario))


@app.route("/api/acessos", methods=["GET"])
@admin_required
def listar_acessos():
    conn = get_conn()
    rows = conn.execute(
        """SELECT a.id, a.data_hora, a.ip, u.nome, u.email, u.tipo
           FROM acessos a JOIN usuarios u ON u.id = a.usuario_id
           ORDER BY a.data_hora DESC LIMIT 200"""
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# Rotas - API de Livros
# ---------------------------------------------------------------------------

@app.route("/api/livros", methods=["GET"])
@login_required
def listar_livros():
    busca = request.args.get("q", "").strip().lower()
    conn = get_conn()
    if busca:
        like = f"%{busca}%"
        rows = conn.execute(
            """SELECT * FROM livros
               WHERE lower(titulo) LIKE ? OR lower(autor) LIKE ? OR lower(categoria) LIKE ?
               ORDER BY titulo""",
            (like, like, like),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM livros ORDER BY titulo").fetchall()
    conn.close()
    return jsonify([livro_para_json(r) for r in rows])


@app.route("/api/livros/<int:livro_id>", methods=["GET"])
@login_required
def obter_livro(livro_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM livros WHERE id = ?", (livro_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"erro": "Livro não encontrado"}), 404
    return jsonify(livro_para_json(row))


@app.route("/api/livros", methods=["POST"])
@login_required
def criar_livro():
    dados = request.get_json(silent=True) or {}
    titulo = (dados.get("titulo") or "").strip()
    autor = (dados.get("autor") or "").strip()
    if not titulo or not autor:
        return jsonify({"erro": "Título e autor são obrigatórios"}), 400

    quantidade = int(dados.get("quantidade_total") or 1)
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO livros (titulo, autor, ano, isbn, categoria, quantidade_total, quantidade_disponivel)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            titulo,
            autor,
            dados.get("ano"),
            dados.get("isbn", ""),
            dados.get("categoria") or "Geral",
            quantidade,
            quantidade,
        ),
    )
    conn.commit()
    novo = conn.execute("SELECT * FROM livros WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(livro_para_json(novo)), 201


@app.route("/api/livros/<int:livro_id>", methods=["PUT"])
@login_required
def atualizar_livro(livro_id):
    dados = request.get_json(silent=True) or {}
    conn = get_conn()
    atual = conn.execute("SELECT * FROM livros WHERE id = ?", (livro_id,)).fetchone()
    if not atual:
        conn.close()
        return jsonify({"erro": "Livro não encontrado"}), 404

    campos = {
        "titulo": dados.get("titulo", atual["titulo"]),
        "autor": dados.get("autor", atual["autor"]),
        "ano": dados.get("ano", atual["ano"]),
        "isbn": dados.get("isbn", atual["isbn"]),
        "categoria": dados.get("categoria", atual["categoria"]),
        "quantidade_total": dados.get("quantidade_total", atual["quantidade_total"]),
        "quantidade_disponivel": dados.get("quantidade_disponivel", atual["quantidade_disponivel"]),
    }
    conn.execute(
        """UPDATE livros SET titulo=?, autor=?, ano=?, isbn=?, categoria=?,
           quantidade_total=?, quantidade_disponivel=? WHERE id=?""",
        (*campos.values(), livro_id),
    )
    conn.commit()
    atualizado = conn.execute("SELECT * FROM livros WHERE id = ?", (livro_id,)).fetchone()
    conn.close()
    return jsonify(livro_para_json(atualizado))


@app.route("/api/livros/<int:livro_id>", methods=["DELETE"])
@login_required
def excluir_livro(livro_id):
    conn = get_conn()
    emprestado = conn.execute(
        "SELECT COUNT(*) AS n FROM emprestimos WHERE livro_id=? AND status='emprestado'",
        (livro_id,),
    ).fetchone()["n"]
    if emprestado > 0:
        conn.close()
        return jsonify({"erro": "Não é possível excluir: há exemplares emprestados"}), 400
    conn.execute("DELETE FROM livros WHERE id = ?", (livro_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Rotas - API de Empréstimos
# ---------------------------------------------------------------------------

@app.route("/api/emprestimos", methods=["GET"])
@login_required
def listar_emprestimos():
    status = request.args.get("status")  # 'emprestado' | 'devolvido' | None (todos)
    conn = get_conn()
    sql = """SELECT e.*, l.titulo AS livro_titulo, l.autor AS livro_autor
              FROM emprestimos e JOIN livros l ON l.id = e.livro_id"""
    params = ()
    if status:
        sql += " WHERE e.status = ?"
        params = (status,)
    sql += " ORDER BY e.data_emprestimo DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/emprestimos", methods=["POST"])
@login_required
def criar_emprestimo():
    dados = request.get_json(silent=True) or {}
    livro_id = dados.get("livro_id")
    dias = int(dados.get("dias") or 14)
    usuario = usuario_atual()

    if not livro_id:
        return jsonify({"erro": "livro_id é obrigatório"}), 400

    conn = get_conn()
    livro = conn.execute("SELECT * FROM livros WHERE id = ?", (livro_id,)).fetchone()
    if not livro:
        conn.close()
        return jsonify({"erro": "Livro não encontrado"}), 404
    if livro["quantidade_disponivel"] <= 0:
        conn.close()
        return jsonify({"erro": "Não há exemplares disponíveis para empréstimo"}), 400

    hoje = date.today()
    prevista = hoje + timedelta(days=dias)

    cur = conn.execute(
        """INSERT INTO emprestimos (livro_id, usuario_id, nome_leitor, data_emprestimo, data_prevista, status)
           VALUES (?, ?, ?, ?, ?, 'emprestado')""",
        (livro_id, usuario["id"], usuario["nome"], hoje.isoformat(), prevista.isoformat()),
    )
    conn.execute(
        "UPDATE livros SET quantidade_disponivel = quantidade_disponivel - 1 WHERE id = ?",
        (livro_id,),
    )
    conn.commit()
    novo = conn.execute(
        """SELECT e.*, l.titulo AS livro_titulo, l.autor AS livro_autor
           FROM emprestimos e JOIN livros l ON l.id = e.livro_id WHERE e.id = ?""",
        (cur.lastrowid,),
    ).fetchone()
    conn.close()
    return jsonify(dict(novo)), 201


@app.route("/api/emprestimos/<int:emprestimo_id>/devolver", methods=["POST"])
@login_required
def devolver_emprestimo(emprestimo_id):
    conn = get_conn()
    emp = conn.execute("SELECT * FROM emprestimos WHERE id = ?", (emprestimo_id,)).fetchone()
    if not emp:
        conn.close()
        return jsonify({"erro": "Empréstimo não encontrado"}), 404
    if emp["status"] == "devolvido":
        conn.close()
        return jsonify({"erro": "Este empréstimo já foi devolvido"}), 400

    conn.execute(
        "UPDATE emprestimos SET status='devolvido', data_devolucao=? WHERE id=?",
        (date.today().isoformat(), emprestimo_id),
    )
    conn.execute(
        "UPDATE livros SET quantidade_disponivel = quantidade_disponivel + 1 WHERE id = ?",
        (emp["livro_id"],),
    )
    conn.commit()
    atualizado = conn.execute(
        """SELECT e.*, l.titulo AS livro_titulo, l.autor AS livro_autor
           FROM emprestimos e JOIN livros l ON l.id = e.livro_id WHERE e.id = ?""",
        (emprestimo_id,),
    ).fetchone()
    conn.close()
    return jsonify(dict(atualizado))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
