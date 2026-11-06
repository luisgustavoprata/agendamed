/* AgendaMed — janela de cadastro de médico.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

function openDoctorDialog(onCreated) {
  openDialog("Cadastrar médico", (close) => {
    const form = h(
      "form",
      { class: "form", novalidate: true },
      h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
      field({
        label: "Nome completo",
        name: "name",
        required: true,
        autocomplete: "off",
      }),
      h(
        "div",
        { class: "form__row" },
        field({ label: "Especialidade", name: "specialty", required: true }),
        field({
          label: "CRM",
          name: "crm",
          required: true,
          hint: "Número e UF, como 123456/SP",
        }),
      ),
      h(
        "div",
        { class: "form__row" },
        field({
          label: "Início do expediente",
          name: "work_start",
          type: "time",
          value: "08:00",
          required: true,
        }),
        field({
          label: "Fim do expediente",
          name: "work_end",
          type: "time",
          value: "18:00",
          required: true,
        }),
        field({
          label: "Duração da consulta",
          name: "slot_minutes",
          as: "select",
          value: "30",
          options: [
            [15, "15 minutos"],
            [20, "20 minutos"],
            [30, "30 minutos"],
            [45, "45 minutos"],
            [60, "1 hora"],
          ],
        }),
      ),
      h(
        "div",
        { class: "form__actions" },
        h(
          "button",
          { class: "btn btn--ghost", type: "button", onclick: close },
          "Cancelar",
        ),
        h(
          "button",
          { class: "btn btn--primary", type: "submit" },
          "Cadastrar médico",
        ),
      ),
    );

    form.elements.crm.addEventListener(
      "input",
      (e) => (e.target.value = e.target.value.toUpperCase()),
    );
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = formValues(form);
      const submit = form.querySelector('[type="submit"]');
      submit.disabled = true;
      try {
        const doctor = await api.post("/doctors", {
          ...values,
          slot_minutes: Number(values.slot_minutes),
        });
        state.doctors = null;
        close();
        toast(`${doctor.name} foi cadastrado(a).`);
        onCreated?.(doctor);
      } catch (err) {
        if (err.status === 401) return;
        showFormErrors(form, err);
      } finally {
        submit.disabled = false;
      }
    });
    return form;
  });
}
