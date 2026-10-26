/* AgendaMed — interface web (JavaScript puro, sem etapa de build).
 *
 * Organização:
 *   1. Utilitários de DOM e datas
 *   2. Cliente da API
 *   3. Estado, sessão e avisos
 *   4. Componentes reutilizáveis (campos, tabelas, paginação, diálogos)
 *   5. Telas: login, agenda, consultas, médicos e pacientes
 *   6. Rotas e inicialização
 *
 * Todo texto vindo da API entra no DOM como nó de texto (nunca via innerHTML),
 * o que impede injeção de HTML/JS (XSS).
 */
"use strict";

/* ===================== 1. Utilitários ===================== */

function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (value === true) el.setAttribute(key, "");
    else el.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : String(child));
  }
  return el;
}

const ICONS = {
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
  doctor: '<path d="M6 3v6a4 4 0 0 0 8 0V3"/><path d="M10 13v2a5 5 0 0 0 10 0v-1"/><circle cx="20" cy="12" r="2"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18.5 14.5A6.5 6.5 0 0 1 21.5 20"/>',
  logout: '<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3"/><path d="M10 17l-5-5 5-5M5 12h11"/>',
  left: '<path d="M15 5l-7 7 7 7"/>',
  right: '<path d="M9 5l7 7-7 7"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  book: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4M12 13v5M9.5 15.5h5"/>',
};

function icon(name) {
  const wrap = document.createElement("span");
  wrap.setAttribute("aria-hidden", "true");
  wrap.style.display = "contents";
  // Conteúdo fixo, definido acima — nunca dados do usuário.
  wrap.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
  return wrap;
}

/** Substitui o conteúdo de um elemento, ignorando itens vazios (null, false, undefined). */
function fill(el, ...children) {
  el.replaceChildren(...children.flat(Infinity).filter((c) => c !== null && c !== undefined && c !== false));
}

function debounce(fn, wait = 250) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

function plural(n, one, many) {
  return `${n} ${n === 1 ? one : many}`;
}

const pad = (n) => String(n).padStart(2, "0");
const toISODate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const toLocalISO = (d) => `${toISODate(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const fmtTime = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;

function parseISODate(value) {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** Converte "AAAA-MM-DDTHH:MM" (horário local da clínica) em Date, sem fuso. */
function parseLocal(value) {
  const [datePart, timePart = "00:00"] = value.split("T");
  const date = parseISODate(datePart);
  const [hh, mm] = timePart.split(":").map(Number);
  date.setHours(hh, mm, 0, 0);
  return date;
}

function addDays(date, days) {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

const isWeekend = (date) => date.getDay() === 0 || date.getDay() === 6;

function nextWorkingDay(from, includeFrom) {
  let day = includeFrom ? new Date(from) : addDays(from, 1);
  while (isWeekend(day)) day = addDays(day, 1);
  return day;
}

const longDateFmt = new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "numeric", month: "long" });
const shortDateFmt = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);
const fmtLongDate = (d) => capitalize(longDateFmt.format(d));
const fmtShortDate = (d) => shortDateFmt.format(d);

function ageFrom(isoDate) {
  const birth = parseISODate(isoDate);
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const beforeBirthday =
    today.getMonth() < birth.getMonth() ||
    (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate());
  if (beforeBirthday) age -= 1;
  return age;
}

function maskCpf(value) {
  const d = value.replace(/\D/g, "").slice(0, 11);
  return d
    .replace(/^(\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d{1,2})$/, ".$1-$2");
}

function maskPhone(value) {
  const d = value.replace(/\D/g, "").slice(0, 11);
  if (d.length === 0) return "";
  if (d.length <= 2) return `(${d}`;
  if (d.length <= 6) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  if (d.length <= 10) return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
}

const STATUS_LABELS = { scheduled: "Agendada", completed: "Concluída", cancelled: "Cancelada" };

function statusBadge(status) {
  return h("span", { class: `badge badge--${status}` }, STATUS_LABELS[status] || status);
}

/* ===================== 2. Cliente da API ===================== */

class ApiError extends Error {
  constructor(status, message, errors = []) {
    super(message);
    this.status = status;
    this.errors = errors;
  }
}

const TOKEN_KEY = "agendamed.token";

const api = {
  get token() {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set token(value) {
    try {
      if (value) localStorage.setItem(TOKEN_KEY, value);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* armazenamento indisponível (ex.: navegação privada) */
    }
  },

  async request(method, path, body) {
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const token = this.token;
    if (token) headers.Authorization = `Bearer ${token}`;

    let response;
    try {
      response = await fetch(path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, "Sem conexão com o servidor. Verifique se a API está rodando.");
    }

    const data = await response.json().catch(() => null);
    if (!response.ok) {
      if (response.status === 401 && token && path !== "/auth/login") session.expire();
      throw new ApiError(response.status, data?.detail || "Erro inesperado no servidor.", data?.errors || []);
    }
    return data;
  },

  get(path, params) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params || {})) {
      if (value !== undefined && value !== null && value !== "") query.set(key, value);
    }
    const qs = query.toString();
    return this.request("GET", qs ? `${path}?${qs}` : path);
  },

  post(path, body = {}) {
    return this.request("POST", path, body);
  },
};

/* ===================== 3. Estado, sessão e avisos ===================== */

const state = {
  user: null,
  doctors: null, // cache da lista de médicos
  agenda: { doctorId: null, date: null, selectedKey: null },
  appointments: { date: "", doctorId: "", status: "", offset: 0 },
  doctorsPage: { specialty: "", offset: 0 },
  patientsPage: { q: "", offset: 0 },
};

const PAGE_SIZE = 20;
const DEMO_EMAIL = "admin@agendamed.dev";
const DEMO_PASSWORD = "admin12345";

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
    const { access_token: token } = await api.post("/auth/login", { email, password });
    api.token = token;
    state.user = await api.get("/auth/me");
    if (!location.hash) location.hash = "#/agendar";
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
  const el = h("div", { class: `toast toast--${tone}`, role: tone === "error" ? "alert" : "status" }, message);
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

/* ===================== 4. Componentes ===================== */

let fieldSeq = 0;

/** Campo de formulário com rótulo, dica e área de erro ligados por acessibilidade. */
function field({ label, name, type = "text", as = "input", hint, options, ...attrs }) {
  const id = `f-${name}-${++fieldSeq}`;
  const errorId = `${id}-error`;
  const hintId = hint ? `${id}-hint` : null;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ");
  const common = { id, name, class: "input", "aria-describedby": describedBy, ...attrs };

  let control;
  if (as === "select") {
    control = h("select", common, options.map(([value, text]) =>
      h("option", { value, selected: String(value) === String(attrs.value ?? "") }, text)));
  } else if (as === "textarea") {
    control = h("textarea", common);
  } else {
    control = h("input", { type, ...common });
  }

  return h("div", { class: "field" },
    h("label", { class: "field__label", for: id }, label),
    control,
    hint && h("p", { class: "field__hint", id: hintId }, hint),
    h("p", { class: "field__error", id: errorId, "data-error-for": name }),
  );
}

function clearFormErrors(form) {
  form.querySelectorAll("[data-error-for]").forEach((el) => (el.textContent = ""));
  form.querySelectorAll("[aria-invalid]").forEach((el) => el.removeAttribute("aria-invalid"));
  const general = form.querySelector(".form__error");
  if (general) general.textContent = "";
}

/** Mostra os erros da API ao lado de cada campo; o restante vai para o topo do formulário. */
function showFormErrors(form, err) {
  clearFormErrors(form);
  const leftovers = [];
  let firstInvalid = null;
  for (const { field: name, message } of err.errors || []) {
    const control = form.elements[name];
    const slot = form.querySelector(`[data-error-for="${CSS.escape(name)}"]`);
    if (control && slot) {
      control.setAttribute("aria-invalid", "true");
      slot.textContent = message;
      firstInvalid ??= control;
    } else {
      leftovers.push(message);
    }
  }
  const general = form.querySelector(".form__error");
  if (general && (leftovers.length || !firstInvalid)) {
    general.textContent = leftovers.length ? leftovers.join(" ") : err.message;
  }
  (firstInvalid || general)?.focus?.();
}

function formValues(form) {
  const values = {};
  for (const [key, value] of new FormData(form)) values[key] = typeof value === "string" ? value.trim() : value;
  return values;
}

function pageHead(title, subtitle, ...actions) {
  return h("header", { class: "page-head" },
    h("div", null,
      h("h1", { class: "page-title", tabindex: "-1" }, title),
      subtitle && h("p", { class: "page-sub" }, subtitle)),
    actions.length ? h("div", { class: "toolbar" }, actions) : null);
}

function loading(text = "Carregando…") {
  return h("p", { class: "loading", role: "status" }, text);
}

function dataTable({ caption, columns, rows, empty }) {
  const table = h("table", { class: "table" },
    h("caption", { class: "visually-hidden" }, caption),
    h("thead", null, h("tr", null, columns.map((col) => h("th", { scope: "col", class: col.class }, col.label)))),
    h("tbody", null, rows.length
      ? rows.map((row) => h("tr", null, columns.map((col) => h("td", { class: col.class }, col.render(row)))))
      : h("tr", null, h("td", { colspan: columns.length, class: "table__empty" }, empty))));
  return h("div", { class: "table-wrap" }, table);
}

function pager(page, onChange) {
  if (page.total === 0) return null;
  const from = page.offset + 1;
  const to = page.offset + page.items.length;
  return h("nav", { class: "pager", "aria-label": "Paginação" },
    h("span", null, `Mostrando ${from}–${to} de ${page.total}`),
    h("div", { class: "pager__btns" },
      h("button", {
        class: "btn btn--ghost btn--small", type: "button", disabled: page.offset === 0,
        onclick: () => onChange(Math.max(0, page.offset - page.limit)),
      }, "Anterior"),
      h("button", {
        class: "btn btn--ghost btn--small", type: "button", disabled: to >= page.total,
        onclick: () => onChange(page.offset + page.limit),
      }, "Próxima")));
}

function openDialog(title, buildBody) {
  const titleId = `dlg-${++fieldSeq}`;
  const dialog = h("dialog", { class: "dialog", "aria-labelledby": titleId });
  const close = () => dialog.close();
  dialog.addEventListener("close", () => dialog.remove());
  dialog.append(h("div", { class: "dialog__inner" },
    h("div", { class: "dialog__head" },
      h("h2", { class: "dialog__title", id: titleId }, title),
      h("button", { class: "btn btn--ghost btn--icon", type: "button", "aria-label": "Fechar", onclick: close }, icon("close"))),
    buildBody(close)));
  document.body.append(dialog);
  dialog.showModal();
  dialog.querySelector("input, select, textarea")?.focus();
  return close;
}

/** Botão de ação destrutiva com confirmação em dois cliques (sem janelas do navegador). */
function confirmButton(label, confirmLabel, onConfirm, extraClass = "") {
  let timer;
  const btn = h("button", { class: `btn btn--danger ${extraClass}`.trim(), type: "button" }, label);
  btn.addEventListener("click", async () => {
    if (!btn.classList.contains("is-confirming")) {
      btn.classList.add("is-confirming");
      btn.textContent = confirmLabel;
      timer = setTimeout(() => {
        btn.classList.remove("is-confirming");
        btn.textContent = label;
      }, 4000);
      return;
    }
    clearTimeout(timer);
    btn.disabled = true;
    try {
      await onConfirm();
    } finally {
      btn.disabled = false;
    }
  });
  return btn;
}

/* ---------- Formulários de cadastro ---------- */

function openDoctorDialog(onCreated) {
  openDialog("Cadastrar médico", (close) => {
    const form = h("form", { class: "form", novalidate: true },
      h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
      field({ label: "Nome completo", name: "name", required: true, autocomplete: "off" }),
      h("div", { class: "form__row" },
        field({ label: "Especialidade", name: "specialty", required: true }),
        field({ label: "CRM", name: "crm", required: true, hint: "Número e UF, como 123456/SP" })),
      h("div", { class: "form__row" },
        field({ label: "Início do expediente", name: "work_start", type: "time", value: "08:00", required: true }),
        field({ label: "Fim do expediente", name: "work_end", type: "time", value: "18:00", required: true }),
        field({
          label: "Duração da consulta", name: "slot_minutes", as: "select", value: "30",
          options: [[15, "15 minutos"], [20, "20 minutos"], [30, "30 minutos"], [45, "45 minutos"], [60, "1 hora"]],
        })),
      h("div", { class: "form__actions" },
        h("button", { class: "btn btn--ghost", type: "button", onclick: close }, "Cancelar"),
        h("button", { class: "btn btn--primary", type: "submit" }, "Cadastrar médico")));

    form.elements.crm.addEventListener("input", (e) => (e.target.value = e.target.value.toUpperCase()));
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = formValues(form);
      const submit = form.querySelector('[type="submit"]');
      submit.disabled = true;
      try {
        const doctor = await api.post("/doctors", { ...values, slot_minutes: Number(values.slot_minutes) });
        state.doctors = null;
        close();
        toast(`${doctor.name} foi cadastrado(a).`);
        onCreated?.(doctor);
      } catch (err) {
        if (err.status === 401) return;
        showFormErrors(form, err);
      } finally {
        submit.disabled = false;
      }
    });
    return form;
  });
}

function openPatientDialog(onCreated) {
  openDialog("Cadastrar paciente", (close) => {
    const form = h("form", { class: "form", novalidate: true },
      h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
      field({ label: "Nome completo", name: "name", required: true, autocomplete: "off" }),
      h("div", { class: "form__row" },
        field({ label: "CPF", name: "cpf", required: true, inputmode: "numeric", placeholder: "000.000.000-00" }),
        field({ label: "Data de nascimento", name: "birth_date", type: "date", required: true, max: toISODate(new Date()) })),
      h("div", { class: "form__row" },
        field({ label: "E-mail", name: "email", type: "email", required: true }),
        field({ label: "Telefone", name: "phone", type: "tel", inputmode: "tel", placeholder: "(00) 00000-0000", hint: "Opcional" })),
      h("div", { class: "form__actions" },
        h("button", { class: "btn btn--ghost", type: "button", onclick: close }, "Cancelar"),
        h("button", { class: "btn btn--primary", type: "submit" }, "Cadastrar paciente")));

    form.elements.cpf.addEventListener("input", (e) => (e.target.value = maskCpf(e.target.value)));
    form.elements.phone.addEventListener("input", (e) => (e.target.value = maskPhone(e.target.value)));
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = formValues(form);
      const submit = form.querySelector('[type="submit"]');
      submit.disabled = true;
      try {
        const patient = await api.post("/patients", { ...values, phone: values.phone || null });
        close();
        toast(`${patient.name} foi cadastrado(a).`);
        onCreated?.(patient);
      } catch (err) {
        if (err.status === 401) return;
        showFormErrors(form, err);
      } finally {
        submit.disabled = false;
      }
    });
    return form;
  });
}

/* ===================== 5. Telas ===================== */

const root = () => document.getElementById("root");

/* ---------- Login ---------- */

function renderLogin() {
  document.title = "Entrar | AgendaMed";
  let mode = "login";

  const sample = h("div", { class: "ruler-sample", "aria-hidden": "true" },
    [
      ["08:00", "block", "Ana Souza"],
      ["08:30", "free", "Livre"],
      ["09:00", "block", "Bruno Lima"],
      ["09:30", "free", "Livre"],
    ].map(([time, kind, text]) =>
      h("div", { class: `ruler-sample__row${time.endsWith(":00") ? " ruler-sample__row--hour" : ""}` },
        h("span", { class: "ruler-sample__time" }, time),
        h("span", { class: kind === "block" ? "ruler-sample__block" : "ruler-sample__free" }, text))));

  const brand = h("section", { class: "login__brand" },
    h("div", { class: "brand", style: "color:#fff" }, h("img", { src: "/static/icon.svg", alt: "" }), h("span", null, "AgendaMed")),
    h("div", null,
      h("p", { class: "login__title" }, "A agenda da clínica, em um só lugar."),
      h("p", { class: "login__lede" }, "Marque e acompanhe as consultas de cada médico sem conflito de horários.")),
    sample);

  const card = h("div", { class: "login__card" });
  const panel = h("main", { class: "login__panel" }, card);
  let demoMode = false;

  // Em modo demonstração (SEED_DEMO_DATA), o servidor avisa pelo /health e a tela
  // oferece entrada com um clique, sem precisar criar conta.
  api.get("/health").then((info) => {
    demoMode = Boolean(info?.demo);
    if (demoMode && mode === "login") draw();
  }).catch(() => {});

  async function enterDemo(button) {
    button.disabled = true;
    button.textContent = "Entrando…";
    try {
      await session.login(DEMO_EMAIL, DEMO_PASSWORD);
    } catch (err) {
      toast(err.message, "error");
      button.disabled = false;
      button.textContent = "Entrar na demonstração";
    }
  }

  function draw() {
    const isLogin = mode === "login";
    const tabs = h("div", { class: "tabs", role: "tablist", "aria-label": "Acesso" },
      h("button", { class: "tabs__btn", type: "button", role: "tab", "aria-selected": String(isLogin), onclick: () => switchTo("login") }, "Entrar"),
      h("button", { class: "tabs__btn", type: "button", role: "tab", "aria-selected": String(!isLogin), onclick: () => switchTo("register") }, "Criar conta"));

    const form = h("form", { class: "form", novalidate: true },
      h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
      !isLogin && field({ label: "Nome completo", name: "full_name", autocomplete: "name", required: true }),
      field({ label: "E-mail", name: "email", type: "email", autocomplete: "email", required: true }),
      field({
        label: "Senha", name: "password", type: "password", required: true,
        autocomplete: isLogin ? "current-password" : "new-password",
        hint: isLogin ? null : "Mínimo de 8 caracteres",
      }),
      h("button", {
        class: `btn ${isLogin && demoMode ? "btn--ghost" : "btn--primary"} btn--block`, type: "submit",
      }, isLogin ? "Entrar" : "Criar conta"));

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = formValues(form);
      const submit = form.querySelector('[type="submit"]');
      submit.disabled = true;
      clearFormErrors(form);
      try {
        if (!isLogin) await api.post("/auth/register", values);
        await session.login(values.email, values.password);
        if (!isLogin) toast("Conta criada. Boas-vindas ao AgendaMed!");
      } catch (err) {
        showFormErrors(form, err);
        submit.disabled = false;
      }
    });

    const demoNote = isLogin && !demoMode && h("div", { class: "demo-note" },
      "Rodou o comando ", h("strong", null, "seed"), "? Entre com a conta de demonstração. ",
      h("button", {
        class: "link-btn", type: "button",
        onclick: () => {
          form.elements.email.value = DEMO_EMAIL;
          form.elements.password.value = DEMO_PASSWORD;
          form.querySelector('[type="submit"]').focus();
        },
      }, "Preencher dados de demonstração"));

    let demoBlock = null;
    if (isLogin && demoMode) {
      const demoButton = h("button", { class: "btn btn--primary btn--block btn--large", type: "button" },
        "Entrar na demonstração");
      demoButton.addEventListener("click", () => enterDemo(demoButton));
      demoBlock = h("div", { class: "demo-entry" },
        demoButton,
        h("p", { class: "demo-entry__hint" },
          "Acesso imediato, sem cadastro, a uma clínica de exemplo com médicos, pacientes e consultas."),
        h("p", { class: "login__divider" }, "ou entre com a sua conta"));
    }

    fill(card, 
      h("h1", { class: "login__heading" }, isLogin ? "Entrar na sua conta" : "Criar uma conta"),
      tabs, demoBlock, form, demoNote);
  }

  function switchTo(next) {
    mode = next;
    draw();
    card.querySelector("input")?.focus();
  }

  draw();
  fill(root(), h("div", { class: "login" }, brand, panel));
}

/* ---------- Agendar (fluxo guiado) ---------- */

const chipDateFmt = new Intl.DateTimeFormat("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" });

/** Os próximos `count` dias úteis, começando por hoje se hoje for dia útil. */
function upcomingWorkingDays(count) {
  const days = [];
  let day = new Date();
  day.setHours(0, 0, 0, 0);
  while (days.length < count) {
    if (!isWeekend(day)) days.push(new Date(day));
    day = addDays(day, 1);
  }
  return days;
}

async function renderBooking(main, isCurrent) {
  fill(main, loading());
  let doctors;
  try {
    doctors = await getDoctors();
  } catch (err) {
    handleError(err);
    return;
  }
  if (!isCurrent()) return;

  // Escolhas da pessoa ao longo das etapas.
  const b = { doctor: null, date: null, slot: null, patient: null, days: [] };

  const doctorStep = h("section", { class: "step", "aria-labelledby": "step-doctor" });
  const timeStep = h("section", { class: "step step--locked", "aria-labelledby": "step-time" });
  const patientStep = h("section", { class: "step step--locked", "aria-labelledby": "step-patient" });
  const summary = h("aside", { class: "panel summary", "aria-label": "Resumo do agendamento" });

  fill(main, 
    pageHead("Agendar consulta", "Escolha o médico, o horário e o paciente. O resumo ao lado mostra o que será marcado."),
    h("div", { class: "booking" }, h("div", { class: "booking__steps" }, doctorStep, timeStep, patientStep), summary));

  function stepHead(number, id, title, hint) {
    return h("header", { class: "step__head" },
      h("span", { class: "step__num", "aria-hidden": "true" }, number),
      h("div", null,
        h("h2", { class: "step__title", id }, title),
        hint && h("p", { class: "step__hint" }, hint)));
  }

  /* Etapa 1: médico */
  function drawDoctors() {
    if (doctors.length === 0) {
      fill(doctorStep, 
        stepHead(1, "step-doctor", "Escolha o médico"),
        h("p", { class: "step__empty" }, "Nenhum médico cadastrado ainda."),
        h("div", null, h("button", {
          class: "btn btn--primary", type: "button",
          onclick: () => openDoctorDialog(() => navigate()),
        }, icon("plus"), "Cadastrar médico")));
      return;
    }
    fill(doctorStep, 
      stepHead(1, "step-doctor", "Escolha o médico", b.doctor ? null : "Toque no profissional para ver os horários livres."),
      h("div", { class: "choice-grid", role: "group", "aria-label": "Médicos" },
        doctors.map((d) => h("button", {
          class: "choice", type: "button", "aria-pressed": String(b.doctor?.id === d.id),
          onclick: () => chooseDoctor(d),
        },
          h("span", { class: "choice__title" }, d.name),
          h("span", { class: "choice__meta" }, d.specialty),
          h("span", { class: "choice__foot" }, `Atende das ${d.work_start} às ${d.work_end}`),
          h("span", { class: "choice__foot" }, `Consultas de ${d.slot_minutes} minutos`)))));
  }

  /* Etapa 2: dia e horário */
  let daysSeq = 0;
  async function chooseDoctor(doctor) {
    b.doctor = doctor;
    b.slot = null;
    b.days = [];
    drawDoctors();
    drawSummary();
    timeStep.className = "step";
    fill(timeStep, stepHead(2, "step-time", "Escolha o dia e o horário"), loading("Buscando horários livres…"));

    const seq = ++daysSeq;
    const days = upcomingWorkingDays(10);
    try {
      const results = await Promise.all(days.map((day) =>
        api.get(`/doctors/${doctor.id}/availability`, { date: toISODate(day) })));
      if (seq !== daysSeq || !isCurrent()) return;
      b.days = days.map((day, i) => ({ day, iso: toISODate(day), slots: results[i].available_slots }));
      const firstWithSlots = b.days.find((d) => d.slots.length > 0);
      b.date = (firstWithSlots || b.days[0]).iso;
      drawTimes();
      if (window.matchMedia("(max-width: 1100px)").matches) {
        timeStep.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch (err) {
      if (seq !== daysSeq) return;
      handleError(err);
      fill(timeStep, stepHead(2, "step-time", "Escolha o dia e o horário"),
        h("p", { class: "step__empty" }, err.message));
    }
  }

  function drawTimes() {
    const current = b.days.find((d) => d.iso === b.date);
    const strip = h("div", { class: "day-strip", role: "group", "aria-label": "Dias" },
      b.days.map((d) => h("button", {
        class: "day-chip", type: "button", "aria-pressed": String(d.iso === b.date), disabled: d.slots.length === 0,
        onclick: () => {
          b.date = d.iso;
          b.slot = null;
          drawTimes();
          drawSummary();
        },
      },
        h("span", { class: "day-chip__day" }, capitalize(chipDateFmt.format(d.day).replace(".", ""))),
        h("span", { class: "day-chip__count" }, d.slots.length ? plural(d.slots.length, "livre", "livres") : "Sem vagas"))));

    const times = current.slots.length
      ? h("div", { class: "time-grid", role: "group", "aria-label": "Horários livres" },
        current.slots.map((key) => h("button", {
          class: "time-btn", type: "button", "aria-pressed": String(b.slot === key),
          onclick: () => {
            b.slot = key;
            drawTimes();
            drawSummary();
            unlockPatients();
          },
        }, fmtTime(parseLocal(key)))))
      : h("p", { class: "step__empty" }, "Sem horários livres neste dia. Escolha outro dia acima.");

    fill(timeStep, 
      stepHead(2, "step-time", "Escolha o dia e o horário", fmtLongDate(parseISODate(b.date))),
      strip, times);
  }

  /* Etapa 3: paciente */
  let patientsReady = false;
  function unlockPatients() {
    if (patientsReady) return;
    patientsReady = true;
    patientStep.className = "step";

    const search = h("input", {
      class: "input", type: "search", id: "booking-search", placeholder: "Buscar por nome ou CPF", autocomplete: "off",
    });
    const results = h("div", { class: "picker picker--wide", role: "group", "aria-label": "Pacientes encontrados" });
    const notes = h("textarea", {
      class: "input", id: "booking-notes", maxlength: "500", placeholder: "Motivo da consulta, retorno, exames…",
    });
    notes.addEventListener("input", () => (b.notes = notes.value.trim()));

    function drawResults(patients) {
      if (patients.length === 0) {
        fill(results, h("p", { class: "picker__empty" }, "Nenhum paciente encontrado. Cadastre um novo abaixo."));
        return;
      }
      fill(results, ...patients.map((p) => h("button", {
        class: "picker__option", type: "button", "aria-pressed": String(b.patient?.id === p.id),
        onclick: (event) => {
          b.patient = p;
          results.querySelectorAll(".picker__option").forEach((el) => el.setAttribute("aria-pressed", "false"));
          event.currentTarget.setAttribute("aria-pressed", "true");
          drawSummary();
        },
      },
        h("span", { class: "picker__name" }, p.name),
        h("span", { class: "picker__meta" }, `CPF ${p.cpf}, ${ageFrom(p.birth_date)} anos`))));
    }

    async function loadPatients(q = "") {
      try {
        const page = await api.get("/patients", { q, limit: 8 });
        if (isCurrent()) drawResults(page.items);
      } catch (err) {
        handleError(err);
      }
    }
    search.addEventListener("input", debounce(() => loadPatients(search.value.trim())));
    loadPatients();

    fill(patientStep, 
      stepHead(3, "step-patient", "Escolha o paciente"),
      h("div", { class: "field" },
        h("label", { class: "field__label", for: "booking-search" }, "Paciente"),
        search, results,
        h("button", {
          class: "link-btn", type: "button", style: "justify-self:start",
          onclick: () => openPatientDialog((p) => {
            b.patient = p;
            search.value = p.name;
            drawResults([p]);
            drawSummary();
          }),
        }, "Cadastrar novo paciente")),
      h("div", { class: "field" },
        h("label", { class: "field__label", for: "booking-notes" }, "Observações (opcional)"),
        notes));
  }

  /* Resumo e confirmação */
  function summaryRow(label, value) {
    return h("div", null,
      h("dt", null, label),
      h("dd", { class: value ? null : "is-empty" }, value || "Ainda não escolhido"));
  }

  function drawSummary() {
    const start = b.slot ? parseLocal(b.slot) : null;
    const end = start ? new Date(start.getTime() + b.doctor.slot_minutes * 60000) : null;
    const ready = Boolean(b.doctor && b.slot && b.patient);
    let next = "Comece escolhendo o médico.";
    if (b.doctor && !b.slot) next = "Agora escolha o dia e o horário.";
    else if (b.slot && !b.patient) next = "Falta escolher o paciente.";

    const error = h("p", { class: "form__error", role: "alert" });
    const confirm = h("button", { class: "btn btn--primary btn--block btn--large", type: "button", disabled: !ready },
      "Confirmar agendamento");
    confirm.addEventListener("click", async () => {
      confirm.disabled = true;
      confirm.textContent = "Agendando…";
      try {
        const appointment = await api.post("/appointments", {
          doctor_id: b.doctor.id, patient_id: b.patient.id, start_at: b.slot, notes: b.notes || null,
        });
        drawSuccess(appointment);
      } catch (err) {
        if (err.status === 401) return;
        error.textContent = err.errors?.length ? err.errors.map((e) => e.message).join(" ") : err.message;
        confirm.textContent = "Confirmar agendamento";
        if (err.status === 409 || err.status === 422) {
          // O horário foi ocupado ou passou enquanto a pessoa escolhia: atualiza a grade.
          const patient = b.patient;
          await chooseDoctor(b.doctor);
          b.patient = patient;
          drawSummary();
          summary.querySelector(".form__error").textContent = error.textContent;
        } else {
          confirm.disabled = false;
        }
      }
    });

    fill(summary, 
      h("h2", { class: "panel__title" }, "Resumo"),
      h("dl", { class: "details" },
        summaryRow("Médico", b.doctor && `${b.doctor.name}, ${b.doctor.specialty}`),
        summaryRow("Dia", start && fmtLongDate(start)),
        summaryRow("Horário", start && `${fmtTime(start)} às ${fmtTime(end)}`),
        summaryRow("Paciente", b.patient?.name)),
      error,
      confirm,
      !ready && h("p", { class: "summary__hint" }, next));
  }

  function drawSuccess(ap) {
    const start = parseLocal(ap.start_at);
    const end = parseLocal(ap.end_at);
    toast("Consulta agendada.");
    fill(summary, 
      h("div", { class: "success" },
        h("span", { class: "success__icon" }, icon("check")),
        h("h2", { class: "panel__title", tabindex: "-1" }, "Consulta agendada"),
        h("p", null, `${ap.patient.name} com ${ap.doctor.name}`),
        h("p", { class: "panel__when" }, `${fmtLongDate(start)}, das ${fmtTime(start)} às ${fmtTime(end)}`)),
      h("div", { class: "success__actions" },
        h("button", { class: "btn btn--primary btn--block", type: "button", onclick: () => navigate() }, "Agendar outra consulta"),
        h("button", {
          class: "btn btn--ghost btn--block", type: "button",
          onclick: () => {
            Object.assign(state.agenda, { doctorId: ap.doctor.id, date: ap.start_at.slice(0, 10), selectedKey: ap.start_at });
            location.hash = "#/agenda";
          },
        }, "Ver na agenda do médico")));
    summary.querySelector(".panel__title").focus();
    if (window.matchMedia("(max-width: 1100px)").matches) {
      summary.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  drawDoctors();
  fill(timeStep, stepHead(2, "step-time", "Escolha o dia e o horário", "Disponível depois de escolher o médico."));
  fill(patientStep, stepHead(3, "step-patient", "Escolha o paciente", "Disponível depois de escolher o horário."));
  drawSummary();
}

/* ---------- Agenda ---------- */

async function renderAgenda(main, isCurrent) {
  fill(main, loading());
  let doctors;
  try {
    doctors = await getDoctors();
  } catch (err) {
    handleError(err);
    return;
  }
  if (!isCurrent()) return;

  if (doctors.length === 0) {
    fill(main, 
      pageHead("Agenda", "Os horários aparecem aqui depois que um médico é cadastrado."),
      h("div", { class: "ruler" }, h("div", { class: "agenda-empty" },
        h("strong", null, "Nenhum médico cadastrado"),
        h("p", null, "Cadastre o primeiro médico para montar a agenda."),
        h("p", { style: "margin-top:16px" },
          h("button", { class: "btn btn--primary", type: "button", onclick: () => openDoctorDialog(() => navigate()) },
            icon("plus"), "Cadastrar médico")))));
    return;
  }

  const a = state.agenda;
  if (!doctors.some((d) => d.id === a.doctorId)) a.doctorId = doctors[0].id;
  if (!a.date) a.date = toISODate(nextWorkingDay(new Date(), true));
  const doctor = () => doctors.find((d) => d.id === a.doctorId);

  const doctorField = field({
    label: "Médico", name: "doctor", as: "select", value: a.doctorId,
    options: doctors.map((d) => [d.id, `${d.name} (${d.specialty})`]),
  });
  doctorField.querySelector("select").addEventListener("change", (e) => {
    a.doctorId = Number(e.target.value);
    a.selectedKey = null;
    loadDay();
  });

  const dateLabel = h("h2", { class: "daybar__date" });
  const summary = h("p", { class: "daybar__summary", "aria-live": "polite" });
  const dateInput = h("input", { class: "input", type: "date", value: a.date, "aria-label": "Escolher data" });
  dateInput.addEventListener("change", () => dateInput.value && goTo(dateInput.value));

  const daybar = h("div", { class: "daybar" },
    h("div", null, dateLabel, summary),
    h("div", { class: "daybar__nav" },
      h("button", { class: "btn btn--ghost btn--icon", type: "button", "aria-label": "Dia anterior", onclick: () => goTo(toISODate(addDays(parseISODate(a.date), -1))) }, icon("left")),
      dateInput,
      h("button", { class: "btn btn--ghost btn--icon", type: "button", "aria-label": "Próximo dia", onclick: () => goTo(toISODate(addDays(parseISODate(a.date), 1))) }, icon("right")),
      h("button", { class: "btn btn--ghost", type: "button", onclick: () => goTo(toISODate(new Date())) }, "Hoje")));

  const ruler = h("div", { class: "ruler", role: "list", "aria-label": "Horários do dia" });
  const panel = h("aside", { class: "panel", "aria-label": "Detalhes do horário" });

  fill(main, 
    pageHead("Agenda", "Veja o dia de cada médico e marque consultas nos horários livres.", doctorField),
    h("div", { class: "agenda" }, h("section", null, daybar, ruler), panel));

  let day = null;
  let daySeq = 0;

  function goTo(iso) {
    a.date = iso;
    a.selectedKey = null;
    dateInput.value = iso;
    loadDay();
  }

  async function loadDay() {
    const seq = ++daySeq;
    const current = doctor();
    dateLabel.textContent = fmtLongDate(parseISODate(a.date));
    summary.textContent = "";
    fill(ruler, loading("Carregando horários…"));
    try {
      const [availability, list] = await Promise.all([
        api.get(`/doctors/${current.id}/availability`, { date: a.date }),
        api.get("/appointments", { doctor_id: current.id, date: a.date, limit: 100 }),
      ]);
      if (seq !== daySeq || !isCurrent()) return;
      const active = list.items.filter((item) => item.status !== "cancelled");
      day = { doctor: current, slots: buildSlots(current, a.date, new Set(availability.available_slots), active) };
      drawDay();
    } catch (err) {
      if (seq !== daySeq) return;
      handleError(err);
      fill(ruler, h("div", { class: "agenda-empty" },
        h("strong", null, "Não foi possível carregar a agenda"), h("p", null, err.message)));
    }
  }

  function drawDay() {
    const dateObj = parseISODate(a.date);
    const booked = day.slots.filter((s) => s.kind === "booked" || s.kind === "done").length;
    const free = day.slots.filter((s) => s.kind === "free").length;

    if (isWeekend(dateObj) && booked === 0) {
      summary.textContent = "Sem atendimento";
      fill(ruler, h("div", { class: "agenda-empty" },
        h("strong", null, "Os médicos não atendem aos fins de semana"),
        h("p", { style: "margin-top:12px" },
          h("button", { class: "btn btn--ghost", type: "button", onclick: () => goTo(toISODate(nextWorkingDay(dateObj, false))) },
            "Ir para o próximo dia útil"))));
      drawPanel();
      return;
    }

    summary.textContent = `${plural(booked, "consulta", "consultas")} e ${plural(free, "horário livre", "horários livres")}`;
    fill(ruler, ...day.slots.map(slotRow));
    drawNowLine(dateObj);
    drawPanel();
  }

  function slotRow(slot) {
    const isSelected = slot.key === a.selectedKey;
    const select = () => {
      a.selectedKey = slot.key;
      ruler.querySelectorAll('[aria-pressed="true"]').forEach((el) => el.setAttribute("aria-pressed", "false"));
      row.querySelector("button")?.setAttribute("aria-pressed", "true");
      drawPanel();
      if (window.matchMedia("(max-width: 1100px)").matches) panel.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    let body;
    if (slot.kind === "free") {
      body = h("button", { class: "slot__btn", type: "button", "aria-pressed": String(isSelected), onclick: select },
        h("span", null, "Livre"),
        h("span", { class: "slot__cta" }, `Agendar às ${fmtTime(slot.time)}`));
    } else if (slot.kind === "past") {
      body = h("div", { title: "Horário indisponível" }, h("span", { class: "visually-hidden" }, "Indisponível"));
    } else {
      const ap = slot.appointment;
      body = h("button", { class: "slot__btn", type: "button", "aria-pressed": String(isSelected), onclick: select },
        h("span", { class: "slot__who" },
          h("span", { class: "slot__name" }, ap.patient.name),
          ap.notes && h("span", { class: "slot__note" }, ap.notes)),
        slot.kind === "done"
          ? statusBadge("completed")
          : h("span", { class: "slot__range" }, `${fmtTime(parseLocal(ap.start_at))} às ${fmtTime(parseLocal(ap.end_at))}`));
    }

    const row = h("div", {
      class: `slot slot--${slot.kind}${slot.time.getMinutes() === 0 ? " slot--hour" : ""}`,
      role: "listitem", "data-key": slot.key,
    },
      h("span", { class: "slot__time" }, fmtTime(slot.time)),
      h("div", { class: "slot__body" }, body));
    return row;
  }

  function drawNowLine(dateObj) {
    const now = new Date();
    if (toISODate(now) !== toISODate(dateObj)) return;
    const rows = [...ruler.querySelectorAll(".slot")];
    const minutes = day.doctor.slot_minutes;
    const index = day.slots.findIndex((s) => now >= s.time && now < new Date(s.time.getTime() + minutes * 60000));
    if (index < 0) return;
    requestAnimationFrame(() => {
      const row = rows[index];
      const fraction = (now - day.slots[index].time) / (minutes * 60000);
      const line = h("div", { class: "now-line", style: `top:${row.offsetTop + fraction * row.offsetHeight}px`, "aria-hidden": "true" },
        h("span", null, `Agora ${fmtTime(now)}`));
      ruler.append(line);
    });
  }

  function drawPanel() {
    const slot = day?.slots.find((s) => s.key === a.selectedKey);
    if (!slot || slot.kind === "past") {
      const d = doctor();
      fill(panel, 
        h("h2", { class: "panel__title" }, "Selecione um horário"),
        h("div", { class: "panel__hint" },
          h("p", null, "Clique em um horário livre para marcar uma consulta, ou em uma consulta para ver os detalhes."),
          h("p", null, `${d.name} atende de ${d.work_start} às ${d.work_end}, com consultas de ${d.slot_minutes} minutos.`)));
    } else if (slot.kind === "free") {
      fill(panel, ...bookingPanel(slot));
    } else {
      fill(panel, ...detailsPanel(slot.appointment));
    }
  }

  function bookingPanel(slot) {
    const d = doctor();
    const end = new Date(slot.time.getTime() + d.slot_minutes * 60000);
    let chosen = null;

    const search = h("input", { class: "input", type: "search", id: "patient-search", placeholder: "Buscar por nome ou CPF", autocomplete: "off" });
    const results = h("div", { class: "picker", role: "group", "aria-label": "Pacientes encontrados" });
    const notes = h("textarea", { class: "input", id: "booking-notes", name: "notes", maxlength: "500", placeholder: "Motivo da consulta, retorno, exames…" });
    const error = h("p", { class: "form__error", role: "alert" });
    const submit = h("button", { class: "btn btn--primary btn--block", type: "submit" }, "Agendar consulta");

    function drawResults(patients) {
      if (patients.length === 0) {
        fill(results, h("p", { class: "picker__empty" }, "Nenhum paciente encontrado."));
        return;
      }
      fill(results, ...patients.map((p) => {
        const option = h("button", {
          class: "picker__option", type: "button", "aria-pressed": String(chosen?.id === p.id),
          onclick: () => {
            chosen = p;
            error.textContent = "";
            results.querySelectorAll(".picker__option").forEach((el) => el.setAttribute("aria-pressed", "false"));
            option.setAttribute("aria-pressed", "true");
          },
        },
          h("span", { class: "picker__name" }, p.name),
          h("span", { class: "picker__meta" }, `CPF ${p.cpf}, ${ageFrom(p.birth_date)} anos`));
        return option;
      }));
    }

    async function loadPatients(q = "") {
      try {
        const page = await api.get("/patients", { q, limit: 8 });
        drawResults(page.items);
      } catch (err) {
        handleError(err);
      }
    }
    search.addEventListener("input", debounce(() => loadPatients(search.value.trim())));
    loadPatients();

    const form = h("form", { class: "form", novalidate: true },
      h("div", { class: "field" },
        h("label", { class: "field__label", for: "patient-search" }, "Paciente"),
        search, results,
        h("button", {
          class: "link-btn", type: "button", style: "justify-self:start",
          onclick: () => openPatientDialog((p) => {
            chosen = p;
            search.value = p.name;
            drawResults([p]);
          }),
        }, "Cadastrar novo paciente")),
      h("div", { class: "field" },
        h("label", { class: "field__label", for: "booking-notes" }, "Observações"),
        notes),
      error,
      submit);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!chosen) {
        error.textContent = "Escolha o paciente da consulta.";
        search.focus();
        return;
      }
      submit.disabled = true;
      try {
        await api.post("/appointments", {
          doctor_id: d.id,
          patient_id: chosen.id,
          start_at: slot.key,
          notes: notes.value.trim() || null,
        });
        toast(`Consulta de ${chosen.name} agendada para as ${fmtTime(slot.time)}.`);
        await loadDay();
      } catch (err) {
        if (err.status === 401) return;
        error.textContent = err.errors?.length ? err.errors.map((e) => e.message).join(" ") : err.message;
        if (err.status === 409) loadDay();
      } finally {
        submit.disabled = false;
      }
    });

    return [
      h("div", null,
        h("h2", { class: "panel__title" }, "Nova consulta"),
        h("p", { class: "panel__when" }, `${fmtLongDate(slot.time)}, das ${fmtTime(slot.time)} às ${fmtTime(end)}`)),
      form,
    ];
  }

  function detailsPanel(ap) {
    const start = parseLocal(ap.start_at);
    const end = parseLocal(ap.end_at);
    const started = start <= new Date();
    const actions = h("div", { class: "form__actions", style: "justify-content:stretch" });

    async function act(action, message) {
      try {
        await api.post(`/appointments/${ap.id}/${action}`);
        toast(message);
        if (action === "cancel") a.selectedKey = null;
        await loadDay();
      } catch (err) {
        handleError(err);
      }
    }

    if (ap.status === "scheduled" && started) {
      actions.append(h("button", {
        class: "btn btn--primary btn--block", type: "button",
        onclick: () => act("complete", "Consulta concluída."),
      }, "Concluir consulta"));
    }
    if (ap.status === "scheduled" && !started) {
      actions.append(confirmButton("Cancelar consulta", "Confirmar cancelamento",
        () => act("cancel", "Consulta cancelada. O horário voltou a ficar livre."), "btn--block"));
    }

    return [
      h("div", null,
        h("h2", { class: "panel__title" }, ap.patient.name),
        h("p", { class: "panel__when" }, `${fmtLongDate(start)}, das ${fmtTime(start)} às ${fmtTime(end)}`)),
      h("dl", { class: "details" },
        h("div", null, h("dt", null, "Situação"), h("dd", null, statusBadge(ap.status))),
        h("div", null, h("dt", null, "Médico"), h("dd", null, ap.doctor.name)),
        h("div", null, h("dt", null, "Observações"), h("dd", null, ap.notes || "Sem observações"))),
      actions.childElementCount ? actions : null,
    ];
  }

  loadDay();
}

function buildSlots(doctor, isoDate, freeKeys, appointments) {
  const [sh, sm] = doctor.work_start.split(":").map(Number);
  const [eh, em] = doctor.work_end.split(":").map(Number);
  const start = parseISODate(isoDate);
  start.setHours(sh, sm, 0, 0);
  const end = parseISODate(isoDate);
  end.setHours(eh, em, 0, 0);
  const step = doctor.slot_minutes * 60000;
  const byStart = new Map(appointments.map((ap) => [ap.start_at, ap]));

  const slots = [];
  for (let t = start.getTime(); t + step <= end.getTime(); t += step) {
    const time = new Date(t);
    const key = toLocalISO(time);
    const appointment = byStart.get(key);
    let kind = "past";
    if (appointment) kind = appointment.status === "completed" ? "done" : "booked";
    else if (freeKeys.has(key)) kind = "free";
    slots.push({ key, time, kind, appointment });
  }
  return slots;
}

/* ---------- Consultas ---------- */

async function renderAppointments(main, isCurrent) {
  const f = state.appointments;
  fill(main, loading());
  let doctors;
  try {
    doctors = await getDoctors();
  } catch (err) {
    handleError(err);
    return;
  }
  if (!isCurrent()) return;

  const filters = h("form", { class: "toolbar", role: "search", "aria-label": "Filtrar consultas" },
    field({ label: "Data", name: "date", type: "date", value: f.date }),
    field({
      label: "Médico", name: "doctor_id", as: "select", value: f.doctorId,
      options: [["", "Todos os médicos"], ...doctors.map((d) => [d.id, d.name])],
    }),
    field({
      label: "Situação", name: "status", as: "select", value: f.status,
      options: [["", "Todas"], ["scheduled", "Agendadas"], ["completed", "Concluídas"], ["cancelled", "Canceladas"]],
    }),
    h("button", {
      class: "btn btn--ghost", type: "button",
      onclick: () => {
        Object.assign(f, { date: "", doctorId: "", status: "", offset: 0 });
        navigate();
      },
    }, "Limpar filtros"));

  const listArea = h("div", null, loading());

  filters.addEventListener("change", () => {
    const values = formValues(filters);
    f.date = values.date;
    f.doctorId = values.doctor_id;
    f.status = values.status;
    f.offset = 0;
    load();
  });
  filters.addEventListener("submit", (e) => e.preventDefault());

  fill(main, pageHead("Consultas", "Todas as consultas da clínica, com filtros por dia, médico e situação."), filters, h("div", { style: "height:20px" }), listArea);

  async function load() {
    try {
      const page = await api.get("/appointments", {
        date: f.date, doctor_id: f.doctorId, status: f.status, limit: PAGE_SIZE, offset: f.offset,
      });
      if (!isCurrent()) return;
      draw(page);
    } catch (err) {
      handleError(err);
    }
  }

  function draw(page) {
    const now = new Date();
    fill(listArea, 
      dataTable({
        caption: "Lista de consultas",
        empty: "Nenhuma consulta encontrada com esses filtros.",
        rows: page.items,
        columns: [
          { label: "Data", class: "num", render: (ap) => fmtShortDate(parseLocal(ap.start_at)) },
          { label: "Horário", class: "num", render: (ap) => `${fmtTime(parseLocal(ap.start_at))} às ${fmtTime(parseLocal(ap.end_at))}` },
          { label: "Paciente", render: (ap) => ap.patient.name },
          { label: "Médico", render: (ap) => ap.doctor.name },
          { label: "Situação", render: (ap) => statusBadge(ap.status) },
          {
            label: "Ações", class: "actions",
            render: (ap) => {
              const start = parseLocal(ap.start_at);
              const buttons = [h("button", {
                class: "btn btn--ghost btn--small", type: "button",
                onclick: () => {
                  Object.assign(state.agenda, { doctorId: ap.doctor.id, date: ap.start_at.slice(0, 10), selectedKey: ap.status === "cancelled" ? null : ap.start_at });
                  location.hash = "#/agenda";
                },
              }, "Ver na agenda")];
              if (ap.status === "scheduled" && start <= now) {
                buttons.push(h("button", {
                  class: "btn btn--primary btn--small", type: "button",
                  onclick: () => act(ap, "complete", "Consulta concluída."),
                }, "Concluir"));
              }
              if (ap.status === "scheduled" && start > now) {
                buttons.push(confirmButton("Cancelar", "Confirmar", () => act(ap, "cancel", "Consulta cancelada."), "btn--small"));
              }
              return buttons;
            },
          },
        ],
      }),
      pager(page, (offset) => {
        f.offset = offset;
        load();
      }));
  }

  async function act(ap, action, message) {
    try {
      await api.post(`/appointments/${ap.id}/${action}`);
      toast(message);
      load();
    } catch (err) {
      handleError(err);
    }
  }

  load();
}

/* ---------- Médicos ---------- */

async function renderDoctors(main, isCurrent) {
  const f = state.doctorsPage;
  const search = field({ label: "Buscar por especialidade", name: "specialty", type: "search", value: f.specialty, placeholder: "Ex.: Pediatria" });
  search.classList.add("field--grow");
  const listArea = h("div", null, loading());

  search.querySelector("input").addEventListener("input", debounce((e) => {
    f.specialty = e.target.value.trim();
    f.offset = 0;
    load();
  }));

  fill(main, 
    pageHead("Médicos", "Profissionais da clínica, seus horários de atendimento e a duração de cada consulta.",
      h("button", { class: "btn btn--primary", type: "button", onclick: () => openDoctorDialog(() => load()) }, icon("plus"), "Cadastrar médico")),
    h("div", { class: "toolbar", role: "search", style: "margin-bottom:20px" }, search),
    listArea);

  async function load() {
    try {
      const page = await api.get("/doctors", { specialty: f.specialty, limit: PAGE_SIZE, offset: f.offset });
      if (!isCurrent()) return;
      fill(listArea, 
        dataTable({
          caption: "Lista de médicos",
          empty: f.specialty ? "Nenhum médico com essa especialidade." : "Nenhum médico cadastrado ainda.",
          rows: page.items,
          columns: [
            { label: "Nome", render: (d) => h("strong", null, d.name) },
            { label: "Especialidade", render: (d) => d.specialty },
            { label: "CRM", class: "num", render: (d) => d.crm },
            { label: "Expediente", class: "num", render: (d) => `${d.work_start} às ${d.work_end}` },
            { label: "Consulta", class: "num", render: (d) => `${d.slot_minutes} min` },
            {
              label: "Ações", class: "actions",
              render: (d) => h("button", {
                class: "btn btn--ghost btn--small", type: "button",
                onclick: () => {
                  Object.assign(state.agenda, { doctorId: d.id, selectedKey: null });
                  location.hash = "#/agenda";
                },
              }, "Ver agenda"),
            },
          ],
        }),
        pager(page, (offset) => {
          f.offset = offset;
          load();
        }));
    } catch (err) {
      handleError(err);
    }
  }

  load();
}

/* ---------- Pacientes ---------- */

async function renderPatients(main, isCurrent) {
  const f = state.patientsPage;
  const search = field({ label: "Buscar paciente", name: "q", type: "search", value: f.q, placeholder: "Nome ou CPF" });
  search.classList.add("field--grow");
  const listArea = h("div", null, loading());

  search.querySelector("input").addEventListener("input", debounce((e) => {
    f.q = e.target.value.trim();
    f.offset = 0;
    load();
  }));

  fill(main, 
    pageHead("Pacientes", "Cadastro de pacientes, com CPF validado e dados de contato.",
      h("button", { class: "btn btn--primary", type: "button", onclick: () => openPatientDialog(() => load()) }, icon("plus"), "Cadastrar paciente")),
    h("div", { class: "toolbar", role: "search", style: "margin-bottom:20px" }, search),
    listArea);

  async function load() {
    try {
      const page = await api.get("/patients", { q: f.q, limit: PAGE_SIZE, offset: f.offset });
      if (!isCurrent()) return;
      fill(listArea, 
        dataTable({
          caption: "Lista de pacientes",
          empty: f.q ? "Nenhum paciente encontrado com essa busca." : "Nenhum paciente cadastrado ainda.",
          rows: page.items,
          columns: [
            { label: "Nome", render: (p) => h("strong", null, p.name) },
            { label: "CPF", class: "num", render: (p) => p.cpf },
            {
              label: "Nascimento", class: "num",
              render: (p) => [fmtShortDate(parseISODate(p.birth_date)), h("br"), h("span", { class: "muted" }, `${ageFrom(p.birth_date)} anos`)],
            },
            { label: "E-mail", render: (p) => p.email },
            { label: "Telefone", class: "num", render: (p) => p.phone || h("span", { class: "muted" }, "Não informado") },
          ],
        }),
        pager(page, (offset) => {
          f.offset = offset;
          load();
        }));
    } catch (err) {
      handleError(err);
    }
  }

  load();
}

/* ===================== 6. Rotas e inicialização ===================== */

const ROUTES = [
  { path: "agendar", label: "Agendar", icon: "book", render: renderBooking },
  { path: "agenda", label: "Agenda", icon: "calendar", render: renderAgenda },
  { path: "consultas", label: "Consultas", icon: "list", render: renderAppointments },
  { path: "medicos", label: "Médicos", icon: "doctor", render: renderDoctors },
  { path: "pacientes", label: "Pacientes", icon: "users", render: renderPatients },
];

let renderSeq = 0;
let mainEl = null;

function renderShell() {
  const nav = h("nav", { class: "nav", "aria-label": "Principal" },
    ROUTES.map((r) => h("a", { class: "nav__link", href: `#/${r.path}`, "data-path": r.path }, icon(r.icon), h("span", null, r.label))));

  const sidebar = h("header", { class: "sidebar" },
    h("a", { class: "brand", href: "#/agendar" }, h("img", { src: "/static/icon.svg", alt: "" }), h("span", null, "AgendaMed")),
    nav,
    h("a", { class: "sidebar__docs", href: "/docs", target: "_blank", rel: "noopener" }, "Documentação da API"),
    h("div", { class: "sidebar__user" },
      h("div", null,
        h("p", { class: "sidebar__user-name" }, state.user.full_name),
        h("p", { class: "sidebar__user-email" }, state.user.email)),
      h("button", { class: "btn btn--ghost btn--small", type: "button", onclick: () => session.logout() }, icon("logout"), "Sair")));

  mainEl = h("main", { class: "main", id: "main" });
  fill(root(), h("div", { class: "shell" }, sidebar, mainEl));
  navigate({ focus: false });
}

function navigate({ focus = true } = {}) {
  if (!state.user || !mainEl) return;
  const path = location.hash.replace(/^#\/?/, "") || "agendar";
  const route = ROUTES.find((r) => r.path === path) || ROUTES[0];
  document.querySelectorAll(".nav__link").forEach((link) => {
    if (link.dataset.path === route.path) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  document.title = `${route.label} | AgendaMed`;

  const seq = ++renderSeq;
  const isCurrent = () => seq === renderSeq;
  Promise.resolve(route.render(mainEl, isCurrent)).then(() => {
    if (focus && isCurrent()) mainEl.querySelector(".page-title")?.focus({ preventScroll: true });
  });
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", () => navigate());
session.start();
