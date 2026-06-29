// ---------------------------------------------------------------------------
// Configuração
// ---------------------------------------------------------------------------
const API_BASE = ""; // mesma origem (Flask serve o front e a API juntos)

// ---------------------------------------------------------------------------
// Elementos - autenticação
// ---------------------------------------------------------------------------
const telaAuth = document.getElementById("tela-auth");
const appEl = document.getElementById("app");
const alternadorBotoes = document.querySelectorAll(".alternador-auth .botao-aba");
const formLogin = document.getElementById("form-login");
const formRegistro = document.getElementById("form-registro");
const textoUsuarioLogado = document.getElementById("texto-usuario-logado");
const botaoSair = document.getElementById("botao-sair");
const abasAdmin = document.querySelectorAll(".apenas-admin");

let usuarioLogado = null;

// ---------------------------------------------------------------------------
// Elementos - aplicação
// ---------------------------------------------------------------------------
const botoesAba = document.querySelectorAll(".gaveta-nav .botao-aba");
const vistaCatalogo = document.getElementById("vista-catalogo");
const vistaEmprestimos = document.getElementById("vista-emprestimos");
const vistaAcessos = document.getElementById("vista-acessos");

const campoBusca = document.getElementById("campo-busca");
const grade = document.getElementById("grade-livros");
const catalogoVazio = document.getElementById("catalogo-vazio");

const listaEmprestimos = document.getElementById("lista-emprestimos");
const emprestimosVazio = document.getElementById("emprestimos-vazio");

const listaAcessos = document.getElementById("lista-acessos");
const acessosVazio = document.getElementById("acessos-vazio");

const modalLivro = document.getElementById("modal-livro");
const formLivro = document.getElementById("form-livro");
const botaoNovoLivro = document.getElementById("botao-novo-livro");
const botaoCancelarLivro = document.getElementById("botao-cancelar-livro");

const modalEmprestimo = document.getElementById("modal-emprestimo");
const formEmprestimo = document.getElementById("form-emprestimo");
const resumoLivroModal = document.getElementById("resumo-livro-modal");
const resumoLeitorModal = document.getElementById("resumo-leitor-modal");
const botaoCancelarEmprestimo = document.getElementById("botao-cancelar-emprestimo");

const avisoEl = document.getElementById("aviso");

let livroSelecionadoId = null;
let timerBusca = null;

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------

function mostrarAviso(mensagem, tipo = "ok") {
  avisoEl.textContent = mensagem;
  avisoEl.classList.remove("oculto", "erro");
  if (tipo === "erro") avisoEl.classList.add("erro");
  clearTimeout(avisoEl._timer);
  avisoEl._timer = setTimeout(() => avisoEl.classList.add("oculto"), 3200);
}

function formatarData(iso) {
  if (!iso) return "—";
  const data = iso.includes("T") ? iso : iso + "T00:00:00";
  const d = new Date(data);
  return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: iso.includes("T") ? "short" : undefined });
}

function escapeHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto ?? "";
  return div.innerHTML;
}

async function chamarApi(caminho, opcoes = {}) {
  const resposta = await fetch(API_BASE + caminho, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...opcoes,
  });
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) {
    throw new Error(dados.erro || "Erro inesperado na requisição");
  }
  return dados;
}

// ---------------------------------------------------------------------------
// Autenticação
// ---------------------------------------------------------------------------

alternadorBotoes.forEach((botao) => {
  botao.addEventListener("click", () => {
    alternadorBotoes.forEach((b) => b.classList.remove("ativo"));
    botao.classList.add("ativo");
    const mostrarRegistro = botao.dataset.form === "criar";
    formLogin.classList.toggle("oculto", mostrarRegistro);
    formRegistro.classList.toggle("oculto", !mostrarRegistro);
  });
});

formLogin.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const dados = new FormData(formLogin);
  try {
    const usuario = await chamarApi("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: dados.get("email"), senha: dados.get("senha") }),
    });
    aposLogin(usuario);
  } catch (erro) {
    mostrarAviso(erro.message, "erro");
  }
});

formRegistro.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const dados = new FormData(formRegistro);
  try {
    const usuario = await chamarApi("/api/auth/registrar", {
      method: "POST",
      body: JSON.stringify({
        nome: dados.get("nome"),
        email: dados.get("email"),
        senha: dados.get("senha"),
      }),
    });
    mostrarAviso(usuario.tipo === "admin" ? "Conta criada como administrador." : "Conta criada com sucesso.");
    aposLogin(usuario);
  } catch (erro) {
    mostrarAviso(erro.message, "erro");
  }
});

function aposLogin(usuario) {
  usuarioLogado = usuario;
  textoUsuarioLogado.textContent = `Olá, ${usuario.nome}${usuario.tipo === "admin" ? " (admin)" : ""}`;
  abasAdmin.forEach((el) => el.classList.toggle("oculto", usuario.tipo !== "admin"));
  telaAuth.classList.add("oculto");
  appEl.classList.remove("oculto");
  formLogin.reset();
  formRegistro.reset();
  carregarLivros();
}

botaoSair.addEventListener("click", async () => {
  try {
    await chamarApi("/api/auth/logout", { method: "POST" });
  } catch (erro) {
    // mesmo se falhar no servidor, limpamos a tela local
  }
  usuarioLogado = null;
  appEl.classList.add("oculto");
  telaAuth.classList.remove("oculto");
});

async function verificarSessao() {
  try {
    const usuario = await chamarApi("/api/auth/me");
    aposLogin(usuario);
  } catch {
    telaAuth.classList.remove("oculto");
    appEl.classList.add("oculto");
  }
}

// ---------------------------------------------------------------------------
// Navegação entre abas internas
// ---------------------------------------------------------------------------

botoesAba.forEach((botao) => {
  botao.addEventListener("click", () => {
    botoesAba.forEach((b) => b.classList.remove("ativo"));
    botao.classList.add("ativo");
    const vista = botao.dataset.vista;
    vistaCatalogo.classList.toggle("oculto", vista !== "catalogo");
    vistaEmprestimos.classList.toggle("oculto", vista !== "emprestimos");
    vistaAcessos.classList.toggle("oculto", vista !== "acessos");
    if (vista === "emprestimos") carregarEmprestimos();
    if (vista === "acessos") carregarAcessos();
  });
});

// ---------------------------------------------------------------------------
// Catálogo de livros
// ---------------------------------------------------------------------------

function cartaoLivro(livro) {
  const disponivel = livro.quantidade_disponivel > 0;
  const div = document.createElement("article");
  div.className = "ficha";
  div.innerHTML = `
    <span class="ficha-numero">${livro.numero_chamada}</span>
    <h3 class="ficha-titulo">${escapeHtml(livro.titulo)}</h3>
    <p class="ficha-autor">${escapeHtml(livro.autor)}${livro.ano ? " · " + livro.ano : ""}</p>
    <div class="ficha-meta">
      <span>${escapeHtml(livro.categoria || "Geral")}</span>
      ${livro.isbn ? `<span>ISBN ${escapeHtml(livro.isbn)}</span>` : ""}
    </div>
    <span class="ficha-disponibilidade ${disponivel ? "disponivel" : "indisponivel"}">
      ${livro.quantidade_disponivel}/${livro.quantidade_total} exemplar(es) disponível(is)
    </span>
    <div class="ficha-acoes">
      <button class="botao botao-primario" data-acao="emprestar" ${disponivel ? "" : "disabled"}>
        Emprestar
      </button>
      <button class="botao botao-perigo" data-acao="excluir">Excluir</button>
    </div>
  `;

  div.querySelector('[data-acao="emprestar"]').addEventListener("click", () => abrirModalEmprestimo(livro));
  div.querySelector('[data-acao="excluir"]').addEventListener("click", () => excluirLivro(livro));

  return div;
}

async function carregarLivros() {
  const termo = campoBusca.value.trim();
  try {
    const livros = await chamarApi(`/api/livros${termo ? `?q=${encodeURIComponent(termo)}` : ""}`);
    grade.innerHTML = "";
    catalogoVazio.classList.toggle("oculto", livros.length > 0);
    livros.forEach((livro) => grade.appendChild(cartaoLivro(livro)));
  } catch (erro) {
    mostrarAviso(erro.message, "erro");
  }
}

campoBusca.addEventListener("input", () => {
  clearTimeout(timerBusca);
  timerBusca = setTimeout(carregarLivros, 250);
});

async function excluirLivro(livro) {
  if (!confirm(`Remover "${livro.titulo}" do acervo?`)) return;
  try {
    await chamarApi(`/api/livros/${livro.id}`, { method: "DELETE" });
    mostrarAviso("Livro removido do acervo.");
    carregarLivros();
  } catch (erro) {
    mostrarAviso(erro.message, "erro");
  }
}

// ---------------------------------------------------------------------------
// Modal: novo livro
// ---------------------------------------------------------------------------

botaoNovoLivro.addEventListener("click", () => modalLivro.classList.remove("oculto"));
botaoCancelarLivro.addEventListener("click", () => fecharModalLivro());

function fecharModalLivro() {
  modalLivro.classList.add("oculto");
  formLivro.reset();
}

formLivro.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const dados = new FormData(formLivro);
  const corpo = {
    titulo: dados.get("titulo"),
    autor: dados.get("autor"),
    ano: dados.get("ano") ? Number(dados.get("ano")) : null,
    categoria: dados.get("categoria") || "Geral",
    isbn: dados.get("isbn") || "",
    quantidade_total: Number(dados.get("quantidade_total")) || 1,
  };
  try {
    await chamarApi("/api/livros", { method: "POST", body: JSON.stringify(corpo) });
    mostrarAviso("Ficha adicionada ao catálogo.");
    fecharModalLivro();
    carregarLivros();
  } catch (erro) {
    mostrarAviso(erro.message, "erro");
  }
});

// ---------------------------------------------------------------------------
// Modal: empréstimo
// ---------------------------------------------------------------------------

function abrirModalEmprestimo(livro) {
  livroSelecionadoId = livro.id;
  resumoLivroModal.textContent = `${livro.titulo} — ${livro.autor}`;
  resumoLeitorModal.textContent = `Será registrado em nome de: ${usuarioLogado.nome}`;
  modalEmprestimo.classList.remove("oculto");
}

botaoCancelarEmprestimo.addEventListener("click", () => fecharModalEmprestimo());

function fecharModalEmprestimo() {
  modalEmprestimo.classList.add("oculto");
  formEmprestimo.reset();
  livroSelecionadoId = null;
}

formEmprestimo.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const dados = new FormData(formEmprestimo);
  const corpo = {
    livro_id: livroSelecionadoId,
    dias: Number(dados.get("dias")) || 14,
  };
  try {
    await chamarApi("/api/emprestimos", { method: "POST", body: JSON.stringify(corpo) });
    mostrarAviso("Empréstimo registrado.");
    fecharModalEmprestimo();
    carregarLivros();
  } catch (erro) {
    mostrarAviso(erro.message, "erro");
  }
});

// ---------------------------------------------------------------------------
// Empréstimos
// ---------------------------------------------------------------------------

function linhaEmprestimo(emp) {
  const div = document.createElement("div");
  div.className = "linha-emprestimo";
  const devolvido = emp.status === "devolvido";
  div.innerHTML = `
    <div class="linha-emprestimo-info">
      <strong>${escapeHtml(emp.livro_titulo)}</strong>
      <span>Leitor(a): ${escapeHtml(emp.nome_leitor)}</span>
      <span>Emprestado em ${formatarData(emp.data_emprestimo)} · Previsto para ${formatarData(emp.data_prevista)}</span>
      ${devolvido ? `<span>Devolvido em ${formatarData(emp.data_devolucao)}</span>` : ""}
    </div>
    <span class="carimbo ${devolvido ? "devolvido" : "emprestado"}">
      ${devolvido ? "Devolvido" : "Emprestado"}
    </span>
    ${devolvido ? "" : `<button class="botao botao-primario" data-acao="devolver">Marcar devolução</button>`}
  `;
  if (!devolvido) {
    div.querySelector('[data-acao="devolver"]').addEventListener("click", () => devolverLivro(emp.id));
  }
  return div;
}

async function carregarEmprestimos() {
  try {
    const emprestimos = await chamarApi("/api/emprestimos");
    listaEmprestimos.innerHTML = "";
    emprestimosVazio.classList.toggle("oculto", emprestimos.length > 0);
    emprestimos.forEach((emp) => listaEmprestimos.appendChild(linhaEmprestimo(emp)));
  } catch (erro) {
    mostrarAviso(erro.message, "erro");
  }
}

async function devolverLivro(emprestimoId) {
  try {
    await chamarApi(`/api/emprestimos/${emprestimoId}/devolver`, { method: "POST" });
    mostrarAviso("Devolução registrada.");
    carregarEmprestimos();
  } catch (erro) {
    mostrarAviso(erro.message, "erro");
  }
}

// ---------------------------------------------------------------------------
// Acessos (admin) — quem entrou no site
// ---------------------------------------------------------------------------

function linhaAcesso(acesso) {
  const div = document.createElement("div");
  div.className = "linha-emprestimo";
  div.innerHTML = `
    <div class="linha-emprestimo-info">
      <strong>${escapeHtml(acesso.nome)}${acesso.tipo === "admin" ? " · admin" : ""}</strong>
      <span>${escapeHtml(acesso.email)}</span>
      <span>Entrou em ${formatarData(acesso.data_hora)} · IP ${escapeHtml(acesso.ip || "—")}</span>
    </div>
  `;
  return div;
}

async function carregarAcessos() {
  try {
    const acessos = await chamarApi("/api/acessos");
    listaAcessos.innerHTML = "";
    acessosVazio.classList.toggle("oculto", acessos.length > 0);
    acessos.forEach((a) => listaAcessos.appendChild(linhaAcesso(a)));
  } catch (erro) {
    mostrarAviso(erro.message, "erro");
  }
}

// ---------------------------------------------------------------------------
// Inicialização
// ---------------------------------------------------------------------------

verificarSessao();
