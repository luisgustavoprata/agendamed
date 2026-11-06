/* AgendaMed — janela de faturar consulta: particular (com preço) ou convênio.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

async function openChargeDialog(ap, onDone) {
  const data = await safe(() =>
    Promise.all([
      api.get(`/appointments/${ap.id}/charge`),
      api.get("/procedures", { active: 1 }),
      api.get("/health-plans", { active: 1 }),
      api.get("/finance/accounts"),
    ]),
  );
  if (!data) return;
  const [{ charge }, procedures, plans, accounts] = data;

  openDialog(`Faturar consulta — ${ap.patient.name}`, (close) => {
    if (charge) {
      return h(
        "div",
        { class: "form" },
        h(
          "dl",
          { class: "details" },
          h("dt", null, "Procedimento"),
          h("dd", null, charge.procedure_name || "—"),
          h("dt", null, "Convênio"),
          h("dd", null, charge.health_plan_name || "Particular"),
          h("dt", null, "Valor"),
          h("dd", null, fmtMoney(charge.amount_cents)),
          h("dt", null, "Situação"),
          h("dd", null, txStatusBadge(charge)),
        ),
        h(
          "p",
          { class: "muted" },
          "Esta consulta já foi faturada. Pagamentos e ajustes ficam em Financeiro → Lançamentos.",
        ),
        h(
          "div",
          { class: "form__actions" },
          h(
            "button",
            { class: "btn btn--primary", type: "button", onclick: close },
            "Fechar",
          ),
        ),
      );
    }
    if (procedures.items.length === 0) {
      return h(
        "div",
        { class: "form" },
        h(
          "p",
          null,
          "Cadastre ao menos um procedimento (ex.: Consulta) com o preço antes de faturar.",
        ),
        h("p", { class: "muted" }, "Vá em Gestão → Procedimentos."),
      );
    }
    const form = h(
      "form",
      { class: "form", novalidate: true },
      h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
      h(
        "div",
        { class: "form__row" },
        field({
          label: "Procedimento",
          name: "procedure_id",
          as: "select",
          value: procedures.items[0].id,
          options: procedures.items.map((p) => [
            p.id,
            `${p.name} — ${fmtMoney(p.price_cents)}`,
          ]),
        }),
        field({
          label: "Pagamento",
          name: "health_plan_id",
          as: "select",
          value: "",
          options: [
            ["", "Particular"],
            ...plans.items.map((p) => [p.id, `Convênio ${p.name}`]),
          ],
        }),
      ),
      h(
        "div",
        { class: "form__row" },
        field({
          label: "Valor (R$)",
          name: "amount_cents",
          inputmode: "decimal",
          value: centsToInput(procedures.items[0].price_cents),
        }),
        h("div", { class: "field" }),
      ),
      h(
        "div",
        { class: "form__row plan-only", hidden: true },
        field({
          label: "Nº da carteirinha",
          name: "plan_card",
          autocomplete: "off",
        }),
        field({
          label: "Nº da guia / autorização",
          name: "plan_guide",
          autocomplete: "off",
        }),
      ),
      h(
        "label",
        { class: "switch" },
        h("input", { type: "checkbox", name: "paid_now" }),
        h(
          "span",
          null,
          h("strong", null, "Já recebido"),
          h("span", { class: "muted" }, "Marque se o paciente já pagou."),
        ),
      ),
      h(
        "div",
        { class: "form__row paid-only", hidden: true },
        field({
          label: "Forma de pagamento",
          name: "payment_method",
          as: "select",
          value: "pix",
          options: Object.entries(PAYMENT_LABELS),
        }),
        field({
          label: "Conta",
          name: "account_id",
          as: "select",
          value: accounts.items[0]?.id ?? "",
          options: [
            ["", "Sem conta"],
            ...accounts.items.map((a) => [a.id, a.name]),
          ],
        }),
      ),
      formActions(close, "Faturar"),
    );

    const el = form.elements;
    el.procedure_id.addEventListener("change", () => {
      const p = procedures.items.find(
        (x) => String(x.id) === el.procedure_id.value,
      );
      el.amount_cents.value = centsToInput(p?.price_cents);
    });
    el.health_plan_id.addEventListener(
      "change",
      () =>
        (form.querySelector(".plan-only").hidden = !el.health_plan_id.value),
    );
    el.paid_now.addEventListener(
      "change",
      () => (form.querySelector(".paid-only").hidden = !el.paid_now.checked),
    );
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const v = formValues(form);
      const amount = parseMoney(v.amount_cents);
      if (amount === null) {
        showFormErrors(
          form,
          new ApiError(422, "", [
            { field: "amount_cents", message: "Informe um valor válido." },
          ]),
        );
        return;
      }
      const paid = el.paid_now.checked;
      submitForm(
        form,
        () =>
          api.post(`/appointments/${ap.id}/charge`, {
            procedure_id: Number(v.procedure_id),
            health_plan_id: v.health_plan_id ? Number(v.health_plan_id) : null,
            amount_cents: amount,
            plan_card: v.plan_card || null,
            plan_guide: v.plan_guide || null,
            paid_on: paid ? toISODate(new Date()) : null,
            payment_method: paid ? v.payment_method : null,
            account_id: paid && v.account_id ? Number(v.account_id) : null,
          }),
        () => {
          close();
          toast("Consulta faturada.");
          onDone?.();
        },
      );
    });
    return form;
  });
}
