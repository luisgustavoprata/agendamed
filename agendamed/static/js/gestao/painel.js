/* AgendaMed — tela Gestão: painel do mês e cadastros de procedimentos e convênios.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

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
