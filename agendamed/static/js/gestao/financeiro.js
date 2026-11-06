/* AgendaMed — tela Financeiro: contas a receber e a pagar, fluxo de caixa, repasse aos
 *
 * médicos e guias de convênio.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

/** Selo da situação do lançamento: recebido/pago, em aberto ou vencido. */
function txStatusBadge(tx) {
  const map = {
    paid: ["completed", tx.kind === "income" ? "Recebido" : "Pago"],
    open: ["scheduled", "Em aberto"],
    overdue: ["cancelled", "Vencido"],
  };
  const [tone, label] = map[tx.status];
  return h("span", { class: `badge badge--${tone}` }, label);
}

/** Janela de nova receita ou nova despesa. */
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

/** Janela de registrar o pagamento de um lançamento (data, conta e forma). */
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

/** Janela simples com um campo de nome (ex.: criar uma conta). */
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

/**
 * Tela Financeiro, com abas: Fluxo de caixa, Lançamentos, Repasse e Guias de convênio.
 * A aba e o mês escolhidos ficam em state.finance.
 */
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
  /** Desenha as abas e o seletor de mês. */
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

  /** Carrega a aba escolhida no mês escolhido. */
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

  /** Aba Fluxo de caixa: totais, movimento por dia, categorias e contas. */
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

  /** Aba Lançamentos: receitas e despesas com as ações de cada um. */
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
    /** Executa uma ação num lançamento e recarrega a aba. */
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

  /** Aba Repasse: regras por médico e o repasse do mês. */
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

  /** Aba Guias de convênio: escolhe o convênio e imprime as guias. */
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
