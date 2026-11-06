/* AgendaMed — tela Agendar (tela inicial): marcar consulta passo a passo.
 *
 * Médico → dia e horário → paciente → confirmação.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

/** Formato dos botões de dia: "seg., 07/01". */
const chipDateFmt = new Intl.DateTimeFormat("pt-BR", {
  weekday: "short",
  day: "2-digit",
  month: "2-digit",
});

/**
 * Tela Agendar (a tela inicial). Passos: 1) médico, 2) dia e horário, 3) paciente; ao
 * lado, o resumo com o botão de confirmar. `b` guarda as escolhas feitas até agora.
 */
async function renderBooking(main, isCurrent) {
  fill(main, loading());
  let doctors;
  try {
    doctors = await getDoctors();
  } catch (err) {
    handleError(err);
    return;
  }
  if (!isCurrent()) return;

  // Escolhas da pessoa ao longo das etapas.
  const b = { doctor: null, date: null, slot: null, patient: null, days: [] };

  const doctorStep = h("section", {
    class: "step",
    "aria-labelledby": "step-doctor",
  });
  const timeStep = h("section", {
    class: "step step--locked",
    "aria-labelledby": "step-time",
  });
  const patientStep = h("section", {
    class: "step step--locked",
    "aria-labelledby": "step-patient",
  });
  const summary = h("aside", {
    class: "panel summary",
    "aria-label": "Resumo do agendamento",
  });

  fill(
    main,
    pageHead(
      "Agendar consulta",
      "Escolha o médico, o horário e o paciente. O resumo ao lado mostra o que será marcado.",
    ),
    h(
      "div",
      { class: "booking" },
      h("div", { class: "booking__steps" }, doctorStep, timeStep, patientStep),
      summary,
    ),
  );

  /** Cabeçalho de um passo: número, título e dica. */
  function stepHead(number, id, title, hint) {
    return h(
      "header",
      { class: "step__head" },
      h("span", { class: "step__num", "aria-hidden": "true" }, number),
      h(
        "div",
        null,
        h("h2", { class: "step__title", id }, title),
        hint && h("p", { class: "step__hint" }, hint),
      ),
    );
  }

  /* Etapa 1: médico */
  function drawDoctors() {
    if (doctors.length === 0) {
      fill(
        doctorStep,
        stepHead(1, "step-doctor", "Escolha o médico"),
        h("p", { class: "step__empty" }, "Nenhum médico cadastrado ainda."),
        h(
          "div",
          null,
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
      );
      return;
    }
    fill(
      doctorStep,
      stepHead(
        1,
        "step-doctor",
        "Escolha o médico",
        b.doctor ? null : "Toque no profissional para ver os horários livres.",
      ),
      h(
        "div",
        { class: "choice-grid", role: "group", "aria-label": "Médicos" },
        doctors.map((d) =>
          h(
            "button",
            {
              class: "choice",
              type: "button",
              "aria-pressed": String(b.doctor?.id === d.id),
              onclick: () => chooseDoctor(d),
            },
            h("span", { class: "choice__title" }, d.name),
            h("span", { class: "choice__meta" }, d.specialty),
            h(
              "span",
              { class: "choice__foot" },
              `Atende das ${d.work_start} às ${d.work_end}`,
            ),
            h(
              "span",
              { class: "choice__foot" },
              `Consultas de ${d.slot_minutes} minutos`,
            ),
          ),
        ),
      ),
    );
  }

  /* Etapa 2: dia e horário */
  let daysSeq = 0;
  /** Escolhe o médico e carrega os próximos dias úteis com horário. */
  async function chooseDoctor(doctor) {
    b.doctor = doctor;
    b.slot = null;
    b.days = [];
    drawDoctors();
    drawSummary();
    timeStep.className = "step";
    fill(
      timeStep,
      stepHead(2, "step-time", "Escolha o dia e o horário"),
      loading("Buscando horários livres…"),
    );

    const seq = ++daysSeq;
    const days = upcomingWorkingDays(10);
    try {
      const results = await Promise.all(
        days.map((day) =>
          api.get(`/doctors/${doctor.id}/availability`, {
            date: toISODate(day),
          }),
        ),
      );
      if (seq !== daysSeq || !isCurrent()) return;
      b.days = days.map((day, i) => ({
        day,
        iso: toISODate(day),
        slots: results[i].available_slots,
      }));
      const firstWithSlots = b.days.find((d) => d.slots.length > 0);
      b.date = (firstWithSlots || b.days[0]).iso;
      drawTimes();
      if (window.matchMedia("(max-width: 1100px)").matches) {
        timeStep.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } catch (err) {
      if (seq !== daysSeq) return;
      handleError(err);
      fill(
        timeStep,
        stepHead(2, "step-time", "Escolha o dia e o horário"),
        h("p", { class: "step__empty" }, err.message),
      );
    }
  }

  /** Desenha a faixa de dias e os horários livres do dia escolhido. */
  function drawTimes() {
    const current = b.days.find((d) => d.iso === b.date);
    const strip = h(
      "div",
      { class: "day-strip", role: "group", "aria-label": "Dias" },
      b.days.map((d) =>
        h(
          "button",
          {
            class: "day-chip",
            type: "button",
            "aria-pressed": String(d.iso === b.date),
            disabled: d.slots.length === 0,
            onclick: () => {
              b.date = d.iso;
              b.slot = null;
              drawTimes();
              drawSummary();
            },
          },
          h(
            "span",
            { class: "day-chip__day" },
            capitalize(chipDateFmt.format(d.day).replace(".", "")),
          ),
          h(
            "span",
            { class: "day-chip__count" },
            d.slots.length
              ? plural(d.slots.length, "livre", "livres")
              : "Sem vagas",
          ),
        ),
      ),
    );

    const times = current.slots.length
      ? h(
          "div",
          {
            class: "time-grid",
            role: "group",
            "aria-label": "Horários livres",
          },
          current.slots.map((key) =>
            h(
              "button",
              {
                class: "time-btn",
                type: "button",
                "aria-pressed": String(b.slot === key),
                onclick: () => {
                  b.slot = key;
                  drawTimes();
                  drawSummary();
                  unlockPatients();
                },
              },
              fmtTime(parseLocal(key)),
            ),
          ),
        )
      : h(
          "p",
          { class: "step__empty" },
          "Sem horários livres neste dia. Escolha outro dia acima.",
        );

    fill(
      timeStep,
      stepHead(
        2,
        "step-time",
        "Escolha o dia e o horário",
        fmtLongDate(parseISODate(b.date)),
      ),
      strip,
      times,
    );
  }

  /* Etapa 3: paciente */
  let patientsReady = false;
  /** Libera o passo do paciente (na primeira vez que um horário é escolhido). */
  function unlockPatients() {
    if (patientsReady) return;
    patientsReady = true;
    patientStep.className = "step";

    const search = h("input", {
      class: "input",
      type: "search",
      id: "booking-search",
      placeholder: "Buscar por nome ou CPF",
      autocomplete: "off",
    });
    const results = h("div", {
      class: "picker picker--wide",
      role: "group",
      "aria-label": "Pacientes encontrados",
    });
    const notes = h("textarea", {
      class: "input",
      id: "booking-notes",
      maxlength: "500",
      placeholder: "Motivo da consulta, retorno, exames…",
    });
    notes.addEventListener("input", () => (b.notes = notes.value.trim()));

    /** Mostra os pacientes encontrados na busca, para escolher um. */
    function drawResults(patients) {
      if (patients.length === 0) {
        fill(
          results,
          h(
            "p",
            { class: "picker__empty" },
            "Nenhum paciente encontrado. Cadastre um novo abaixo.",
          ),
        );
        return;
      }
      fill(
        results,
        ...patients.map((p) =>
          h(
            "button",
            {
              class: "picker__option",
              type: "button",
              "aria-pressed": String(b.patient?.id === p.id),
              onclick: (event) => {
                b.patient = p;
                results
                  .querySelectorAll(".picker__option")
                  .forEach((el) => el.setAttribute("aria-pressed", "false"));
                event.currentTarget.setAttribute("aria-pressed", "true");
                drawSummary();
              },
            },
            h("span", { class: "picker__name" }, p.name),
            h(
              "span",
              { class: "picker__meta" },
              `CPF ${p.cpf}, ${ageFrom(p.birth_date)} anos`,
            ),
          ),
        ),
      );
    }

    /** Busca pacientes pelo nome ou CPF (até 8 resultados). */
    async function loadPatients(q = "") {
      try {
        const page = await api.get("/patients", { q, limit: 8 });
        if (isCurrent()) drawResults(page.items);
      } catch (err) {
        handleError(err);
      }
    }
    search.addEventListener(
      "input",
      debounce(() => loadPatients(search.value.trim())),
    );
    loadPatients();

    fill(
      patientStep,
      stepHead(3, "step-patient", "Escolha o paciente"),
      h(
        "div",
        { class: "field" },
        h(
          "label",
          { class: "field__label", for: "booking-search" },
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
                b.patient = p;
                search.value = p.name;
                drawResults([p]);
                drawSummary();
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
          "Observações (opcional)",
        ),
        notes,
      ),
    );
  }

  /* Resumo e confirmação */
  function summaryRow(label, value) {
    return h(
      "div",
      null,
      h("dt", null, label),
      h(
        "dd",
        { class: value ? null : "is-empty" },
        value || "Ainda não escolhido",
      ),
    );
  }

  /** Atualiza o resumo ao lado e o botão de confirmar. */
  function drawSummary() {
    const start = b.slot ? parseLocal(b.slot) : null;
    const end = start
      ? new Date(start.getTime() + b.doctor.slot_minutes * 60000)
      : null;
    const ready = Boolean(b.doctor && b.slot && b.patient);
    let next = "Comece escolhendo o médico.";
    if (b.doctor && !b.slot) next = "Agora escolha o dia e o horário.";
    else if (b.slot && !b.patient) next = "Falta escolher o paciente.";

    const error = h("p", { class: "form__error", role: "alert" });
    const confirm = h(
      "button",
      {
        class: "btn btn--primary btn--block btn--large",
        type: "button",
        disabled: !ready,
      },
      "Confirmar agendamento",
    );
    confirm.addEventListener("click", async () => {
      confirm.disabled = true;
      confirm.textContent = "Agendando…";
      try {
        const appointment = await api.post("/appointments", {
          doctor_id: b.doctor.id,
          patient_id: b.patient.id,
          start_at: b.slot,
          notes: b.notes || null,
        });
        drawSuccess(appointment);
      } catch (err) {
        if (err.status === 401) return;
        error.textContent = err.errors?.length
          ? err.errors.map((e) => e.message).join(" ")
          : err.message;
        confirm.textContent = "Confirmar agendamento";
        if (err.status === 409 || err.status === 422) {
          // O horário foi ocupado ou passou enquanto a pessoa escolhia: atualiza a grade.
          const patient = b.patient;
          await chooseDoctor(b.doctor);
          b.patient = patient;
          drawSummary();
          summary.querySelector(".form__error").textContent = error.textContent;
        } else {
          confirm.disabled = false;
        }
      }
    });

    fill(
      summary,
      h("h2", { class: "panel__title" }, "Resumo"),
      h(
        "dl",
        { class: "details" },
        summaryRow(
          "Médico",
          b.doctor && `${b.doctor.name}, ${b.doctor.specialty}`,
        ),
        summaryRow("Dia", start && fmtLongDate(start)),
        summaryRow("Horário", start && `${fmtTime(start)} às ${fmtTime(end)}`),
        summaryRow("Paciente", b.patient?.name),
      ),
      error,
      confirm,
      !ready && h("p", { class: "summary__hint" }, next),
    );
  }

  /** Mostra a consulta marcada e as opções do que fazer depois. */
  function drawSuccess(ap) {
    const start = parseLocal(ap.start_at);
    const end = parseLocal(ap.end_at);
    toast("Consulta agendada.");
    fill(
      summary,
      h(
        "div",
        { class: "success" },
        h("span", { class: "success__icon" }, icon("check")),
        h("h2", { class: "panel__title", tabindex: "-1" }, "Consulta agendada"),
        h("p", null, `${ap.patient.name} com ${ap.doctor.name}`),
        h(
          "p",
          { class: "panel__when" },
          `${fmtLongDate(start)}, das ${fmtTime(start)} às ${fmtTime(end)}`,
        ),
      ),
      h(
        "div",
        { class: "success__actions" },
        h(
          "button",
          {
            class: "btn btn--primary btn--block",
            type: "button",
            onclick: () => navigate(),
          },
          "Agendar outra consulta",
        ),
        h(
          "button",
          {
            class: "btn btn--ghost btn--block",
            type: "button",
            onclick: () => {
              Object.assign(state.agenda, {
                doctorId: ap.doctor.id,
                date: ap.start_at.slice(0, 10),
                selectedKey: ap.start_at,
              });
              location.hash = "#/agenda";
            },
          },
          "Ver na agenda do médico",
        ),
      ),
    );
    summary.querySelector(".panel__title").focus();
    if (window.matchMedia("(max-width: 1100px)").matches) {
      summary.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  drawDoctors();
  fill(
    timeStep,
    stepHead(
      2,
      "step-time",
      "Escolha o dia e o horário",
      "Disponível depois de escolher o médico.",
    ),
  );
  fill(
    patientStep,
    stepHead(
      3,
      "step-patient",
      "Escolha o paciente",
      "Disponível depois de escolher o horário.",
    ),
  );
  drawSummary();
}
