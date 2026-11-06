/* AgendaMed — tela Consultas: lista com filtros por médico, data e status.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

/**
 * Tela Consultas: lista com filtros por data, médico e situação, e as ações de cada
 * consulta. Os filtros ficam em state.appointments.
 */
async function renderAppointments(main, isCurrent) {
  const f = state.appointments;
  fill(main, loading());
  let doctors;
  try {
    doctors = await getDoctors();
  } catch (err) {
    handleError(err);
    return;
  }
  if (!isCurrent()) return;

  const filters = h(
    "form",
    { class: "toolbar", role: "search", "aria-label": "Filtrar consultas" },
    field({ label: "Data", name: "date", type: "date", value: f.date }),
    field({
      label: "Médico",
      name: "doctor_id",
      as: "select",
      value: f.doctorId,
      options: [
        ["", "Todos os médicos"],
        ...doctors.map((d) => [d.id, d.name]),
      ],
    }),
    field({
      label: "Situação",
      name: "status",
      as: "select",
      value: f.status,
      options: [
        ["", "Todas"],
        ["scheduled", "Agendadas"],
        ["completed", "Concluídas"],
        ["cancelled", "Canceladas"],
      ],
    }),
    h(
      "button",
      {
        class: "btn btn--ghost",
        type: "button",
        onclick: () => {
          Object.assign(f, { date: "", doctorId: "", status: "", offset: 0 });
          navigate();
        },
      },
      "Limpar filtros",
    ),
  );

  const listArea = h("div", null, loading());

  filters.addEventListener("change", () => {
    const values = formValues(filters);
    f.date = values.date;
    f.doctorId = values.doctor_id;
    f.status = values.status;
    f.offset = 0;
    load();
  });
  filters.addEventListener("submit", (e) => e.preventDefault());

  fill(
    main,
    pageHead(
      "Consultas",
      "Todas as consultas da clínica, com filtros por dia, médico e situação.",
    ),
    filters,
    h("div", { style: "height:20px" }),
    listArea,
  );

  /** Busca a página de consultas com os filtros atuais. */
  async function load() {
    try {
      const page = await api.get("/appointments", {
        date: f.date,
        doctor_id: f.doctorId,
        status: f.status,
        limit: PAGE_SIZE,
        offset: f.offset,
      });
      if (!isCurrent()) return;
      draw(page);
    } catch (err) {
      handleError(err);
    }
  }

  /** Desenha a tabela de consultas e a paginação. */
  function draw(page) {
    const now = new Date();
    fill(
      listArea,
      dataTable({
        caption: "Lista de consultas",
        empty: "Nenhuma consulta encontrada com esses filtros.",
        rows: page.items,
        columns: [
          {
            label: "Data",
            class: "num",
            render: (ap) => fmtShortDate(parseLocal(ap.start_at)),
          },
          {
            label: "Horário",
            class: "num",
            render: (ap) =>
              `${fmtTime(parseLocal(ap.start_at))} às ${fmtTime(parseLocal(ap.end_at))}`,
          },
          { label: "Paciente", render: (ap) => ap.patient.name },
          { label: "Médico", render: (ap) => ap.doctor.name },
          { label: "Situação", render: (ap) => statusBadge(ap.status) },
          {
            label: "Ações",
            class: "actions",
            render: (ap) => {
              const start = parseLocal(ap.start_at);
              const buttons = [
                h(
                  "button",
                  {
                    class: "btn btn--ghost btn--small",
                    type: "button",
                    onclick: () => {
                      Object.assign(state.agenda, {
                        doctorId: ap.doctor.id,
                        date: ap.start_at.slice(0, 10),
                        selectedKey:
                          ap.status === "cancelled" ? null : ap.start_at,
                      });
                      location.hash = "#/agenda";
                    },
                  },
                  "Ver na agenda",
                ),
              ];
              if (ap.status === "scheduled" && start <= now) {
                buttons.push(
                  h(
                    "button",
                    {
                      class: "btn btn--primary btn--small",
                      type: "button",
                      onclick: () => act(ap, "complete", "Consulta concluída."),
                    },
                    "Concluir",
                  ),
                );
              }
              if (ap.status !== "cancelled") {
                buttons.push(
                  h(
                    "button",
                    {
                      class: "btn btn--ghost btn--small",
                      type: "button",
                      onclick: () => openChargeDialog(ap, () => load()),
                    },
                    "Faturar",
                  ),
                );
              }
              if (ap.status === "completed") {
                buttons.push(
                  h(
                    "button",
                    {
                      class: "btn btn--ghost btn--small",
                      type: "button",
                      onclick: () => act(ap, "reopen", "Consulta reaberta."),
                    },
                    "Reabrir",
                  ),
                );
              }
              if (ap.status === "scheduled") {
                buttons.push(
                  confirmButton(
                    "Cancelar",
                    "Confirmar",
                    () => act(ap, "cancel", "Consulta cancelada."),
                    "btn--small",
                  ),
                );
              }
              return buttons;
            },
          },
        ],
      }),
      pager(page, (offset) => {
        f.offset = offset;
        load();
      }),
    );
  }

  /** Executa uma ação na consulta (concluir, reabrir...) e recarrega. */
  async function act(ap, action, message) {
    try {
      await api.post(`/appointments/${ap.id}/${action}`);
      toast(message);
      load();
    } catch (err) {
      handleError(err);
    }
  }

  load();
}
