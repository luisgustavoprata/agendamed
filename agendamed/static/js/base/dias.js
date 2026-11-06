/* AgendaMed — dias úteis: fim de semana, próximo dia útil e a faixa de dias da tela
 *
 * Agendar.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

/** É sábado ou domingo? (a clínica não atende no fim de semana) */
const isWeekend = (date) => date.getDay() === 0 || date.getDay() === 6;

/**
 * O próximo dia útil depois de `from` (com `includeFrom`, a própria data vale, se for
 * dia útil).
 */
function nextWorkingDay(from, includeFrom) {
  let day = includeFrom ? new Date(from) : addDays(from, 1);
  while (isWeekend(day)) day = addDays(day, 1);
  return day;
}

/** Os próximos `count` dias úteis, começando por hoje se hoje for dia útil. */
function upcomingWorkingDays(count) {
  const days = [];
  let day = new Date();
  day.setHours(0, 0, 0, 0);
  while (days.length < count) {
    if (!isWeekend(day)) days.push(new Date(day));
    day = addDays(day, 1);
  }
  return days;
}
