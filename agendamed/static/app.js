/* AgendaMed — interface da Clínica Vida: ponto de partida (carregado por último).
 *
 *
 * Aqui ficam o menu (ROUTES), a moldura das telas (renderShell), a troca de tela pelo
 * endereço (#/agenda, #/pacientes...) e a inicialização. As telas e as peças que elas
 * usam estão em js/ (veja a lista e a ordem de carga no index.html):
 *
 *   js/base/      utilitários, dias úteis, marca, API, sessão e componentes
 *   js/dialogos/  janelas de cadastro (médico e paciente)
 *   js/telas/     uma tela por arquivo (entrada, agendar, agenda, consultas...)
 *   js/gestao/    prontuário, prescrições, financeiro, estoque e painel de gestão
 *
 * JavaScript puro, sem etapa de build: o navegador roda estes arquivos como estão.
 */
"use strict";

const ROUTES = [
  { path: "agendar", label: "Agendar", icon: "book", render: renderBooking },
  { path: "agenda", label: "Agenda", icon: "calendar", render: renderAgenda },
  {
    path: "consultas",
    label: "Consultas",
    icon: "list",
    render: renderAppointments,
  },
  { path: "medicos", label: "Médicos", icon: "doctor", render: renderDoctors },
  {
    path: "pacientes",
    label: "Pacientes",
    icon: "users",
    render: renderPatients,
  },
  {
    path: "financeiro",
    label: "Financeiro",
    icon: "money",
    render: renderFinance,
  },
  { path: "estoque", label: "Estoque", icon: "box", render: renderStock },
  { path: "gestao", label: "Gestão", icon: "chart", render: renderManagement },
];

let renderSeq = 0;
let mainEl = null;

function renderShell() {
  const nav = h(
    "nav",
    { class: "nav", "aria-label": "Principal" },
    ROUTES.map((r) =>
      h(
        "a",
        { class: "nav__link", href: `#/${r.path}`, "data-path": r.path },
        icon(r.icon),
        h("span", null, r.label),
      ),
    ),
  );

  const sidebar = h(
    "header",
    { class: "sidebar" },
    h(
      "a",
      { class: "brand", href: "#/agendar" },
      h("img", { src: "/static/icon.svg", alt: "" }),
      h("span", null, "AgendaMed"),
    ),
    nav,
    h(
      "div",
      { class: "sidebar__foot" },
      h(
        "a",
        {
          class: "sidebar__docs",
          href: "/docs",
          target: "_blank",
          rel: "noopener",
        },
        "Documentação da API",
      ),
      h(
        "div",
        { class: "sidebar__user" },
        h(
          "span",
          { class: "avatar", "aria-hidden": "true" },
          initials(state.user.full_name),
        ),
        h(
          "div",
          null,
          h(
            "p",
            { class: "sidebar__user-name", title: state.user.full_name },
            state.user.full_name,
          ),
          h(
            "p",
            { class: "sidebar__user-email", title: state.user.email },
            state.user.email,
          ),
        ),
        h(
          "button",
          {
            class: "btn btn--ghost btn--small",
            type: "button",
            onclick: () => session.logout(),
          },
          icon("logout"),
          "Sair",
        ),
      ),
    ),
  );

  mainEl = h("main", { class: "main", id: "main" });
  fill(root(), h("div", { class: "shell" }, sidebar, mainEl));
  navigate({ focus: false });
}

function navigate({ focus = true } = {}) {
  if (!state.user || !mainEl) return;
  const path = location.hash.replace(/^#\/?/, "") || "agendar";
  const route = ROUTES.find((r) => r.path === path) || ROUTES[0];
  document.querySelectorAll(".nav__link").forEach((link) => {
    if (link.dataset.path === route.path)
      link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  document.title = `${route.label} | AgendaMed`;

  const seq = ++renderSeq;
  const isCurrent = () => seq === renderSeq;
  Promise.resolve(route.render(mainEl, isCurrent)).then(() => {
    if (focus && isCurrent())
      mainEl.querySelector(".page-title")?.focus({ preventScroll: true });
  });
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", () => navigate());
applyClinicTheme(CLINIC_BRAND.colors);
session.start();
