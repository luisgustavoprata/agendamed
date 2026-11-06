/* AgendaMed — componentes reutilizáveis das telas.
 *
 * Campos de formulário (com os erros da API ao lado), título de página, tabelas,
 * paginação, janelas (diálogos) e botão de confirmação em dois cliques.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

let fieldSeq = 0;

/** Campo de formulário com rótulo, dica e área de erro ligados por acessibilidade. */
function field({
  label,
  name,
  type = "text",
  as = "input",
  hint,
  options,
  ...attrs
}) {
  const id = `f-${name}-${++fieldSeq}`;
  const errorId = `${id}-error`;
  const hintId = hint ? `${id}-hint` : null;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ");
  const common = {
    id,
    name,
    class: "input",
    "aria-describedby": describedBy,
    ...attrs,
  };

  let control;
  if (as === "select") {
    control = h(
      "select",
      common,
      options.map(([value, text]) =>
        h(
          "option",
          { value, selected: String(value) === String(attrs.value ?? "") },
          text,
        ),
      ),
    );
  } else if (as === "textarea") {
    control = h("textarea", common);
  } else {
    control = h("input", { type, ...common });
  }

  return h(
    "div",
    { class: "field" },
    h("label", { class: "field__label", for: id }, label),
    control,
    hint && h("p", { class: "field__hint", id: hintId }, hint),
    h("p", { class: "field__error", id: errorId, "data-error-for": name }),
  );
}

function clearFormErrors(form) {
  form
    .querySelectorAll("[data-error-for]")
    .forEach((el) => (el.textContent = ""));
  form
    .querySelectorAll("[aria-invalid]")
    .forEach((el) => el.removeAttribute("aria-invalid"));
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
  for (const [key, value] of new FormData(form))
    values[key] = typeof value === "string" ? value.trim() : value;
  return values;
}

function pageHead(title, subtitle, ...actions) {
  return h(
    "header",
    { class: "page-head" },
    h(
      "div",
      null,
      h("h1", { class: "page-title", tabindex: "-1" }, title),
      subtitle && h("p", { class: "page-sub" }, subtitle),
    ),
    actions.length ? h("div", { class: "toolbar" }, actions) : null,
  );
}

function loading(text = "Carregando…") {
  return h("p", { class: "loading", role: "status" }, text);
}

function dataTable({ caption, columns, rows, empty }) {
  const table = h(
    "table",
    { class: "table" },
    h("caption", { class: "visually-hidden" }, caption),
    h(
      "thead",
      null,
      h(
        "tr",
        null,
        columns.map((col) =>
          h("th", { scope: "col", class: col.class }, col.label),
        ),
      ),
    ),
    h(
      "tbody",
      null,
      rows.length
        ? rows.map((row) =>
            h(
              "tr",
              null,
              columns.map((col) =>
                h("td", { class: col.class }, col.render(row)),
              ),
            ),
          )
        : h(
            "tr",
            null,
            h("td", { colspan: columns.length, class: "table__empty" }, empty),
          ),
    ),
  );
  return h("div", { class: "table-wrap" }, table);
}

function pager(page, onChange) {
  if (page.total === 0) return null;
  const from = page.offset + 1;
  const to = page.offset + page.items.length;
  return h(
    "nav",
    { class: "pager", "aria-label": "Paginação" },
    h("span", null, `Mostrando ${from}–${to} de ${page.total}`),
    h(
      "div",
      { class: "pager__btns" },
      h(
        "button",
        {
          class: "btn btn--ghost btn--small",
          type: "button",
          disabled: page.offset === 0,
          onclick: () => onChange(Math.max(0, page.offset - page.limit)),
        },
        "Anterior",
      ),
      h(
        "button",
        {
          class: "btn btn--ghost btn--small",
          type: "button",
          disabled: to >= page.total,
          onclick: () => onChange(page.offset + page.limit),
        },
        "Próxima",
      ),
    ),
  );
}

function openDialog(title, buildBody) {
  const titleId = `dlg-${++fieldSeq}`;
  const dialog = h("dialog", { class: "dialog", "aria-labelledby": titleId });
  const close = () => dialog.close();
  dialog.addEventListener("close", () => dialog.remove());
  dialog.append(
    h(
      "div",
      { class: "dialog__inner" },
      h(
        "div",
        { class: "dialog__head" },
        h("h2", { class: "dialog__title", id: titleId }, title),
        h(
          "button",
          {
            class: "btn btn--ghost btn--icon",
            type: "button",
            "aria-label": "Fechar",
            onclick: close,
          },
          icon("close"),
        ),
      ),
      buildBody(close),
    ),
  );
  document.body.append(dialog);
  dialog.showModal();
  dialog.querySelector("input, select, textarea")?.focus();
  return close;
}

/** Botão de ação destrutiva com confirmação em dois cliques (sem janelas do navegador). */
function confirmButton(label, confirmLabel, onConfirm, extraClass = "") {
  let timer;
  const btn = h(
    "button",
    { class: `btn btn--danger ${extraClass}`.trim(), type: "button" },
    label,
  );
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
