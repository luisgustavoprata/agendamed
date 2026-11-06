/* AgendaMed — janela do prontuário do paciente.
 *
 * Ficha clínica, registros (anamnese, evolução, exames...) e prescrições.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

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
