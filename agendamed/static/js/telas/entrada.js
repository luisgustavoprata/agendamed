/* AgendaMed — tela de entrada da Clínica Vida (login e criar conta).
 *
 * A faixa de cima traz a marca da clínica, uma saudação conforme a hora e o traço de
 * eletrocardiograma; o rodapé, a assinatura da Argentum Software.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

/** Marca da Argentum Software (versão clara) no canto da área verde do login. */
function argentumMark() {
  const svg = (tag, attrs) => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    return node;
  };
  const icon = svg("svg", {
    viewBox: "0 0 64 64",
    class: "argentum__icon",
    "aria-hidden": "true",
  });
  icon.append(
    svg("rect", { x: 0, y: 0, width: 64, height: 64, rx: 15, fill: "#0E1A24" }),
    svg("polygon", { points: "10,54 25,12 33,12 19,54", fill: "#FFFFFF" }),
    svg("polygon", { points: "36,24 44,24 54,54 46,54", fill: "#FFFFFF" }),
    svg("rect", {
      x: 37,
      y: 10,
      width: 9,
      height: 9,
      rx: 1.5,
      fill: "#3FD8C2",
    }),
  );
  return h(
    "div",
    { class: "argentum", role: "img", "aria-label": "Argentum Software" },
    icon,
    h(
      "span",
      { class: "argentum__words", "aria-hidden": "true" },
      h("span", { class: "argentum__name" }, "Argentum"),
      h("span", { class: "argentum__sub" }, "SOFTWARE"),
    ),
  );
}

function renderLogin() {
  // Na tela de entrada o endereço fica limpo (sem "#/financeiro" de uma visita anterior).
  if (location.hash)
    history.replaceState(null, "", `${location.pathname}${location.search}`);
  document.title = `Entrar | ${CLINIC_BRAND.name}`;
  let mode = "login";

  const card = h("div", { class: "login__card login__card--boxed" });
  const panel = h(
    "main",
    { class: "login__center" },
    card,
    h(
      "p",
      { class: "login__powered" },
      "tecnologia",
      h("img", { src: "/static/icon.svg", alt: "" }),
      h("strong", null, "AgendaMed"),
    ),
    h(
      "p",
      { class: "login__trust" },
      h("span", null, icon("shield"), "Conexão protegida por HTTPS"),
      h("span", null, icon("lock"), "Acesso restrito à equipe"),
    ),
  );
  // Começa fechado: a aba "Criar conta" só aparece se o servidor disser que o cadastro está
  // aberto (antes ela piscava na tela enquanto o /health não respondia).
  let signupOpen = false;

  // Com o cadastro fechado (ALLOW_SIGNUP=false), o servidor avisa pelo /health e a aba
  // "Criar conta" some: só entra quem tem acesso criado pela clínica.
  api
    .get("/health")
    .then((info) => {
      signupOpen = info?.signup === true;
      if (signupOpen && mode === "login") draw();
    })
    .catch(() => {});

  /** "Esqueci minha senha": nesta versão as senhas da equipe vêm do responsável (variáveis
   * do servidor), então a tela explica com quem falar em vez de mandar e-mail. */
  function drawForgot() {
    const phone = CLINIC_BRAND.phone;
    fill(
      card,
      h(
        "div",
        { class: "vida-card-head" },
        h("h2", { class: "vida-card-head__title" }, "Esqueceu a senha?"),
        h(
          "p",
          { class: "vida-card-head__sub" },
          "Sem problema. Quem cria e redefine as senhas da equipe é o responsável pela clínica.",
        ),
      ),
      h(
        "ol",
        { class: "forgot-steps" },
        h(
          "li",
          null,
          h("strong", null, "Fale com o responsável"),
          h("span", null, "Peça uma senha nova para o seu e-mail de acesso."),
        ),
        h(
          "li",
          null,
          h("strong", null, "Ele redefine a senha"),
          h(
            "span",
            null,
            "No painel do servidor, onde ficam as contas da equipe.",
          ),
        ),
        h(
          "li",
          null,
          h("strong", null, "Entre com a senha nova"),
          h("span", null, "Ela já vale no próximo acesso."),
        ),
      ),
      h(
        "div",
        { class: "forgot-contact" },
        icon("phone"),
        h(
          "div",
          null,
          h("p", { class: "forgot-contact__label" }, "Recepção da clínica"),
          h("a", { href: `tel:+55${phone.replace(/\D/g, "")}` }, phone),
        ),
      ),
      h(
        "button",
        {
          class: "btn btn--primary btn--block",
          type: "button",
          onclick: () => switchTo("login"),
        },
        "Voltar para entrar",
      ),
    );
  }

  function draw() {
    if (mode === "forgot") return drawForgot();
    const isLogin = mode === "login";
    const tabs =
      signupOpen &&
      h(
        "div",
        { class: "tabs", role: "tablist", "aria-label": "Acesso" },
        h(
          "button",
          {
            class: "tabs__btn",
            type: "button",
            role: "tab",
            "aria-selected": String(isLogin),
            onclick: () => switchTo("login"),
          },
          "Entrar",
        ),
        h(
          "button",
          {
            class: "tabs__btn",
            type: "button",
            role: "tab",
            "aria-selected": String(!isLogin),
            onclick: () => switchTo("register"),
          },
          "Criar conta",
        ),
      );

    const form = h(
      "form",
      { class: "form", novalidate: true },
      h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
      !isLogin &&
        field({
          label: "Nome completo",
          name: "full_name",
          autocomplete: "name",
          required: true,
        }),
      field({
        label: "E-mail",
        name: "email",
        type: "email",
        autocomplete: "email",
        required: true,
      }),
      field({
        label: "Senha",
        name: "password",
        type: "password",
        required: true,
        autocomplete: isLogin ? "current-password" : "new-password",
        hint: isLogin ? null : "Mínimo de 8 caracteres",
      }),
      h(
        "button",
        {
          class: "btn btn--primary btn--block",
          type: "submit",
        },
        isLogin ? "Entrar" : "Criar conta",
      ),
      isLogin &&
        h(
          "button",
          {
            class: "link-btn forgot-link",
            type: "button",
            onclick: () => switchTo("forgot"),
          },
          "Esqueci minha senha",
        ),
    );

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

    fill(
      card,
      h(
        "div",
        { class: "vida-card-head" },
        h(
          "h2",
          { class: "vida-card-head__title" },
          isLogin ? "Acesso da equipe" : "Criar conta",
        ),
        h(
          "p",
          { class: "vida-card-head__sub" },
          isLogin
            ? "Use o e-mail e a senha que a clínica criou para você."
            : "Cadastre-se para usar a agenda da clínica.",
        ),
      ),
      h(
        "h1",
        { class: "visually-hidden" },
        `Entrar na agenda da ${CLINIC_BRAND.name}`,
      ),
      !isLogin &&
        h(
          "p",
          { class: "login__sub" },
          "Use um e-mail que você acessa. A senha precisa ter ao menos 8 caracteres.",
        ),
      tabs,
      form,
    );
  }

  function switchTo(next) {
    mode = next;
    draw();
    card.querySelector("input")?.focus();
  }

  draw();
  fill(
    root(),
    h(
      "div",
      { class: "login login--clinic login--vida" },
      h("div", { class: "vida-band", "aria-hidden": "true" }, ecgTrace()),
      vidaTop(),
      vidaGreeting(),
      panel,
      h(
        "footer",
        { class: "login__signature" },
        argentumMark(),
        h(
          "p",
          { class: "vida-legal" },
          `© ${new Date().getFullYear()} ${CLINIC_BRAND.name} · clínica de demonstração do AgendaMed`,
        ),
      ),
    ),
  );
  enhancePasswords(card);
}

/** Faixa de cima: a clínica à esquerda, o contato à direita. */
function vidaTop() {
  return h(
    "header",
    { class: "vida-top" },
    h(
      "div",
      { class: "vida-top__brand" },
      h(
        "span",
        { class: "vida-top__logo", "aria-hidden": "true" },
        CLINIC_BRAND.initials,
      ),
      h(
        "div",
        null,
        h("p", { class: "vida-top__name" }, CLINIC_BRAND.name),
        h("p", { class: "vida-top__sub" }, CLINIC_BRAND.specialties),
      ),
    ),
    h(
      "div",
      { class: "vida-top__contact" },
      h("span", null, icon("phone"), CLINIC_BRAND.phone),
      h("span", null, icon("pin"), CLINIC_BRAND.address),
    ),
  );
}

/** "Bom dia, equipe." com a data de hoje, por cima do cartão. */
function vidaGreeting() {
  const now = new Date();
  const hour = now.getHours();
  const hello = hour < 12 ? "Bom dia" : hour < 18 ? "Boa tarde" : "Boa noite";
  const date = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(now);
  return h(
    "section",
    { class: "vida-hello" },
    h("p", { class: "vida-hello__title" }, `${hello}, equipe.`),
    h(
      "p",
      { class: "vida-hello__date" },
      date.charAt(0).toUpperCase() + date.slice(1),
    ),
  );
}

/** Traço fino de eletrocardiograma na faixa (aparece da esquerda para a direita). */
function ecgTrace() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 1440 160");
  svg.setAttribute("preserveAspectRatio", "none");
  const path = document.createElementNS(ns, "path");
  const beat = (x) =>
    `L${x} 96 Q${x + 14} 86 ${x + 28} 96 L${x + 46} 96 L${x + 54} 104 L${x + 66} 30 L${x + 78} 124 L${x + 88} 96 L${x + 112} 96 Q${x + 134} 76 ${x + 156} 96`;
  path.setAttribute(
    "d",
    `M0 96 L96 96 ${beat(96)} L1160 96 ${beat(1160)} L1440 96`,
  );
  svg.append(path);
  // A linha já nasce visível; a revelação só roda com a página na tela, e some em 3 s de
  // qualquer jeito (em aba de fundo a animação fica parada).
  const reveal = document.visibilityState === "visible";
  const trace = h("div", { class: reveal ? "ecg ecg--reveal" : "ecg" }, svg);
  if (reveal) setTimeout(() => trace.classList.remove("ecg--reveal"), 3000);
  return trace;
}

/** Senha: botão para mostrar/esconder e aviso de Caps Lock ligado. */
function enhancePasswords(scope) {
  const apply = () =>
    scope
      .querySelectorAll('input[type="password"]:not([data-enhanced])')
      .forEach((input) => {
        input.dataset.enhanced = "1";
        const wrap = h("div", { class: "pw-field" });
        input.replaceWith(wrap);
        const toggle = h(
          "button",
          {
            class: "pw-field__toggle",
            type: "button",
            "aria-label": "Mostrar senha",
            title: "Mostrar senha",
          },
          icon("eye"),
        );
        toggle.addEventListener("click", () => {
          const show = input.type === "password";
          input.type = show ? "text" : "password";
          toggle.setAttribute(
            "aria-label",
            show ? "Esconder senha" : "Mostrar senha",
          );
          toggle.title = toggle.getAttribute("aria-label");
          fill(toggle, icon(show ? "eyeOff" : "eye"));
          input.focus();
        });
        const caps = h(
          "p",
          { class: "pw-field__caps", hidden: true, "aria-live": "polite" },
          "Caps Lock está ligado.",
        );
        const check = (e) => (caps.hidden = !e.getModifierState?.("CapsLock"));
        input.addEventListener("keydown", check);
        input.addEventListener("keyup", check);
        input.addEventListener("blur", () => (caps.hidden = true));
        wrap.append(input, toggle);
        wrap.after(caps);
      });
  apply();
  // O cartão é redesenhado (entrar, criar conta, esqueci a senha): aplica de novo.
  new MutationObserver(apply).observe(scope, {
    childList: true,
    subtree: true,
  });
}
