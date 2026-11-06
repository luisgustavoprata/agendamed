/* AgendaMed — utilitários das telas de gestão (prontuário, financeiro, estoque, painel).
 *
 * Dinheiro (os valores vêm da API em centavos), datas, seletor de mês, abas internas,
 * números de destaque e o envio padrão de formulários.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

/** Formato de dinheiro em reais: "R$ 1.234,56". */
const moneyFmt = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
/** Centavos (como vêm da API) em reais: 123456 → "R$ 1.234,56". */
const fmtMoney = (cents) => moneyFmt.format((cents || 0) / 100);

/** "1.234,56", "1234.56" ou "300" → centavos. Devolve null se não for um valor válido. */
function parseMoney(text) {
  let raw = String(text ?? "").replace(/[^\d,.-]/g, "");
  if (!raw) return null;
  if (raw.includes(",")) raw = raw.replace(/\./g, "").replace(",", ".");
  const value = Number(raw);
  return Number.isFinite(value) && value >= 0 ? Math.round(value * 100) : null;
}

/** Centavos para o campo de valor: 123456 → "1234,56" (vazio se zero). */
const centsToInput = (cents) =>
  cents ? (cents / 100).toFixed(2).replace(".", ",") : "";
/** Data curta a partir de "AAAA-MM-DD..." (ou "—" se não houver). */
const fmtDate = (iso) =>
  iso ? fmtShortDate(parseISODate(iso.slice(0, 10))) : "—";
/** Data e hora curtas a partir de "AAAA-MM-DDTHH:MM" (ou "—"). */
const fmtDateTime = (iso) =>
  iso ? `${fmtDate(iso)} ${iso.slice(11, 16)}` : "—";

/** Nome em português de cada forma de pagamento. */
const PAYMENT_LABELS = {
  dinheiro: "Dinheiro",
  pix: "Pix",
  cartao_credito: "Cartão de crédito",
  cartao_debito: "Cartão de débito",
  boleto: "Boleto",
  transferencia: "Transferência",
  convenio: "Convênio",
};
/** Tipos de registro do prontuário, para o campo de escolha. */
const RECORD_KIND_OPTIONS = [
  ["evolucao", "Evolução"],
  ["anamnese", "Anamnese"],
  ["exame_fisico", "Exame físico"],
  ["diagnostico", "Hipótese diagnóstica"],
  ["conduta", "Conduta"],
  ["exame", "Resultado de exame"],
  ["anotacao", "Anotação"],
];
/** Tipos de documento (receitas, atestado, exames, relatório). */
const RX_KIND_OPTIONS = [
  ["simples", "Receituário simples"],
  ["controle_especial", "Receituário de controle especial"],
  ["atestado", "Atestado médico"],
  ["exames", "Solicitação de exames"],
  ["relatorio", "Relatório médico"],
];
/** Tipos sanguíneos para a ficha clínica (o vazio = não informado). */
const BLOOD_TYPES = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
/* Nesta versão não há perfis: toda a equipe usa todas as telas. */
const isOwner = () => true;
/** Nesta versão não há perfil de médico: sempre falso. */
const isDoctorUser = () => false;
/** Nome da clínica (vem de CLINIC_BRAND), usado nos documentos impressos. */
const clinicName = () => CLINIC_BRAND.name;

/** Mês escolhido (AAAA-MM) → início e fim, no formato da API. */
function monthRange(month) {
  const [y, m] = month.split("-").map(Number);
  return {
    start: toISODate(new Date(y, m - 1, 1)),
    end: toISODate(new Date(y, m, 0)),
  };
}
/** O mês atual no formato "AAAA-MM". */
const currentMonth = () => toISODate(new Date()).slice(0, 7);

/** Campo de escolha do mês; onChange recebe o mês escolhido ("AAAA-MM"). */
function monthPicker(value, onChange) {
  const wrap = field({ label: "Mês", name: "month", type: "month", value });
  wrap
    .querySelector("input")
    .addEventListener(
      "change",
      (e) => e.target.value && onChange(e.target.value),
    );
  return wrap;
}

/** Abas internas de uma tela. `tabs`: [[chave, rótulo], ...]. */
function subTabs(tabs, active, onPick) {
  return h(
    "div",
    { class: "subtabs", role: "tablist" },
    tabs.filter(Boolean).map(([key, label]) =>
      h(
        "button",
        {
          class: "subtabs__btn",
          type: "button",
          role: "tab",
          "aria-selected": String(key === active),
          onclick: () => onPick(key),
        },
        label,
      ),
    ),
  );
}

/** Número de destaque com rótulo (ex.: "Recebido no mês"). */
function stat(label, value, tone = "") {
  return h(
    "div",
    { class: `stat ${tone ? `stat--${tone}` : ""}` },
    h("p", { class: "stat__label" }, label),
    h("p", { class: "stat__value" }, value),
  );
}

/** Barra horizontal simples (proporção do maior valor). */
function bar(value, max, tone = "") {
  const pct = max > 0 ? Math.max(2, Math.round((100 * value) / max)) : 0;
  return h("span", {
    class: `bar ${tone ? `bar--${tone}` : ""}`,
    style: `--w:${pct}%`,
    "aria-hidden": "true",
  });
}

/**
 * Executa uma chamada à API e devolve o resultado; se der erro, mostra o aviso e
 * devolve null (quem chama só precisa conferir se veio null).
 */
async function safe(fn) {
  try {
    return await fn();
  } catch (err) {
    handleError(err);
    return null;
  }
}

/**
 * Envio padrão de formulário: desliga o botão, chama `request`, mostra os erros nos
 * campos (se houver) e chama `onOk` com o resultado quando dá certo.
 */
async function submitForm(form, request, onOk) {
  const submit = form.querySelector('[type="submit"]');
  if (submit) submit.disabled = true;
  clearFormErrors(form);
  try {
    const result = await request();
    onOk(result);
  } catch (err) {
    if (err.status !== 401) showFormErrors(form, err);
  } finally {
    if (submit) submit.disabled = false;
  }
}

/** Botões do rodapé de uma janela: Cancelar e o botão principal. */
function formActions(close, label) {
  return h(
    "div",
    { class: "form__actions" },
    h(
      "button",
      { class: "btn btn--ghost", type: "button", onclick: close },
      "Cancelar",
    ),
    h("button", { class: "btn btn--primary", type: "submit" }, label),
  );
}
