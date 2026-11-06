/* AgendaMed — tela Agenda: o dia do médico em forma de régua de horários.
 *
 * Mostra horários livres e ocupados e as ações de cada consulta.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

/**
 * Tela Agenda: o dia de um médico como uma régua de horários.
 * Partes: o cabeçalho (médico, dia e navegação), a régua (loadDay/drawDay/slotRow) e o
 * painel ao lado (drawPanel), que muda conforme o horário escolhido: livre
 * (bookingPanel, para marcar) ou ocupado (detailsPanel, com as ações da consulta).
 * O estado (médico, dia e horário escolhidos) fica em state.agenda.
 */
async function renderAgenda(main, isCurrent) {
  fill(main, loading());
  let doctors;
  try {
    doctors = await getDoctors();
  } catch (err) {
    handleError(err);
    return;
  }
  if (!isCurrent()) return;

  if (doctors.length === 0) {
    fill(
      main,
      pageHead(
        "Agenda",
        "Os horários aparecem aqui depois que um médico é cadastrado.",
      ),
      h(
        "div",
        { class: "ruler" },
        h(
          "div",
          { class: "agenda-empty" },
          h("strong", null, "Nenhum médico cadastrado"),
          h("p", null, "Cadastre o primeiro médico para montar a agenda."),
          h(
            "p",
            { style: "margin-top:16px" },
            h(
              "button",
              {
                class: "btn btn--primary",
                type: "button",
                onclick: () => openDoctorDialog(() => navigate()),
              },
              icon("plus"),
              "Cadastrar médico",
            ),
          ),
        ),
      ),
    );
    return;
  }

  const a = state.agenda;
  if (!doctors.some((d) => d.id === a.doctorId)) a.doctorId = doctors[0].id;
  if (!a.date) a.date = toISODate(nextWorkingDay(new Date(), true));
  /** O médico escolhido na agenda. */
  const doctor = () => doctors.find((d) => d.id === a.doctorId);

  const doctorField = field({
    label: "Médico",
    name: "doctor",
    as: "select",
    value: a.doctorId,
    options: doctors.map((d) => [d.id, `${d.name} (${d.specialty})`]),
  });
  doctorField.querySelector("select").addEventListener("change", (e) => {
    a.doctorId = Number(e.target.value);
    a.selectedKey = null;
    loadDay();
  });

  const dateLabel = h("h2", { class: "daybar__date" });
  const summary = h("p", { class: "daybar__summary", "aria-live": "polite" });
  const dateInput = h("input", {
    class: "input",
    type: "date",
    value: a.date,
    "aria-label": "Escolher data",
  });
  dateInput.addEventListener(
    "change",
    () => dateInput.value && goTo(dateInput.value),
  );

  const daybar = h(
    "div",
    { class: "daybar" },
    h("div", null, dateLabel, summary),
    h(
      "div",
      { class: "daybar__nav" },
      h(
        "button",
        {
          class: "btn btn--ghost btn--icon",
          type: "button",
          "aria-label": "Dia anterior",
          onclick: () => goTo(toISODate(addDays(parseISODate(a.date), -1))),
        },
        icon("left"),
      ),
      dateInput,
      h(
        "button",
        {
          class: "btn btn--ghost btn--icon",
          type: "button",
          "aria-label": "Próximo dia",
          onclick: () => goTo(toISODate(addDays(parseISODate(a.date), 1))),
        },
        icon("right"),
      ),
      h(
        "button",
        {
          class: "btn btn--ghost",
          type: "button",
          onclick: () => goTo(toISODate(new Date())),
        },
        "Hoje",
      ),
    ),
  );

  const ruler = h("div", {
    class: "ruler",
    role: "list",
    "aria-label": "Horários do dia",
  });
  const panel = h("aside", {
    class: "panel",
    "aria-label": "Detalhes do horário",
  });

  fill(
    main,
    pageHead(
      "Agenda",
      "Veja o dia de cada médico e marque consultas nos horários livres.",
      doctorField,
    ),
    h("div", { class: "agenda" }, h("section", null, daybar, ruler), panel),
  );

  let day = null;
  let daySeq = 0;

  /** Vai para outro dia e recarrega a régua. */
  function goTo(iso) {
    a.date = iso;
    a.selectedKey = null;
    dateInput.value = iso;
    loadDay();
  }

  /**
   * Carrega o dia: horários livres e consultas do médico, e monta as linhas da régua.
   */
  async function loadDay() {
    const seq = ++daySeq;
    const current = doctor();
    dateLabel.textContent = fmtLongDate(parseISODate(a.date));
    summary.textContent = "";
    fill(ruler, loading("Carregando horários…"));
    try {
      const [availability, list] = await Promise.all([
        api.get(`/doctors/${current.id}/availability`, { date: a.date }),
        api.get("/appointments", {
          doctor_id: current.id,
          date: a.date,
          limit: 100,
        }),
      ]);
      if (seq !== daySeq || !isCurrent()) return;
      const active = list.items.filter((item) => item.status !== "cancelled");
      day = {
        doctor: current,
        slots: buildSlots(
          current,
          a.date,
          new Set(availability.available_slots),
          active,
        ),
      };
      drawDay();
    } catch (err) {
      if (seq !== daySeq) return;
      handleError(err);
      fill(
        ruler,
        h(
          "div",
          { class: "agenda-empty" },
          h("strong", null, "Não foi possível carregar a agenda"),
          h("p", null, err.message),
        ),
      );
    }
  }

  /** Desenha a régua do dia e o resumo (quantos livres e ocupados). */
  function drawDay() {
    const dateObj = parseISODate(a.date);
    const booked = day.slots.filter(
      (s) => s.kind === "booked" || s.kind === "done",
    ).length;
    const free = day.slots.filter((s) => s.kind === "free").length;

    if (isWeekend(dateObj) && booked === 0) {
      summary.textContent = "Sem atendimento";
      fill(
        ruler,
        h(
          "div",
          { class: "agenda-empty" },
          h("strong", null, "Os médicos não atendem aos fins de semana"),
          h(
            "p",
            { style: "margin-top:12px" },
            h(
              "button",
              {
                class: "btn btn--ghost",
                type: "button",
                onclick: () => goTo(toISODate(nextWorkingDay(dateObj, false))),
              },
              "Ir para o próximo dia útil",
            ),
          ),
        ),
      );
      drawPanel();
      return;
    }

    summary.textContent = `${plural(booked, "consulta", "consultas")} e ${plural(free, "horário livre", "horários livres")}`;
    fill(ruler, ...day.slots.map(slotRow));
    drawNowLine(dateObj);
    drawPanel();
  }

  /** Uma linha da régua: o horário e o que há nele (livre ou consulta). */
  function slotRow(slot) {
    const isSelected = slot.key === a.selectedKey;
    const select = () => {
      a.selectedKey = slot.key;
      ruler
        .querySelectorAll('[aria-pressed="true"]')
        .forEach((el) => el.setAttribute("aria-pressed", "false"));
      row.querySelector("button")?.setAttribute("aria-pressed", "true");
      drawPanel();
      if (window.matchMedia("(max-width: 1100px)").matches)
        panel.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    let body;
    if (slot.kind === "free") {
      body = h(
        "button",
        {
          class: "slot__btn",
          type: "button",
          "aria-pressed": String(isSelected),
          onclick: select,
        },
        h("span", null, "Livre"),
        h("span", { class: "slot__cta" }, `Agendar às ${fmtTime(slot.time)}`),
      );
    } else if (slot.kind === "past") {
      body = h(
        "div",
        { title: "Horário indisponível" },
        h("span", { class: "visually-hidden" }, "Indisponível"),
      );
    } else {
      const ap = slot.appointment;
      body = h(
        "button",
        {
          class: "slot__btn",
          type: "button",
          "aria-pressed": String(isSelected),
          onclick: select,
        },
        h(
          "span",
          { class: "slot__who" },
          h("span", { class: "slot__name" }, ap.patient.name),
          ap.notes && h("span", { class: "slot__note" }, ap.notes),
        ),
        slot.kind === "done"
          ? statusBadge("completed")
          : h(
              "span",
              { class: "slot__range" },
              `${fmtTime(parseLocal(ap.start_at))} às ${fmtTime(parseLocal(ap.end_at))}`,
            ),
      );
    }

    const row = h(
      "div",
      {
        class: `slot slot--${slot.kind}${slot.time.getMinutes() === 0 ? " slot--hour" : ""}`,
        role: "listitem",
        "data-key": slot.key,
      },
      h("span", { class: "slot__time" }, fmtTime(slot.time)),
      h("div", { class: "slot__body" }, body),
    );
    return row;
  }

  /** Linha da hora atual, quando o dia mostrado é hoje. */
  function drawNowLine(dateObj) {
    const now = new Date();
    if (toISODate(now) !== toISODate(dateObj)) return;
    const rows = [...ruler.querySelectorAll(".slot")];
    const minutes = day.doctor.slot_minutes;
    const index = day.slots.findIndex(
      (s) =>
        now >= s.time && now < new Date(s.time.getTime() + minutes * 60000),
    );
    if (index < 0) return;
    requestAnimationFrame(() => {
      const row = rows[index];
      const fraction = (now - day.slots[index].time) / (minutes * 60000);
      const line = h(
        "div",
        {
          class: "now-line",
          style: `top:${row.offsetTop + fraction * row.offsetHeight}px`,
          "aria-hidden": "true",
        },
        h("span", null, `Agora ${fmtTime(now)}`),
      );
      ruler.append(line);
    });
  }

  /** Desenha o painel ao lado conforme o horário escolhido. */
  function drawPanel() {
    const slot = day?.slots.find((s) => s.key === a.selectedKey);
    if (!slot || slot.kind === "past") {
      const d = doctor();
      fill(
        panel,
        h("h2", { class: "panel__title" }, "Selecione um horário"),
        h(
          "div",
          { class: "panel__hint" },
          h(
            "p",
            null,
            "Clique em um horário livre para marcar uma consulta, ou em uma consulta para ver os detalhes.",
          ),
          h(
            "p",
            null,
            `${d.name} atende de ${d.work_start} às ${d.work_end}, com consultas de ${d.slot_minutes} minutos.`,
          ),
        ),
      );
    } else if (slot.kind === "free") {
      fill(panel, ...bookingPanel(slot));
    } else {
      fill(panel, ...detailsPanel(slot.appointment));
    }
  }

  /** Painel de um horário livre: buscar o paciente e marcar. */
  function bookingPanel(slot) {
    const d = doctor();
    const end = new Date(slot.time.getTime() + d.slot_minutes * 60000);
    let chosen = null;

    const search = h("input", {
      class: "input",
      type: "search",
      id: "patient-search",
      placeholder: "Buscar por nome ou CPF",
      autocomplete: "off",
    });
    const results = h("div", {
      class: "picker",
      role: "group",
      "aria-label": "Pacientes encontrados",
    });
    const notes = h("textarea", {
      class: "input",
      id: "booking-notes",
      name: "notes",
      maxlength: "500",
      placeholder: "Motivo da consulta, retorno, exames…",
    });
    const error = h("p", { class: "form__error", role: "alert" });
    const submit = h(
      "button",
      { class: "btn btn--primary btn--block", type: "submit" },
      "Agendar consulta",
    );

    function drawResults(patients) {
      if (patients.length === 0) {
        fill(
          results,
          h("p", { class: "picker__empty" }, "Nenhum paciente encontrado."),
        );
        return;
      }
      fill(
        results,
        ...patients.map((p) => {
          const option = h(
            "button",
            {
              class: "picker__option",
              type: "button",
              "aria-pressed": String(chosen?.id === p.id),
              onclick: () => {
                chosen = p;
                error.textContent = "";
                results
                  .querySelectorAll(".picker__option")
                  .forEach((el) => el.setAttribute("aria-pressed", "false"));
                option.setAttribute("aria-pressed", "true");
              },
            },
            h("span", { class: "picker__name" }, p.name),
            h(
              "span",
              { class: "picker__meta" },
              `CPF ${p.cpf}, ${ageFrom(p.birth_date)} anos`,
            ),
          );
          return option;
        }),
      );
    }

    async function loadPatients(q = "") {
      try {
        const page = await api.get("/patients", { q, limit: 8 });
        drawResults(page.items);
      } catch (err) {
        handleError(err);
      }
    }
    search.addEventListener(
      "input",
      debounce(() => loadPatients(search.value.trim())),
    );
    loadPatients();

    const form = h(
      "form",
      { class: "form", novalidate: true },
      h(
        "div",
        { class: "field" },
        h(
          "label",
          { class: "field__label", for: "patient-search" },
          "Paciente",
        ),
        search,
        results,
        h(
          "button",
          {
            class: "link-btn",
            type: "button",
            style: "justify-self:start",
            onclick: () =>
              openPatientDialog((p) => {
                chosen = p;
                search.value = p.name;
                drawResults([p]);
              }),
          },
          "Cadastrar novo paciente",
        ),
      ),
      h(
        "div",
        { class: "field" },
        h(
          "label",
          { class: "field__label", for: "booking-notes" },
          "Observações",
        ),
        notes,
      ),
      error,
      submit,
    );

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!chosen) {
        error.textContent = "Escolha o paciente da consulta.";
        search.focus();
        return;
      }
      submit.disabled = true;
      try {
        await api.post("/appointments", {
          doctor_id: d.id,
          patient_id: chosen.id,
          start_at: slot.key,
          notes: notes.value.trim() || null,
        });
        toast(
          `Consulta de ${chosen.name} agendada para as ${fmtTime(slot.time)}.`,
        );
        await loadDay();
      } catch (err) {
        if (err.status === 401) return;
        error.textContent = err.errors?.length
          ? err.errors.map((e) => e.message).join(" ")
          : err.message;
        if (err.status === 409) loadDay();
      } finally {
        submit.disabled = false;
      }
    });

    return [
      h(
        "div",
        null,
        h("h2", { class: "panel__title" }, "Nova consulta"),
        h(
          "p",
          { class: "panel__when" },
          `${fmtLongDate(slot.time)}, das ${fmtTime(slot.time)} às ${fmtTime(end)}`,
        ),
      ),
      form,
    ];
  }

  /** Painel de uma consulta: dados do paciente e as ações da consulta. */
  function detailsPanel(ap) {
    const start = parseLocal(ap.start_at);
    const end = parseLocal(ap.end_at);
    const started = start <= new Date();
    const actions = h("div", {
      class: "form__actions",
      style: "justify-content:stretch",
    });

    async function act(action, message) {
      try {
        await api.post(`/appointments/${ap.id}/${action}`);
        toast(message);
        if (action === "cancel") a.selectedKey = null;
        await loadDay();
      } catch (err) {
        handleError(err);
      }
    }

    if (ap.status === "scheduled" && started) {
      actions.append(
        h(
          "button",
          {
            class: "btn btn--primary btn--block",
            type: "button",
            onclick: () => act("complete", "Consulta concluída."),
          },
          "Concluir consulta",
        ),
      );
    }
    if (ap.status === "completed") {
      actions.append(
        h(
          "button",
          {
            class: "btn btn--ghost btn--block",
            type: "button",
            onclick: () => act("reopen", "Consulta reaberta."),
          },
          "Reabrir consulta",
        ),
      );
    }
    if (ap.status === "scheduled") {
      actions.append(
        confirmButton(
          "Cancelar consulta",
          "Confirmar cancelamento",
          () =>
            act(
              "cancel",
              started
                ? "Consulta cancelada."
                : "Consulta cancelada. O horário voltou a ficar livre.",
            ),
          "btn--block",
        ),
      );
    }

    return [
      h(
        "div",
        null,
        h("h2", { class: "panel__title" }, ap.patient.name),
        h(
          "p",
          { class: "panel__when" },
          `${fmtLongDate(start)}, das ${fmtTime(start)} às ${fmtTime(end)}`,
        ),
      ),
      h(
        "dl",
        { class: "details" },
        h(
          "div",
          null,
          h("dt", null, "Situação"),
          h("dd", null, statusBadge(ap.status)),
        ),
        h("div", null, h("dt", null, "Médico"), h("dd", null, ap.doctor.name)),
        h(
          "div",
          null,
          h("dt", null, "Observações"),
          h("dd", null, ap.notes || "Sem observações"),
        ),
      ),
      actions.childElementCount ? actions : null,
    ];
  }

  loadDay();
}

/**
 * Monta as linhas da régua do dia: um horário a cada `slot_minutes` dentro do
 * expediente, marcado como livre, ocupado (com a consulta), concluído ou passado.
 */
function buildSlots(doctor, isoDate, freeKeys, appointments) {
  const [sh, sm] = doctor.work_start.split(":").map(Number);
  const [eh, em] = doctor.work_end.split(":").map(Number);
  const start = parseISODate(isoDate);
  start.setHours(sh, sm, 0, 0);
  const end = parseISODate(isoDate);
  end.setHours(eh, em, 0, 0);
  const step = doctor.slot_minutes * 60000;
  const byStart = new Map(appointments.map((ap) => [ap.start_at, ap]));

  const slots = [];
  for (let t = start.getTime(); t + step <= end.getTime(); t += step) {
    const time = new Date(t);
    const key = toLocalISO(time);
    const appointment = byStart.get(key);
    let kind = "past";
    if (appointment)
      kind = appointment.status === "completed" ? "done" : "booked";
    else if (freeKeys.has(key)) kind = "free";
    slots.push({ key, time, kind, appointment });
  }
  return slots;
}
