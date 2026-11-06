/* AgendaMed — identidade da Clínica Vida: nome, iniciais, cores e o cabeçalho com a marca.
 *
 * Para usar o sistema com outra clínica, comece trocando CLINIC_BRAND.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

/* Login com a marca da clínica: cada clínica entraria com o próprio logo e a própria cor,
   e o AgendaMed aparece só como assinatura. Aqui, uma clínica de exemplo. */
const CLINIC_BRAND = {
  name: "Clínica Vida",
  initials: "CV",
  tagline: "Agenda da equipe",
  // Linha sob o nome no cabeçalho da entrada (clínica de exemplo).
  specialties: "Cardiologia · Pediatria · Dermatologia",
  // Saem no cabeçalho das receitas, atestados e pedidos de exame.
  address: "Rua das Palmeiras, 250, Centro, Rio Verde/GO",
  phone: "(64) 3620-0000",
  // Cor da clínica no sistema todo: botões, aba ativa, consultas na agenda e destaques.
  colors: {
    main: "#3f6b57",
    deep: "#2f5343",
    ink: "#24402f",
    wash: "#e8f0ea",
    line: "#c4d6ca",
  },
};

/** Pinta o sistema com a cor da clínica (troca os tons de destaque usados pelo CSS). */
function applyClinicTheme(colors) {
  const style = document.documentElement.style;
  style.setProperty("--navy", colors.main);
  style.setProperty("--navy-deep", colors.deep);
  style.setProperty("--navy-ink", colors.ink);
  style.setProperty("--navy-wash", colors.wash);
  style.setProperty("--navy-line", colors.line);
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", colors.ink);
}

/**
 * Bloco com a marca da clínica (iniciais e nome). Hoje nenhuma tela usa esta função.
 */
function clinicHeader() {
  return h(
    "div",
    { class: "clinic-mark" },
    h(
      "span",
      { class: "clinic-mark__logo", "aria-hidden": "true" },
      CLINIC_BRAND.initials,
    ),
    h(
      "div",
      null,
      h("p", { class: "clinic-mark__name" }, CLINIC_BRAND.name),
      h("p", { class: "clinic-mark__tagline" }, CLINIC_BRAND.tagline),
    ),
  );
}
