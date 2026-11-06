/* AgendaMed — impressão: receitas e atestados e guias de convênio.
 *
 * Cada documento é montado numa janela própria e enviado para a impressora.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

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
