/* AgendaMed — janela de cadastrar ou editar um paciente.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

/** Cadastra um paciente novo ou, recebendo `patient`, edita o cadastro existente. */
function openPatientDialog(onSaved, patient = null) {
  const editing = Boolean(patient);
  openDialog(editing ? "Editar paciente" : "Cadastrar paciente", (close) => {
    const v = patient || {};
    const form = h(
      "form",
      { class: "form", novalidate: true },
      h("p", { class: "form__error", role: "alert", tabindex: "-1" }),
      field({
        label: "Nome completo",
        name: "name",
        required: true,
        autocomplete: "off",
        value: v.name ?? "",
      }),
      h(
        "div",
        { class: "form__row" },
        field({
          label: "CPF",
          name: "cpf",
          required: true,
          inputmode: "numeric",
          placeholder: "000.000.000-00",
          value: v.cpf ?? "",
        }),
        field({
          label: "Data de nascimento",
          name: "birth_date",
          type: "date",
          required: true,
          max: toISODate(new Date()),
          value: v.birth_date ?? "",
        }),
      ),
      h(
        "div",
        { class: "form__row" },
        field({
          label: "E-mail",
          name: "email",
          type: "email",
          required: true,
          value: v.email ?? "",
        }),
        field({
          label: "Telefone",
          name: "phone",
          type: "tel",
          inputmode: "tel",
          placeholder: "(00) 00000-0000",
          hint: "Opcional",
          value: v.phone ?? "",
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
          editing ? "Salvar alterações" : "Cadastrar paciente",
        ),
      ),
    );

    form.elements.cpf.addEventListener(
      "input",
      (e) => (e.target.value = maskCpf(e.target.value)),
    );
    form.elements.phone.addEventListener(
      "input",
      (e) => (e.target.value = maskPhone(e.target.value)),
    );
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = formValues(form);
      const body = { ...values, phone: values.phone || null };
      const submit = form.querySelector('[type="submit"]');
      submit.disabled = true;
      try {
        const saved = editing
          ? await api.patch(`/patients/${patient.id}`, body)
          : await api.post("/patients", body);
        close();
        toast(
          editing
            ? `Os dados de ${saved.name} foram atualizados.`
            : `${saved.name} foi cadastrado(a).`,
        );
        onSaved?.(saved);
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
