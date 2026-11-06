/* AgendaMed — tela Pacientes: busca por nome ou CPF, cadastro e edição.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

async function renderPatients(main, isCurrent) {
  const f = state.patientsPage;
  const search = field({
    label: "Buscar paciente",
    name: "q",
    type: "search",
    value: f.q,
    placeholder: "Nome ou CPF",
  });
  search.classList.add("field--grow");
  const listArea = h("div", null, loading());

  search.querySelector("input").addEventListener(
    "input",
    debounce((e) => {
      f.q = e.target.value.trim();
      f.offset = 0;
      load();
    }),
  );

  fill(
    main,
    pageHead(
      "Pacientes",
      "Cadastro de pacientes, com CPF validado e dados de contato.",
      h(
        "button",
        {
          class: "btn btn--primary",
          type: "button",
          onclick: () => openPatientDialog(() => load()),
        },
        icon("plus"),
        "Cadastrar paciente",
      ),
    ),
    h(
      "div",
      { class: "toolbar", role: "search", style: "margin-bottom:20px" },
      search,
    ),
    listArea,
  );

  async function load() {
    try {
      const page = await api.get("/patients", {
        q: f.q,
        limit: PAGE_SIZE,
        offset: f.offset,
      });
      if (!isCurrent()) return;
      fill(
        listArea,
        dataTable({
          caption: "Lista de pacientes",
          empty: f.q
            ? "Nenhum paciente encontrado com essa busca."
            : "Nenhum paciente cadastrado ainda.",
          rows: page.items,
          columns: [
            { label: "Nome", render: (p) => h("strong", null, p.name) },
            { label: "CPF", class: "num", render: (p) => p.cpf },
            {
              label: "Nascimento",
              class: "num",
              render: (p) => [
                fmtShortDate(parseISODate(p.birth_date)),
                h("br"),
                h("span", { class: "muted" }, `${ageFrom(p.birth_date)} anos`),
              ],
            },
            { label: "E-mail", render: (p) => p.email },
            {
              label: "Telefone",
              class: "num",
              render: (p) =>
                p.phone || h("span", { class: "muted" }, "Não informado"),
            },
            {
              label: "Ações",
              class: "actions",
              render: (p) => [
                h(
                  "button",
                  {
                    class: "btn btn--primary btn--small",
                    type: "button",
                    "aria-label": `Prontuário de ${p.name}`,
                    onclick: () => openRecordDialog(p),
                  },
                  "Prontuário",
                ),
                h(
                  "button",
                  {
                    class: "btn btn--ghost btn--small",
                    type: "button",
                    "aria-label": `Editar ${p.name}`,
                    onclick: () => openPatientDialog(() => load(), p),
                  },
                  "Editar",
                ),
              ],
            },
          ],
        }),
        pager(page, (offset) => {
          f.offset = offset;
          load();
        }),
      );
    } catch (err) {
      handleError(err);
    }
  }

  load();
}
