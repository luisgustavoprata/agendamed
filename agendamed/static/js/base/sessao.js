/* AgendaMed — estado da aplicação e sessão de quem está usando.
 *
 * `state` guarda o usuário e os filtros das telas; `session` entra, sai e restaura o
 * login; `toast` mostra avisos rápidos.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

const state = {
  user: null,
  doctors: null, // cache da lista de médicos
  agenda: { doctorId: null, date: null, selectedKey: null },
  appointments: { date: "", doctorId: "", status: "", offset: 0 },
  doctorsPage: { specialty: "", offset: 0 },
  patientsPage: { q: "", offset: 0 },
};

const PAGE_SIZE = 20;

const session = {
  async start() {
    if (!api.token) return renderLogin();
    try {
      state.user = await api.get("/auth/me");
      renderShell();
    } catch {
      api.token = null;
      renderLogin();
    }
  },

  async login(email, password) {
    const { access_token: token } = await api.post("/auth/login", {
      email,
      password,
    });
    api.token = token;
    state.user = await api.get("/auth/me");
    // Depois de entrar, sempre começa em "Agendar consulta".
    history.replaceState(
      null,
      "",
      `${location.pathname}${location.search}#/agendar`,
    );
    renderShell();
  },

  logout() {
    api.token = null;
    state.user = null;
    state.doctors = null;
    renderLogin();
  },

  expire() {
    if (!state.user) return;
    this.logout();
    toast("Sua sessão expirou. Entre novamente.", "error");
  },
};

function toast(message, tone = "success") {
  const el = h(
    "div",
    {
      class: `toast toast--${tone}`,
      role: tone === "error" ? "alert" : "status",
    },
    message,
  );
  document.getElementById("toasts").append(el);
  setTimeout(() => {
    el.classList.add("toast--leaving");
    setTimeout(() => el.remove(), 220);
  }, 4200);
}

function handleError(err) {
  if (err.status === 401) return; // a sessão já foi encerrada com aviso próprio
  toast(err.message, "error");
}

async function getDoctors(force = false) {
  if (!state.doctors || force) {
    const page = await api.get("/doctors", { limit: 100 });
    state.doctors = page.items;
  }
  return state.doctors;
}
