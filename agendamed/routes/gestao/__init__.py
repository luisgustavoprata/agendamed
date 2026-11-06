"""Rotas de prontuário, prescrições, financeiro, repasse, estoque e relatórios.

Nesta versão não há perfis de acesso: toda a equipe logada usa todas as telas,
inclusive prontuários.

Arquivos deste pacote (todos registram rotas no mesmo blueprint, `bp`):

    _comum.py       blueprint e ajudantes usados por todos
    prontuario.py   /patients/<id>/record...
    prescricoes.py  /patients/<id>/prescriptions e /prescriptions/<id>
    cadastros.py    /procedures e /health-plans
    financeiro.py   /finance/... e /appointments/<id>/charge
    estoque.py      /stock/...
    relatorios.py   /reports/overview
"""

# A ordem dos imports é a ordem em que as rotas são registradas (a mesma de antes).
from agendamed.routes.gestao import (  # noqa: F401 (importar já registra as rotas)
    prontuario,
    prescricoes,
    cadastros,
    financeiro,
    estoque,
    relatorios,
)
from agendamed.routes.gestao._comum import bp

__all__ = ["bp"]
