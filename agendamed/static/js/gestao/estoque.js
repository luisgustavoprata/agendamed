/* AgendaMed — tela Estoque: itens, entradas e saídas e o histórico de cada item.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

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
