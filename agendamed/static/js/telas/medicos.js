/* AgendaMed — tela Médicos: lista, cadastro, agenda e remoção.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

/** Tela Médicos: lista, cadastro, agenda de cada um e remoção. */
async function renderDoctors(main, isCurrent) {
  const f = state.doctorsPage;
  const search = field({
    label: "Buscar por especialidade",
    name: "specialty",
    type: "search",
    value: f.specialty,
    placeholder: "Ex.: Pediatria",
  });
  search.classList.add("field--grow");
  const listArea = h("div", null, loading());

  search.querySelector("input").addEventListener(
    "input",
    debounce((e) => {
      f.specialty = e.target.value.trim();
      f.offset = 0;
      load();
    }),
  );

  fill(
    main,
    pageHead(
      "Médicos",
      "Profissionais da clínica, seus horários de atendimento e a duração de cada consulta.",
      h(
        "button",
        {
          class: "btn btn--primary",
          type: "button",
          onclick: () => openDoctorDialog(() => load()),
        },
        icon("plus"),
        "Cadastrar médico",
      ),
    ),
    h(
      "div",
      { class: "toolbar", role: "search", style: "margin-bottom:20px" },
      search,
    ),
    listArea,
  );

  /** Busca a página de médicos com o filtro de especialidade. */
  async function load() {
    try {
      const page = await api.get("/doctors", {
        specialty: f.specialty,
        limit: PAGE_SIZE,
        offset: f.offset,
      });
      if (!isCurrent()) return;
      fill(
        listArea,
        dataTable({
          caption: "Lista de médicos",
          empty: f.specialty
            ? "Nenhum médico com essa especialidade."
            : "Nenhum médico cadastrado ainda.",
          rows: page.items,
          columns: [
            { label: "Nome", render: (d) => h("strong", null, d.name) },
            { label: "Especialidade", render: (d) => d.specialty },
            { label: "CRM", class: "num", render: (d) => d.crm },
            {
              label: "Expediente",
              class: "num",
              render: (d) => `${d.work_start} às ${d.work_end}`,
            },
            {
              label: "Consulta",
              class: "num",
              render: (d) => `${d.slot_minutes} min`,
            },
            {
              label: "Ações",
              class: "actions",
              render: (d) => [
                h(
                  "button",
                  {
                    class: "btn btn--ghost btn--small",
                    type: "button",
                    onclick: () => {
                      Object.assign(state.agenda, {
                        doctorId: d.id,
                        selectedKey: null,
                      });
                      location.hash = "#/agenda";
                    },
                  },
                  "Ver agenda",
                ),
                confirmButton(
                  "Remover",
                  "Confirmar remoção",
                  () => removeDoctor(d),
                  "btn--small",
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

  /* Remove o médico. Com consultas futuras, o servidor recusa e explica o motivo. */
  async function removeDoctor(doctor) {
    try {
      await api.del(`/doctors/${doctor.id}`);
      state.doctors = null;
      if (state.agenda.doctorId === doctor.id) state.agenda.doctorId = null;
      toast(
        `${doctor.name} foi removido(a). As consultas antigas continuam no histórico.`,
      );
      load();
    } catch (err) {
      handleError(err);
    }
  }

  load();
}
