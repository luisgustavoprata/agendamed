"""Gestão da clínica: prontuário, prescrições, financeiro, repasse, estoque e relatórios.

Os dados da gestão são lidos e gravados pela classe `Gestao`. Ela é montada a partir de
várias partes menores, cada uma num arquivo, para ficar fácil achar cada assunto:

    base.py         conexão, clínica e conferências usadas por todas as partes
    prontuario.py   ficha clínica e registros do prontuário
    prescricoes.py  receitas, atestados, pedidos de exame e relatórios
    cadastros.py    procedimentos, convênios e contas
    financeiro.py   lançamentos, faturamento das consultas e fluxo de caixa
    repasse.py      parte de cada médico sobre o que foi recebido
    estoque.py      materiais, entradas e saídas
    relatorios.py   painel de gestão e guias de convênio
    schemas.py      formato dos dados que a API recebe (validação)

Cada parte é uma classe "mixin": ela tem só métodos e não funciona sozinha. A classe
`Gestao` herda de todas, então `Gestao(...).transactions(...)` funciona como se todos os
métodos estivessem num lugar só. Um método de uma parte pode chamar o de outra pelo `self`
(exemplo: o relatório usa `self.transactions`, que está em financeiro.py).

Uso: `Gestao(GestaoDb(get_db()), CLINIC_ID)`. Valores em dinheiro são inteiros em centavos.
"""

from agendamed.gestao.base import CLINIC_ID, GestaoBase, GestaoDb
from agendamed.gestao.cadastros import CadastrosMixin
from agendamed.gestao.estoque import EstoqueMixin
from agendamed.gestao.financeiro import FinanceiroMixin
from agendamed.gestao.prescricoes import PrescricoesMixin
from agendamed.gestao.prontuario import ProntuarioMixin
from agendamed.gestao.relatorios import RelatoriosMixin
from agendamed.gestao.repasse import RepasseMixin

__all__ = ["CLINIC_ID", "Gestao", "GestaoDb"]


class Gestao(
    ProntuarioMixin,
    PrescricoesMixin,
    CadastrosMixin,
    FinanceiroMixin,
    RepasseMixin,
    EstoqueMixin,
    RelatoriosMixin,
    GestaoBase,
):
    """Acesso aos dados de gestão da clínica (junta todas as partes do pacote)."""
