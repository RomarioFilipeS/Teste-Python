HEAD
# Biblioteca — Catálogo e Empréstimos

Projeto completo: back-end em **Python (Flask + SQLite)** e front-end em
**HTML/CSS/JavaScript puro**, servidos juntos pelo Flask.

## Como rodar

```bash
cd biblioteca
pip install -r requirements.txt
python app.py
```

Acesse **http://localhost:5000** no navegador. O arquivo `biblioteca.db`
(SQLite) é criado automaticamente na primeira execução, já com alguns
livros de exemplo.

## Estrutura

```
biblioteca/
├── app.py              # API Flask + criação do banco SQLite
├── requirements.txt
├── biblioteca.db        # criado automaticamente ao rodar
└── static/
    ├── index.html
    ├── style.css
    └── script.js
```

## Login

O sistema agora exige login para usar o catálogo:

- **O primeiro usuário cadastrado se torna administrador automaticamente.**
  Os próximos cadastros entram como "leitor".
- Senhas são armazenadas com hash (nunca em texto puro), usando `werkzeug.security`.
- A sessão é mantida por cookie (`flask.session`) — não há necessidade de
  enviar token manualmente no front.
- Apenas administradores veem a aba **"Acessos"**, com o histórico de quem
  entrou no site (nome, e-mail, data/hora e IP).

Para promover alguém a admin manualmente (ex: depois de já ter um admin),
pode rodar no terminal:
```bash
python -c "
import sqlite3
conn = sqlite3.connect('biblioteca.db')
conn.execute(\"UPDATE usuarios SET tipo='admin' WHERE email=?\", ('email@da/pessoa.com',))
conn.commit()
"
```

## Modelo de dados

**usuarios**: id, nome, email, senha_hash, tipo (`admin`/`leitor`), criado_em

**acessos**: id, usuario_id, data_hora, ip — um registro por login

**livros**: id, titulo, autor, ano, isbn, categoria, quantidade_total, quantidade_disponivel

**emprestimos**: id, livro_id, usuario_id, nome_leitor, data_emprestimo, data_prevista, data_devolucao, status

## Endpoints da API

| Método | Rota                                   | Descrição                              | Acesso        |
|--------|-----------------------------------------|------------------------------------------|---------------|
| POST   | `/api/auth/registrar`                  | Cria conta (e já faz login)             | público       |
| POST   | `/api/auth/login`                      | Login                                    | público       |
| POST   | `/api/auth/logout`                     | Logout                                   | logado        |
| GET    | `/api/auth/me`                         | Dados do usuário logado                  | logado        |
| GET    | `/api/acessos`                         | Histórico de logins                      | admin         |
| GET    | `/api/livros?q=termo`                  | Lista livros (busca opcional)           | logado        |
| GET    | `/api/livros/<id>`                     | Detalhe de um livro                      | logado        |
| POST   | `/api/livros`                          | Cadastra um livro                        | logado        |
| PUT    | `/api/livros/<id>`                     | Atualiza um livro                        | logado        |
| DELETE | `/api/livros/<id>`                     | Remove um livro                          | logado        |
| GET    | `/api/emprestimos?status=emprestado`   | Lista empréstimos (filtro opcional)      | logado        |
| POST   | `/api/emprestimos`                     | Registra um empréstimo no nome do logado | logado        |
| POST   | `/api/emprestimos/<id>/devolver`       | Marca devolução                          | logado        |

## Observações

- Se quiser usar o front-end separado da API (outra porta/domínio), o CORS
  já está liberado com `supports_credentials=True` em `app.py` — basta
  apontar `API_BASE` em `script.js` e usar `credentials: "include"` nas
  chamadas `fetch`.
- Troque o valor de `app.secret_key` em `app.py` antes de usar em produção.
- Não é possível excluir um livro que tenha exemplares emprestados.
=======
# Teste-Python
1f7023cdd3b10203250620f4f5789bb02ea9e4e9
