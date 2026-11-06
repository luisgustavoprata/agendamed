/* AgendaMed — telas de gestão: prontuário, prescrições, financeiro, estoque e painel.
 *
 * Carregado ANTES do app.js e usa os utilitários dele (h, api, field, openDialog...)
 * somente dentro das funções, que só rodam depois que tudo carregou.
 * Como no app.js, todo texto vindo da API entra no DOM como texto (nunca innerHTML).
 */
"use strict";

/* ===================== Utilitários ===================== */

const moneyFmt = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
const fmtMoney = (cents) => moneyFmt.format((cents || 0) / 100);

/** "1.234,56", "1234.56" ou "300" → centavos. Devolve null se não for um valor válido. */
function parseMoney(text) {
  let raw = String(text ?? "").replace(/[^\d,.-]/g, "");
  if (!raw) return null;
  if (raw.includes(",")) raw = raw.replace(/\./g, "").replace(",", ".");
  const value = Number(raw);
  return Number.isFinite(value) && value >= 0 ? Math.round(value * 100) : null;
}

const centsToInput = (cents) =>
  cents ? (cents / 100).toFixed(2).replace(".", ",") : "";
const fmtDate = (iso) =>
  iso ? fmtShortDate(parseISODate(iso.slice(0, 10))) : "—";
const fmtDateTime = (iso) =>
  iso ? `${fmtDate(iso)} ${iso.slice(11, 16)}` : "—";

const PAYMENT_LABELS = {
  dinheiro: "Dinheiro",
  pix: "Pix",
  cartao_credito: "Cartão de crédito",
  cartao_debito: "Cartão de débito",
  boleto: "Boleto",
  transferencia: "Transferência",
  convenio: "Convênio",
};
const RECORD_KIND_OPTIONS = [
  ["evolucao", "Evolução"],
  ["anamnese", "Anamnese"],
  ["exame_fisico", "Exame físico"],
  ["diagnostico", "Hipótese diagnóstica"],
  ["conduta", "Conduta"],
  ["exame", "Resultado de exame"],
  ["anotacao", "Anotação"],
];
const RX_KIND_OPTIONS = [
  ["simples", "Receituário simples"],
  ["controle_especial", "Receituário de controle especial"],
  ["atestado", "Atestado médico"],
  ["exames", "Solicitação de exames"],
  ["relatorio", "Relatório médico"],
];
const BLOOD_TYPES = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
/* Nesta versão não há perfis: toda a equipe usa todas as telas. */
const isOwner = () => true;
const isDoctorUser = () => false;
const clinicName = () => CLINIC_BRAND.name;

/** Mês escolhido (AAAA-MM) → início e fim, no formato da API. */
function monthRange(month) {
  const [y, m] = month.split("-").map(Number);
  return {
    start: toISODate(new Date(y, m - 1, 1)),
    end: toISODate(new Date(y, m, 0)),
  };
}
const currentMonth = () => toISODate(new Date()).slice(0, 7);

function monthPicker(value, onChange) {
  const wrap = field({ label: "Mês", name: "month", type: "month", value });
  wrap
    .querySelector("input")
    .addEventListener(
      "change",
      (e) => e.target.value && onChange(e.target.value),
    );
  return wrap;
}

/** Abas internas de uma tela. `tabs`: [[chave, rótulo], ...]. */
function subTabs(tabs, active, onPick) {
  return h(
    "div",
    { class: "subtabs", role: "tablist" },
    tabs.filter(Boolean).map(([key, label]) =>
      h(
        "button",
        {
          class: "subtabs__btn",
          type: "button",
          role: "tab",
          "aria-selected": String(key === active),
          onclick: () => onPick(key),
        },
        label,
      ),
    ),
  );
}

function stat(label, value, tone = "") {
  return h(
    "div",
    { class: `stat ${tone ? `stat--${tone}` : ""}` },
    h("p", { class: "stat__label" }, label),
    h("p", { class: "stat__value" }, value),
  );
}

/** Barra horizontal simples (proporção do maior valor). */
function bar(value, max, tone = "") {
  const pct = max > 0 ? Math.max(2, Math.round((100 * value) / max)) : 0;
  return h("span", {
    class: `bar ${tone ? `bar--${tone}` : ""}`,
    style: `--w:${pct}%`,
    "aria-hidden": "true",
  });
}

async function safe(fn) {
  try {
    return await fn();
  } catch (err) {
    handleError(err);
    return null;
  }
}

async function submitForm(form, request, onOk) {
  const submit = form.querySelector('[type="submit"]');
  if (submit) submit.disabled = true;
  clearFormErrors(form);
  try {
    const result = await request();
    onOk(result);
  } catch (err) {
    if (err.status !== 401) showFormErrors(form, err);
  } finally {
    if (submit) submit.disabled = false;
  }
}

function formActions(close, label) {
  return h(
    "div",
    { class: "form__actions" },
    h(
      "button",
      { class: "btn btn--ghost", type: "button", onclick: close },
      "Cancelar",
    ),
    h("button", { class: "btn btn--primary", type: "submit" }, label),
  );
}

/* ---------- Impressão ---------- */

/** Mostra só `doc` na impressão e abre a janela de imprimir do navegador. */
function printDocument(doc) {
  const area = h("div", { class: "print-area" }, doc);
  document.body.append(area);
  document.body.classList.add("is-printing");
  const done = () => {
    document.body.classList.remove("is-printing");
    area.remove();
    window.removeEventListener("afterprint", done);
  };
  window.addEventListener("afterprint", done);
  setTimeout(() => window.print(), 50);
}

function printPrescription(rx) {
  const kindTitle = rx.kind_label.toUpperCase();
  const doc = h(
    "article",
    { class: "print-doc" },
    h(
      "header",
      { class: "print-doc__head" },
      h("p", { class: "print-doc__clinic" }, clinicName()),
      h("p", null, `${CLINIC_BRAND.address} · Telefone: ${CLINIC_BRAND.phone}`),
      h(
        "p",
        null,
        `${rx.doctor_name} · ${rx.doctor_specialty} · CRM ${rx.doctor_crm}`,
      ),
    ),
    h("h1", { class: "print-doc__title" }, kindTitle),
    rx.kind === "controle_especial" &&
      h(
        "p",
        { class: "print-doc__note" },
        "1ª via: farmácia · 2ª via: paciente",
      ),
    h(
      "dl",
      { class: "print-doc__patient" },
      h("dt", null, "Paciente"),
      h("dd", null, rx.patient_name),
      h("dt", null, "CPF"),
      h("dd", null, maskCpf(rx.patient_cpf)),
      h("dt", null, "Nascimento"),
      h("dd", null, fmtDate(rx.patient_birth_date)),
    ),
    rx.items.length > 0 &&
      h(
        "ol",
        { class: "print-doc__items" },
        rx.items.map((item) =>
          h(
            "li",
            null,
            h(
              "p",
              null,
              h("strong", null, item.name),
              item.dosage ? ` — ${item.dosage}` : "",
            ),
            item.instructions && h("p", null, item.instructions),
          ),
        ),
      ),
    rx.text && h("p", { class: "print-doc__text" }, rx.text),
    h(
      "footer",
      { class: "print-doc__sign" },
      h("p", null, `Emitido em ${fmtDate(rx.created_at)}`),
      h("p", { class: "print-doc__line" }, rx.doctor_name),
      h("p", null, `CRM ${rx.doctor_crm}`),
    ),
  );
  printDocument(doc);
}

function printTissBatch(batch) {
  const row = (label, value) =>
    h(
      "div",
      { class: "guide-cell" },
      h("dt", null, label),
      h("dd", null, value || "—"),
    );
  const guides = batch.guides.map((g, i) =>
    h(
      "article",
      { class: "print-doc print-doc--guide" },
      h("h1", { class: "print-doc__title" }, "GUIA DE CONSULTA"),
      h(
        "p",
        { class: "print-doc__note" },
        `Guia ${i + 1} de ${batch.guides.length}`,
      ),
      h(
        "dl",
        { class: "guide-grid" },
        row("1 - Registro ANS", batch.health_plan.ans_code),
        row("2 - Nº da guia", g.plan_guide),
        row("Operadora", batch.health_plan.name),
        row("4 - Nº da carteira", g.plan_card),
        row("7 - Nome do beneficiário", g.patient_name),
        row("CPF", maskCpf(g.patient_cpf)),
        row("Nascimento", fmtDate(g.patient_birth_date)),
        row("10 - Contratado", clinicName()),
        row("12 - Profissional executante", g.doctor_name),
        row("14 - Conselho / Nº", `CRM ${g.doctor_crm}`),
        row("Especialidade", g.doctor_specialty),
        row("17 - Data do atendimento", fmtDate(g.start_at)),
        row("19 - Código do procedimento (TUSS)", g.procedure_tuss),
        row("Procedimento", g.procedure_name),
        row("20 - Valor", fmtMoney(g.amount_cents)),
      ),
      h(
        "p",
        { class: "print-doc__line print-doc__line--wide" },
        "Assinatura do beneficiário",
      ),
    ),
  );
  printDocument(
    h(
      "div",
      null,
      h(
        "header",
        { class: "print-doc print-doc__head" },
        h(
          "p",
          { class: "print-doc__clinic" },
          `Lote de guias — ${batch.health_plan.name}`,
        ),
        h(
          "p",
          null,
          `${fmtDate(batch.start)} a ${fmtDate(batch.end)} · ${plural(batch.guides.length, "guia", "guias")} · ${fmtMoney(batch.total_cents)}`,
        ),
      ),
      guides,
    ),
  );
}

/* ===================== Prontuário e prescrições ===================== */

async function openRecordDialog(patient) {
  const doctors = isOwner() ? await safe(() => getDoctors()) : [];
  if (doctors === null) return;
  let tab = "registros";

  openDialog(
    `Prontuário — ${patient.name}`,
    (close) => {
      const body = h("div", { class: "record" }, loading());
      const tabs = h("div");
      const drawTabs = () =>
        fill(
          tabs,
          subTabs(
            [
              ["registros", "Registros"],
              ["ficha", "Ficha clínica"],
              ["prescricoes", "Prescrições"],
            ],
            tab,
            (key) => {
              tab = key;
              drawTabs();
              load();
            },
          ),
        );
      drawTabs();

      const doctorPicker = () =>
        isOwner() &&
        doctors.length > 0 &&
        field({
          label: "Médico responsável",
          name: "doctor_id",
          as: "select",
          value: doctors.length === 1 ? doctors[0].id : "",
          options: [["", "Escolha"], ...doctors.map((d) => [d.id, d.name])],
        });

      async function load() {
        fill(body, loading());
        if (tab === "prescricoes") {
          const data = await safe(() =>
            api.get(`/patients/${patient.id}/prescriptions`),
          );
          if (data) drawPrescriptions(data.items);
          return;
        }
        const record = await safe(() =>
          api.get(`/patients/${patient.id}/record`),
        );
        if (!record) return;
        if (tab === "ficha") drawSummary(record.summary);
        else drawEntries(record);
      }

      function drawEntries(record) {
        const s = record.summary;
        const form = h(
          "form",
          { class: "form", novalidate: true },
          h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
          h(
            "div",
            { class: "form__row" },
            field({
              label: "Tipo de registro",
              name: "kind",
              as: "select",
              value: "evolucao",
              options: RECORD_KIND_OPTIONS,
            }),
            doctorPicker(),
          ),
          field({
            label: "Texto",
            name: "content",
            as: "textarea",
            rows: 5,
            required: true,
          }),
          h(
            "div",
            { class: "form__actions" },
            h(
              "button",
              { class: "btn btn--primary", type: "submit" },
              "Salvar no prontuário",
            ),
          ),
        );
        form.addEventListener("submit", (e) => {
          e.preventDefault();
          const v = formValues(form);
          submitForm(
            form,
            () =>
              api.post(`/patients/${patient.id}/record/entries`, {
                kind: v.kind,
                content: v.content,
                doctor_id: v.doctor_id ? Number(v.doctor_id) : null,
              }),
            () => {
              toast("Registro salvo no prontuário.");
              load();
            },
          );
        });
        fill(
          body,
          (s.allergies || s.conditions) &&
            h(
              "div",
              { class: "alert-box" },
              s.allergies &&
                h("p", null, h("strong", null, "Alergias: "), s.allergies),
              s.conditions &&
                h("p", null, h("strong", null, "Doenças: "), s.conditions),
            ),
          form,
          h(
            "p",
            { class: "muted small" },
            "Os registros não podem ser apagados nem alterados. Para corrigir, faça um registro novo.",
          ),
          h(
            "ol",
            { class: "timeline" },
            record.entries.length === 0
              ? h("li", { class: "muted" }, "Nenhum registro ainda.")
              : record.entries.map((e) =>
                  h(
                    "li",
                    { class: "timeline__item" },
                    h(
                      "p",
                      { class: "timeline__meta" },
                      h("strong", null, e.kind_label),
                      ` · ${fmtDateTime(e.created_at)} · `,
                      e.doctor_name || e.author,
                    ),
                    h("p", { class: "timeline__text" }, e.content),
                  ),
                ),
          ),
        );
      }

      function drawSummary(s) {
        const form = h(
          "form",
          { class: "form", novalidate: true },
          h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
          field({
            label: "Alergias",
            name: "allergies",
            as: "textarea",
            rows: 2,
            hint: "Ex.: dipirona, penicilina, látex",
          }),
          field({
            label: "Doenças e condições",
            name: "conditions",
            as: "textarea",
            rows: 2,
            hint: "Ex.: hipertensão, diabetes tipo 2",
          }),
          field({
            label: "Medicamentos em uso",
            name: "medications",
            as: "textarea",
            rows: 2,
          }),
          field({
            label: "Tipo sanguíneo",
            name: "blood_type",
            as: "select",
            value: s.blood_type || "",
            options: BLOOD_TYPES.map((b) => [b, b || "Não informado"]),
          }),
          field({
            label: "Observações",
            name: "notes",
            as: "textarea",
            rows: 3,
          }),
          s.updated_at &&
            h(
              "p",
              { class: "muted small" },
              `Atualizada em ${fmtDateTime(s.updated_at)} por ${s.updated_by}`,
            ),
          h(
            "div",
            { class: "form__actions" },
            h(
              "button",
              { class: "btn btn--primary", type: "submit" },
              "Salvar ficha",
            ),
          ),
        );
        for (const name of ["allergies", "conditions", "medications", "notes"])
          form.elements[name].value = s[name] || "";
        form.addEventListener("submit", (e) => {
          e.preventDefault();
          const v = formValues(form);
          const payload = Object.fromEntries(
            Object.entries(v).map(([k, val]) => [k, val || null]),
          );
          submitForm(
            form,
            () => api.put(`/patients/${patient.id}/record/summary`, payload),
            () => toast("Ficha clínica salva."),
          );
        });
        fill(body, form);
      }

      function drawPrescriptions(items) {
        const itemsBox = h("div", { class: "rx-items" });
        const addItem = () =>
          itemsBox.append(
            h(
              "div",
              { class: "rx-item" },
              field({
                label: "Medicamento ou exame",
                name: "item_name",
                autocomplete: "off",
              }),
              field({
                label: "Quantidade / dose",
                name: "item_dosage",
                autocomplete: "off",
                placeholder: "Ex.: 500 mg, 1 caixa",
              }),
              field({
                label: "Como usar",
                name: "item_instructions",
                autocomplete: "off",
                placeholder: "Ex.: 1 comprimido de 8/8h por 7 dias",
              }),
            ),
          );
        addItem();
        const form = h(
          "form",
          { class: "form", novalidate: true },
          h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
          h(
            "div",
            { class: "form__row" },
            field({
              label: "Tipo",
              name: "kind",
              as: "select",
              value: "simples",
              options: RX_KIND_OPTIONS,
            }),
            doctorPicker(),
          ),
          itemsBox,
          h(
            "button",
            {
              class: "btn btn--ghost btn--small",
              type: "button",
              style: "justify-self:start",
              onclick: addItem,
            },
            icon("plus"),
            "Adicionar item",
          ),
          field({
            label: "Texto livre",
            name: "text",
            as: "textarea",
            rows: 3,
            hint: 'Para atestados (ex.: "Atesto para os devidos fins que...") ou observações.',
          }),
          h(
            "div",
            { class: "form__actions" },
            h(
              "button",
              { class: "btn btn--primary", type: "submit" },
              "Emitir e imprimir",
            ),
          ),
        );
        form.addEventListener("submit", (e) => {
          e.preventDefault();
          const v = formValues(form);
          const rows = [...itemsBox.querySelectorAll(".rx-item")]
            .map((el) => ({
              name: el.querySelector('[name="item_name"]').value.trim(),
              dosage:
                el.querySelector('[name="item_dosage"]').value.trim() || null,
              instructions:
                el.querySelector('[name="item_instructions"]').value.trim() ||
                null,
            }))
            .filter((item) => item.name);
          submitForm(
            form,
            () =>
              api.post(`/patients/${patient.id}/prescriptions`, {
                kind: v.kind,
                items: rows,
                text: v.text || null,
                doctor_id: v.doctor_id ? Number(v.doctor_id) : null,
              }),
            (rx) => {
              toast(`${rx.kind_label} emitido.`);
              printPrescription(rx);
              load();
            },
          );
        });
        fill(
          body,
          form,
          h("h3", { class: "dialog__subtitle" }, "Emitidas"),
          dataTable({
            caption: "Prescrições do paciente",
            empty: "Nenhuma prescrição emitida.",
            rows: items,
            columns: [
              {
                label: "Data",
                class: "num",
                render: (rx) => fmtDate(rx.created_at),
              },
              { label: "Tipo", render: (rx) => rx.kind_label },
              {
                label: "Conteúdo",
                render: (rx) =>
                  rx.items.map((i) => i.name).join(", ") ||
                  (rx.text || "").slice(0, 60),
              },
              { label: "Médico", render: (rx) => rx.doctor_name },
              {
                label: "Ações",
                class: "actions",
                render: (rx) =>
                  h(
                    "button",
                    {
                      class: "btn btn--ghost btn--small",
                      type: "button",
                      onclick: () => printPrescription(rx),
                    },
                    "Imprimir",
                  ),
              },
            ],
          }),
        );
      }

      load();
      return h("div", { class: "form" }, tabs, body);
    },
    { wide: true },
  );
}

/* ===================== Faturar consulta ===================== */

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

/* ===================== Financeiro ===================== */

function txStatusBadge(tx) {
  const map = {
    paid: ["completed", tx.kind === "income" ? "Recebido" : "Pago"],
    open: ["scheduled", "Em aberto"],
    overdue: ["cancelled", "Vencido"],
  };
  const [tone, label] = map[tx.status];
  return h("span", { class: `badge badge--${tone}` }, label);
}

function openTransactionDialog(onSaved, accounts, kind = "income") {
  openDialog(kind === "income" ? "Nova receita" : "Nova despesa", (close) => {
    const form = h(
      "form",
      { class: "form", novalidate: true },
      h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
      field({
        label: "Descrição",
        name: "description",
        required: true,
        autocomplete: "off",
      }),
      h(
        "div",
        { class: "form__row" },
        field({
          label: "Categoria",
          name: "category",
          required: true,
          list: "tx-categories",
          hint:
            kind === "income"
              ? "Ex.: Consultas particulares, Convênio"
              : "Ex.: Aluguel, Salários, Materiais, Impostos",
        }),
        field({
          label: "Valor (R$)",
          name: "amount_cents",
          required: true,
          inputmode: "decimal",
        }),
      ),
      h(
        "div",
        { class: "form__row" },
        field({
          label: "Vencimento",
          name: "due_date",
          type: "date",
          required: true,
          value: toISODate(new Date()),
        }),
        field({
          label: "Conta",
          name: "account_id",
          as: "select",
          value: accounts[0]?.id ?? "",
          options: [["", "Sem conta"], ...accounts.map((a) => [a.id, a.name])],
        }),
      ),
      h(
        "label",
        { class: "switch" },
        h("input", { type: "checkbox", name: "paid_now" }),
        h(
          "span",
          null,
          h("strong", null, kind === "income" ? "Já recebido" : "Já pago"),
        ),
      ),
      field({
        label: "Forma de pagamento",
        name: "payment_method",
        as: "select",
        value: "pix",
        options: Object.entries(PAYMENT_LABELS),
      }),
      h(
        "datalist",
        { id: "tx-categories" },
        [
          "Consultas particulares",
          "Convênio",
          "Aluguel",
          "Salários",
          "Materiais",
          "Impostos",
          "Contas de consumo",
          "Marketing",
          "Outros",
        ].map((c) => h("option", { value: c })),
      ),
      formActions(close, "Salvar"),
    );
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const v = formValues(form);
      const amount = parseMoney(v.amount_cents);
      if (!amount) {
        showFormErrors(
          form,
          new ApiError(422, "", [
            {
              field: "amount_cents",
              message: "Informe um valor maior que zero.",
            },
          ]),
        );
        return;
      }
      const paid = form.elements.paid_now.checked;
      submitForm(
        form,
        () =>
          api.post("/finance/transactions", {
            kind,
            description: v.description,
            category: v.category,
            amount_cents: amount,
            due_date: v.due_date,
            paid_on: paid ? v.due_date : null,
            payment_method: v.payment_method || null,
            account_id: v.account_id ? Number(v.account_id) : null,
          }),
        () => {
          close();
          toast("Lançamento salvo.");
          onSaved();
        },
      );
    });
    return form;
  });
}

function openPayDialog(tx, accounts, onSaved) {
  openDialog(
    tx.kind === "income" ? "Registrar recebimento" : "Registrar pagamento",
    (close) => {
      const form = h(
        "form",
        { class: "form", novalidate: true },
        h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
        h(
          "p",
          null,
          h("strong", null, tx.description),
          ` — ${fmtMoney(tx.amount_cents)}`,
        ),
        h(
          "div",
          { class: "form__row" },
          field({
            label: "Data",
            name: "paid_on",
            type: "date",
            required: true,
            value: toISODate(new Date()),
          }),
          field({
            label: "Forma de pagamento",
            name: "payment_method",
            as: "select",
            value: tx.payment_method || "pix",
            options: Object.entries(PAYMENT_LABELS),
          }),
        ),
        field({
          label: "Conta",
          name: "account_id",
          as: "select",
          value: tx.account_id ?? accounts[0]?.id ?? "",
          options: [["", "Sem conta"], ...accounts.map((a) => [a.id, a.name])],
        }),
        formActions(close, "Confirmar"),
      );
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const v = formValues(form);
        submitForm(
          form,
          () =>
            api.post(`/finance/transactions/${tx.id}/pay`, {
              paid_on: v.paid_on,
              payment_method: v.payment_method,
              account_id: v.account_id ? Number(v.account_id) : null,
            }),
          () => {
            close();
            toast("Pagamento registrado.");
            onSaved();
          },
        );
      });
      return form;
    },
  );
}

function openNameDialog(title, label, onSubmit) {
  openDialog(title, (close) => {
    const form = h(
      "form",
      { class: "form", novalidate: true },
      h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
      field({ label, name: "name", required: true, autocomplete: "off" }),
      formActions(close, "Salvar"),
    );
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      submitForm(
        form,
        () => onSubmit(formValues(form).name),
        () => close(),
      );
    });
    return form;
  });
}

async function renderFinance(main, isCurrent) {
  const f = (state.finance ??= {
    tab: "fluxo",
    month: currentMonth(),
    kind: "",
    status: "",
  });
  const content = h("div", null, loading());
  const tabs = [
    ["fluxo", "Fluxo de caixa"],
    ["lancamentos", "Lançamentos"],
    isOwner() && ["repasse", "Repasse"],
    ["guias", "Guias de convênio"],
  ];
  const head = h("div");
  const drawHead = () =>
    fill(
      head,
      subTabs(tabs, f.tab, (key) => {
        f.tab = key;
        drawHead();
        load();
      }),
      h(
        "div",
        { class: "toolbar", style: "margin:16px 0 20px" },
        monthPicker(f.month, (m) => {
          f.month = m;
          load();
        }),
      ),
    );
  drawHead();
  fill(
    main,
    pageHead(
      "Financeiro",
      "Fluxo de caixa, contas a pagar e a receber, repasse aos médicos e guias de convênio.",
    ),
    head,
    content,
  );

  async function load() {
    fill(content, loading());
    const period = monthRange(f.month);
    const views = {
      fluxo: drawCashflow,
      lancamentos: drawTransactions,
      repasse: drawPayouts,
      guias: drawGuides,
    };
    await views[f.tab](period);
  }

  async function drawCashflow(period) {
    const flow = await safe(() => api.get("/finance/cashflow", period));
    if (!flow || !isCurrent()) return;
    const t = flow.totals;
    const maxDay = Math.max(
      1,
      ...flow.days.map((d) => Math.max(d.income_cents, d.expense_cents)),
    );
    fill(
      content,
      h(
        "div",
        { class: "stats" },
        stat("Recebido", fmtMoney(t.income_paid), "good"),
        stat("Pago", fmtMoney(t.expense_paid), "bad"),
        stat(
          "Saldo do mês",
          fmtMoney(t.balance_paid),
          t.balance_paid >= 0 ? "good" : "bad",
        ),
        stat("A receber", fmtMoney(t.income_open)),
        stat("A pagar", fmtMoney(t.expense_open)),
        stat(
          "Saldo previsto",
          fmtMoney(t.balance_forecast),
          t.balance_forecast >= 0 ? "good" : "bad",
        ),
      ),
      t.overdue_income || t.overdue_expense
        ? h(
            "p",
            { class: "alert-box" },
            t.overdue_income
              ? `${fmtMoney(t.overdue_income)} vencido para receber. `
              : "",
            t.overdue_expense
              ? `${fmtMoney(t.overdue_expense)} vencido para pagar.`
              : "",
          )
        : null,
      h(
        "div",
        { class: "settings" },
        h(
          "section",
          { class: "panel" },
          h(
            "div",
            { class: "panel__row" },
            h("h2", { class: "panel__title" }, "Contas"),
            h(
              "button",
              {
                class: "btn btn--ghost btn--small",
                type: "button",
                onclick: () =>
                  openNameDialog(
                    "Nova conta",
                    "Nome (ex.: Caixa, Banco, Maquininha)",
                    async (name) => {
                      await api.post("/finance/accounts", { name });
                      toast("Conta criada.");
                      load();
                    },
                  ),
              },
              icon("plus"),
              "Nova conta",
            ),
          ),
          flow.accounts.length === 0
            ? h(
                "p",
                { class: "muted" },
                "Crie contas para separar o dinheiro do caixa, do banco e da maquininha.",
              )
            : h(
                "ul",
                { class: "kv" },
                flow.accounts.map((a) =>
                  h(
                    "li",
                    null,
                    h("span", null, a.name),
                    h("strong", null, fmtMoney(a.balance_cents)),
                  ),
                ),
              ),
        ),
        h(
          "section",
          { class: "panel" },
          h("h2", { class: "panel__title" }, "Por categoria (realizado)"),
          flow.categories.length === 0
            ? h("p", { class: "muted" }, "Nenhum pagamento registrado no mês.")
            : h(
                "ul",
                { class: "kv" },
                flow.categories.map((c) =>
                  h(
                    "li",
                    null,
                    h("span", null, c.category),
                    h(
                      "strong",
                      { class: c.kind === "income" ? "pos" : "neg" },
                      `${c.kind === "income" ? "+" : "−"} ${fmtMoney(c.amount_cents)}`,
                    ),
                  ),
                ),
              ),
        ),
      ),
      h(
        "section",
        { class: "panel", style: "margin-top:24px" },
        h("h2", { class: "panel__title" }, "Dia a dia"),
        flow.days.length === 0
          ? h("p", { class: "muted" }, "Nenhum lançamento no mês.")
          : h(
              "table",
              { class: "table bars-table" },
              h(
                "caption",
                { class: "visually-hidden" },
                "Entradas e saídas por dia",
              ),
              h(
                "thead",
                null,
                h(
                  "tr",
                  null,
                  h("th", null, "Dia"),
                  h("th", null, "Entradas"),
                  h("th", null, "Saídas"),
                ),
              ),
              h(
                "tbody",
                null,
                flow.days.map((d) =>
                  h(
                    "tr",
                    null,
                    h("td", { class: "num" }, fmtDate(d.date)),
                    h(
                      "td",
                      null,
                      bar(d.income_cents, maxDay, "good"),
                      fmtMoney(d.income_cents),
                    ),
                    h(
                      "td",
                      null,
                      bar(d.expense_cents, maxDay, "bad"),
                      fmtMoney(d.expense_cents),
                    ),
                  ),
                ),
              ),
            ),
      ),
    );
  }

  async function drawTransactions(period) {
    const data = await safe(() =>
      Promise.all([
        api.get("/finance/transactions", {
          ...period,
          kind: f.kind,
          status: f.status,
        }),
        api.get("/finance/accounts"),
      ]),
    );
    if (!data || !isCurrent()) return;
    const [{ items }, { items: accounts }] = data;
    const filters = h(
      "form",
      { class: "toolbar" },
      field({
        label: "Tipo",
        name: "kind",
        as: "select",
        value: f.kind,
        options: [
          ["", "Receitas e despesas"],
          ["income", "Receitas"],
          ["expense", "Despesas"],
        ],
      }),
      field({
        label: "Situação",
        name: "status",
        as: "select",
        value: f.status,
        options: [
          ["", "Todas"],
          ["open", "Em aberto"],
          ["paid", "Pagas"],
        ],
      }),
      h(
        "button",
        {
          class: "btn btn--primary",
          type: "button",
          onclick: () => openTransactionDialog(load, accounts, "income"),
        },
        icon("plus"),
        "Receita",
      ),
      h(
        "button",
        {
          class: "btn btn--ghost",
          type: "button",
          onclick: () => openTransactionDialog(load, accounts, "expense"),
        },
        icon("plus"),
        "Despesa",
      ),
    );
    filters.addEventListener("change", () => {
      const v = formValues(filters);
      f.kind = v.kind;
      f.status = v.status;
      load();
    });
    const act = async (fn, message) => {
      if ((await safe(fn)) !== null) {
        toast(message);
        load();
      }
    };
    fill(
      content,
      filters,
      h("div", { style: "height:16px" }),
      dataTable({
        caption: "Lançamentos",
        empty: "Nenhum lançamento neste mês.",
        rows: items,
        columns: [
          {
            label: "Data",
            class: "num",
            render: (t) => [
              fmtDate(t.paid_on || t.due_date),
              h("br"),
              h(
                "span",
                { class: "muted" },
                t.paid_on ? "pagamento" : "vencimento",
              ),
            ],
          },
          {
            label: "Descrição",
            render: (t) => [
              h("strong", null, t.description),
              t.doctor_name && h("br"),
              t.doctor_name && h("span", { class: "muted" }, t.doctor_name),
            ],
          },
          { label: "Categoria", render: (t) => t.category },
          {
            label: "Conta",
            render: (t) => t.account_name || h("span", { class: "muted" }, "—"),
          },
          {
            label: "Valor",
            class: "num",
            render: (t) =>
              h(
                "strong",
                { class: t.kind === "income" ? "pos" : "neg" },
                `${t.kind === "income" ? "+" : "−"} ${fmtMoney(t.amount_cents)}`,
              ),
          },
          { label: "Situação", render: txStatusBadge },
          {
            label: "Ações",
            class: "actions",
            render: (t) =>
              t.paid_on
                ? h(
                    "button",
                    {
                      class: "btn btn--ghost btn--small",
                      type: "button",
                      onclick: () =>
                        act(
                          () => api.post(`/finance/transactions/${t.id}/unpay`),
                          "Pagamento desfeito.",
                        ),
                    },
                    "Desfazer",
                  )
                : [
                    h(
                      "button",
                      {
                        class: "btn btn--primary btn--small",
                        type: "button",
                        onclick: () => openPayDialog(t, accounts, load),
                      },
                      t.kind === "income" ? "Receber" : "Pagar",
                    ),
                    confirmButton(
                      "Excluir",
                      "Confirmar",
                      () =>
                        act(
                          () => api.del(`/finance/transactions/${t.id}`),
                          "Lançamento excluído.",
                        ),
                      "btn--small",
                    ),
                  ],
          },
        ],
      }),
    );
  }

  async function drawPayouts(period) {
    const data = await safe(() =>
      Promise.all([
        api.get("/finance/payouts", period),
        api.get("/finance/payout-rules"),
        getDoctors(),
        api.get("/procedures"),
      ]),
    );
    if (!data || !isCurrent()) return;
    const [payouts, { items: rules }, doctors, { items: procedures }] = data;
    const form = h(
      "form",
      { class: "toolbar" },
      field({
        label: "Médico",
        name: "doctor_id",
        as: "select",
        value: doctors[0]?.id ?? "",
        options: doctors.map((d) => [d.id, d.name]),
      }),
      field({
        label: "Procedimento",
        name: "procedure_id",
        as: "select",
        value: "",
        options: [
          ["", "Todos (regra geral)"],
          ...procedures.map((p) => [p.id, p.name]),
        ],
      }),
      field({
        label: "Repasse (%)",
        name: "percent",
        type: "number",
        min: 0,
        max: 100,
        value: 50,
      }),
      h(
        "button",
        { class: "btn btn--primary", type: "submit" },
        "Salvar regra",
      ),
    );
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const v = formValues(form);
      if (
        (await safe(() =>
          api.put("/finance/payout-rules", {
            doctor_id: Number(v.doctor_id),
            procedure_id: v.procedure_id ? Number(v.procedure_id) : null,
            percent: Number(v.percent),
          }),
        )) !== null
      ) {
        toast("Regra de repasse salva.");
        load();
      }
    });
    fill(
      content,
      h(
        "p",
        { class: "muted", style: "margin-bottom:16px" },
        "O repasse é calculado sobre o que foi RECEBIDO no mês. A regra de um procedimento vale mais que a regra geral do médico.",
      ),
      h(
        "div",
        { class: "stats" },
        payouts.items.length === 0
          ? h(
              "p",
              { class: "muted" },
              "Nenhum recebimento ligado a médicos neste mês.",
            )
          : payouts.items.map((p) =>
              stat(
                p.doctor_name,
                `${fmtMoney(p.payout_cents)} de ${fmtMoney(p.received_cents)}`,
              ),
            ),
      ),
      payouts.items.map((p) =>
        h(
          "details",
          { class: "panel", style: "margin-top:16px" },
          h(
            "summary",
            null,
            h("strong", null, p.doctor_name),
            ` — repasse ${fmtMoney(p.payout_cents)}`,
          ),
          dataTable({
            caption: `Repasse de ${p.doctor_name}`,
            empty: "",
            rows: p.items,
            columns: [
              { label: "Data", class: "num", render: (i) => fmtDate(i.date) },
              { label: "Descrição", render: (i) => i.description },
              {
                label: "Recebido",
                class: "num",
                render: (i) => fmtMoney(i.amount_cents),
              },
              { label: "%", class: "num", render: (i) => `${i.percent}%` },
              {
                label: "Repasse",
                class: "num",
                render: (i) => fmtMoney(i.payout_cents),
              },
            ],
          }),
        ),
      ),
      h(
        "h2",
        { class: "panel__title", style: "margin:28px 0 12px" },
        "Regras de repasse",
      ),
      form,
      h("div", { style: "height:12px" }),
      dataTable({
        caption: "Regras de repasse",
        empty: "Nenhuma regra. Sem regra, o repasse é 0%.",
        rows: rules,
        columns: [
          { label: "Médico", render: (r) => r.doctor_name },
          {
            label: "Procedimento",
            render: (r) =>
              r.procedure_name || h("span", { class: "muted" }, "Todos"),
          },
          { label: "Repasse", class: "num", render: (r) => `${r.percent}%` },
          {
            label: "Ações",
            class: "actions",
            render: (r) =>
              confirmButton(
                "Remover",
                "Confirmar",
                async () => {
                  if (
                    (await safe(() =>
                      api.del(`/finance/payout-rules/${r.id}`),
                    )) !== null
                  )
                    load();
                },
                "btn--small",
              ),
          },
        ],
      }),
    );
  }

  async function drawGuides(period) {
    const plans = await safe(() => api.get("/health-plans"));
    if (!plans || !isCurrent()) return;
    if (plans.items.length === 0) {
      fill(
        content,
        h(
          "p",
          { class: "muted" },
          "Cadastre os convênios em Gestão → Convênios.",
        ),
      );
      return;
    }
    f.planId ??= plans.items[0].id;
    const picker = field({
      label: "Convênio",
      name: "plan",
      as: "select",
      value: f.planId,
      options: plans.items.map((p) => [p.id, p.name]),
    });
    picker.querySelector("select").addEventListener("change", (e) => {
      f.planId = Number(e.target.value);
      load();
    });
    const batch = await safe(() =>
      api.get("/finance/tiss", { health_plan_id: f.planId, ...period }),
    );
    if (!batch || !isCurrent()) return;
    fill(
      content,
      h(
        "div",
        { class: "toolbar" },
        picker,
        h(
          "button",
          {
            class: "btn btn--primary",
            type: "button",
            disabled: batch.guides.length === 0,
            onclick: () => printTissBatch(batch),
          },
          "Imprimir lote de guias",
        ),
      ),
      h(
        "p",
        { class: "muted", style: "margin:12px 0 16px" },
        `${plural(batch.guides.length, "guia", "guias")} · total ${fmtMoney(batch.total_cents)}. As guias saem no modelo de Guia de Consulta (padrão TISS) para conferência e envio à operadora. `,
        "O envio eletrônico (XML TISS) ainda não está disponível.",
      ),
      dataTable({
        caption: "Guias do convênio",
        empty: "Nenhuma consulta faturada por este convênio no mês.",
        rows: batch.guides,
        columns: [
          { label: "Data", class: "num", render: (g) => fmtDate(g.start_at) },
          { label: "Paciente", render: (g) => g.patient_name },
          {
            label: "Carteirinha",
            class: "num",
            render: (g) =>
              g.plan_card || h("span", { class: "muted" }, "faltando"),
          },
          { label: "Guia", class: "num", render: (g) => g.plan_guide || "—" },
          {
            label: "Procedimento",
            render: (g) => [
              g.procedure_name,
              g.procedure_tuss &&
                h("span", { class: "muted" }, ` (${g.procedure_tuss})`),
            ],
          },
          {
            label: "Valor",
            class: "num",
            render: (g) => fmtMoney(g.amount_cents),
          },
          { label: "Situação", render: txStatusBadge },
        ],
      }),
    );
  }

  load();
}

/* ===================== Estoque ===================== */

function openStockMoveDialog(item, direction, onSaved) {
  openDialog(
    `${direction > 0 ? "Entrada" : "Saída"} — ${item.name}`,
    (close) => {
      const form = h(
        "form",
        { class: "form", novalidate: true },
        h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
        h("p", { class: "muted" }, `Em estoque: ${item.quantity} ${item.unit}`),
        field({
          label: `Quantidade (${item.unit})`,
          name: "qty",
          type: "number",
          min: 1,
          required: true,
          value: 1,
        }),
        field({
          label: "Motivo",
          name: "reason",
          autocomplete: "off",
          hint:
            direction > 0
              ? "Ex.: compra, doação"
              : "Ex.: uso em consulta, vencido",
        }),
        formActions(close, "Registrar"),
      );
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const v = formValues(form);
        submitForm(
          form,
          () =>
            api.post(`/stock/items/${item.id}/movements`, {
              delta: direction * Number(v.qty || 0),
              reason: v.reason || null,
            }),
          () => {
            close();
            toast("Movimentação registrada.");
            onSaved();
          },
        );
      });
      return form;
    },
  );
}

async function openStockHistory(item) {
  const data = await safe(() => api.get(`/stock/items/${item.id}/movements`));
  if (!data) return;
  openDialog(
    `Histórico — ${item.name}`,
    () =>
      dataTable({
        caption: "Movimentações",
        empty: "Nenhuma movimentação.",
        rows: data.items,
        columns: [
          {
            label: "Data",
            class: "num",
            render: (m) => fmtDateTime(m.created_at),
          },
          {
            label: "Quantidade",
            class: "num",
            render: (m) =>
              h(
                "strong",
                { class: m.delta > 0 ? "pos" : "neg" },
                `${m.delta > 0 ? "+" : ""}${m.delta} ${item.unit}`,
              ),
          },
          { label: "Motivo", render: (m) => m.reason || "—" },
          { label: "Quem", render: (m) => m.author },
        ],
      }),
    { wide: true },
  );
}

function openStockItemDialog(onSaved, item = null) {
  openDialog(item ? "Editar item" : "Novo item de estoque", (close) => {
    const form = h(
      "form",
      { class: "form", novalidate: true },
      h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
      field({
        label: "Nome",
        name: "name",
        required: true,
        autocomplete: "off",
        value: item?.name ?? "",
      }),
      h(
        "div",
        { class: "form__row" },
        field({
          label: "Unidade",
          name: "unit",
          value: item?.unit ?? "un",
          hint: "Ex.: un, cx, ml, frasco",
        }),
        field({
          label: "Estoque mínimo",
          name: "min_quantity",
          type: "number",
          min: 0,
          value: item?.min_quantity ?? 0,
          hint: "Abaixo disso, o item aparece em alerta.",
        }),
      ),
      formActions(close, "Salvar"),
    );
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const v = formValues(form);
      const body = {
        name: v.name,
        unit: v.unit || "un",
        min_quantity: Number(v.min_quantity || 0),
      };
      submitForm(
        form,
        () =>
          item
            ? api.patch(`/stock/items/${item.id}`, body)
            : api.post("/stock/items", body),
        () => {
          close();
          toast("Item salvo.");
          onSaved();
        },
      );
    });
    return form;
  });
}

async function renderStock(main, isCurrent) {
  const listArea = h("div", null, loading());
  fill(
    main,
    pageHead(
      "Estoque",
      "Materiais e medicamentos da clínica, com alerta de estoque baixo.",
      h(
        "button",
        {
          class: "btn btn--primary",
          type: "button",
          onclick: () => openStockItemDialog(load),
        },
        icon("plus"),
        "Novo item",
      ),
    ),
    listArea,
  );

  async function load() {
    const data = await safe(() => api.get("/stock/items"));
    if (!data || !isCurrent()) return;
    const low = data.items.filter((i) => i.active && i.low);
    fill(
      listArea,
      low.length > 0 &&
        h(
          "p",
          { class: "alert-box" },
          `Estoque baixo: ${low.map((i) => `${i.name} (${i.quantity} ${i.unit})`).join(", ")}.`,
        ),
      dataTable({
        caption: "Itens do estoque",
        empty: "Nenhum item cadastrado.",
        rows: data.items,
        columns: [
          {
            label: "Item",
            render: (i) => [
              h("strong", null, i.name),
              !i.active && h("span", { class: "tag" }, "inativo"),
            ],
          },
          {
            label: "Quantidade",
            class: "num",
            render: (i) =>
              h(
                "span",
                { class: i.low ? "neg" : "" },
                `${i.quantity} ${i.unit}`,
              ),
          },
          {
            label: "Mínimo",
            class: "num",
            render: (i) => `${i.min_quantity} ${i.unit}`,
          },
          {
            label: "Ações",
            class: "actions",
            render: (i) => [
              h(
                "button",
                {
                  class: "btn btn--primary btn--small",
                  type: "button",
                  onclick: () => openStockMoveDialog(i, 1, load),
                },
                "Entrada",
              ),
              h(
                "button",
                {
                  class: "btn btn--ghost btn--small",
                  type: "button",
                  disabled: i.quantity === 0,
                  onclick: () => openStockMoveDialog(i, -1, load),
                },
                "Saída",
              ),
              h(
                "button",
                {
                  class: "btn btn--ghost btn--small",
                  type: "button",
                  onclick: () => openStockHistory(i),
                },
                "Histórico",
              ),
              h(
                "button",
                {
                  class: "btn btn--ghost btn--small",
                  type: "button",
                  onclick: () => openStockItemDialog(load, i),
                },
                "Editar",
              ),
            ],
          },
        ],
      }),
    );
  }
  load();
}

/* ===================== Gestão (painel e cadastros) ===================== */

function openCatalogDialog(kind, onSaved, item = null) {
  const isProc = kind === "procedure";
  openDialog(
    `${item ? "Editar" : "Novo"} ${isProc ? "procedimento" : "convênio"}`,
    (close) => {
      const form = h(
        "form",
        { class: "form", novalidate: true },
        h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
        field({
          label: "Nome",
          name: "name",
          required: true,
          autocomplete: "off",
          value: item?.name ?? "",
          hint: isProc
            ? "Ex.: Consulta, Retorno, Eletrocardiograma"
            : "Ex.: Unimed, Bradesco Saúde",
        }),
        isProc
          ? h(
              "div",
              { class: "form__row" },
              field({
                label: "Preço particular (R$)",
                name: "price",
                inputmode: "decimal",
                value: centsToInput(item?.price_cents),
              }),
              field({
                label: "Código TUSS",
                name: "tuss_code",
                inputmode: "numeric",
                value: item?.tuss_code ?? "",
                hint: "8 dígitos. Ex.: consulta em consultório = 10101012",
              }),
            )
          : field({
              label: "Registro ANS da operadora",
              name: "ans_code",
              inputmode: "numeric",
              value: item?.ans_code ?? "",
              hint: "6 dígitos, aparece na carteirinha",
            }),
        h(
          "label",
          { class: "switch" },
          h("input", {
            type: "checkbox",
            name: "active",
            checked: item ? item.active : true,
          }),
          h("span", null, h("strong", null, "Ativo")),
        ),
        formActions(close, "Salvar"),
      );
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const v = formValues(form);
        const active = form.elements.active.checked;
        let body;
        if (isProc) {
          const price = parseMoney(v.price || "0");
          if (price === null) {
            showFormErrors(
              form,
              new ApiError(422, "", [
                { field: "price", message: "Informe um valor válido." },
              ]),
            );
            return;
          }
          body = {
            name: v.name,
            price_cents: price,
            tuss_code: v.tuss_code || null,
            active,
          };
        } else {
          body = { name: v.name, ans_code: v.ans_code || null, active };
        }
        const base = isProc ? "/procedures" : "/health-plans";
        submitForm(
          form,
          () =>
            item ? api.put(`${base}/${item.id}`, body) : api.post(base, body),
          () => {
            close();
            toast("Cadastro salvo.");
            onSaved();
          },
        );
      });
      return form;
    },
  );
}

async function renderManagement(main, isCurrent) {
  const f = (state.management ??= { tab: "painel", month: currentMonth() });
  const head = h("div");
  const content = h("div", null, loading());
  const drawHead = () =>
    fill(
      head,
      subTabs(
        [
          ["painel", "Painel"],
          ["procedimentos", "Procedimentos"],
          ["convenios", "Convênios"],
        ],
        f.tab,
        (key) => {
          f.tab = key;
          drawHead();
          load();
        },
      ),
      f.tab === "painel" &&
        h(
          "div",
          { class: "toolbar", style: "margin:16px 0 20px" },
          monthPicker(f.month, (m) => {
            f.month = m;
            load();
          }),
        ),
    );
  drawHead();
  fill(
    main,
    pageHead(
      "Gestão da clínica",
      "Indicadores do mês e os cadastros usados no faturamento.",
    ),
    head,
    content,
  );

  async function load() {
    fill(content, loading());
    if (f.tab === "painel") return drawPanel();
    return drawCatalog(f.tab === "procedimentos" ? "procedure" : "plan");
  }

  async function drawPanel() {
    const r = await safe(() =>
      api.get("/reports/overview", monthRange(f.month)),
    );
    if (!r || !isCurrent()) return;
    const a = r.appointments;
    const t = r.finance;
    const maxRevenue = Math.max(1, ...r.doctors.map((d) => d.revenue_cents));
    const maxPlan = Math.max(
      1,
      ...r.revenue_by_plan.map((p) => p.amount_cents),
    );
    fill(
      content,
      h(
        "div",
        { class: "stats" },
        stat("Consultas no mês", String(a.total)),
        stat("Concluídas", String(a.completed), "good"),
        stat(
          "Canceladas",
          `${a.cancelled} (${a.cancel_rate}%)`,
          a.cancelled ? "bad" : "",
        ),
        stat("Prováveis faltas", String(a.missed), a.missed ? "bad" : ""),
        stat("Novos pacientes", String(r.new_patients)),
        stat("Faturamento recebido", fmtMoney(t.income_paid), "good"),
        stat("Despesas pagas", fmtMoney(t.expense_paid)),
        stat(
          "Resultado",
          fmtMoney(t.balance_paid),
          t.balance_paid >= 0 ? "good" : "bad",
        ),
      ),
      a.missed > 0 &&
        h(
          "p",
          { class: "muted", style: "margin-top:8px" },
          "Prováveis faltas: consultas agendadas de dias anteriores que não foram concluídas nem canceladas.",
        ),
      h(
        "div",
        { class: "settings", style: "margin-top:24px" },
        h(
          "section",
          { class: "panel" },
          h("h2", { class: "panel__title" }, "Por médico"),
          dataTable({
            caption: "Indicadores por médico",
            empty: "Nenhum médico.",
            rows: r.doctors,
            columns: [
              { label: "Médico", render: (d) => d.name },
              {
                label: "Consultas",
                class: "num",
                render: (d) => `${d.completed}/${d.total}`,
              },
              {
                label: "Recebido",
                render: (d) => [
                  bar(d.revenue_cents, maxRevenue, "good"),
                  fmtMoney(d.revenue_cents),
                ],
              },
            ],
          }),
        ),
        h(
          "section",
          { class: "panel" },
          h("h2", { class: "panel__title" }, "Recebido por convênio"),
          r.revenue_by_plan.length === 0
            ? h("p", { class: "muted" }, "Nada recebido no mês.")
            : h(
                "ul",
                { class: "kv" },
                r.revenue_by_plan.map((p) =>
                  h(
                    "li",
                    null,
                    h("span", null, p.name),
                    h(
                      "span",
                      null,
                      bar(p.amount_cents, maxPlan, "good"),
                      h("strong", null, fmtMoney(p.amount_cents)),
                    ),
                  ),
                ),
              ),
          r.low_stock.length > 0 &&
            h(
              "p",
              { class: "alert-box" },
              `Estoque baixo: ${r.low_stock.map((i) => i.name).join(", ")}.`,
            ),
        ),
      ),
    );
  }

  async function drawCatalog(kind) {
    const isProc = kind === "procedure";
    const data = await safe(() =>
      api.get(isProc ? "/procedures" : "/health-plans"),
    );
    if (!data || !isCurrent()) return;
    fill(
      content,
      h(
        "div",
        { class: "toolbar", style: "margin:16px 0" },
        h(
          "button",
          {
            class: "btn btn--primary",
            type: "button",
            onclick: () => openCatalogDialog(kind, load),
          },
          icon("plus"),
          isProc ? "Novo procedimento" : "Novo convênio",
        ),
      ),
      dataTable({
        caption: isProc ? "Procedimentos" : "Convênios",
        empty: isProc
          ? 'Nenhum procedimento. Comece por "Consulta" com o preço particular.'
          : "Nenhum convênio cadastrado.",
        rows: data.items,
        columns: [
          {
            label: "Nome",
            render: (i) => [
              h("strong", null, i.name),
              !i.active && h("span", { class: "tag" }, "inativo"),
            ],
          },
          isProc
            ? {
                label: "Código TUSS",
                class: "num",
                render: (i) => i.tuss_code || "—",
              }
            : {
                label: "Registro ANS",
                class: "num",
                render: (i) => i.ans_code || "—",
              },
          isProc && {
            label: "Preço particular",
            class: "num",
            render: (i) => fmtMoney(i.price_cents),
          },
          {
            label: "Ações",
            class: "actions",
            render: (i) =>
              h(
                "button",
                {
                  class: "btn btn--ghost btn--small",
                  type: "button",
                  onclick: () => openCatalogDialog(kind, load, i),
                },
                "Editar",
              ),
          },
        ],
      }),
    );
  }

  load();
}
