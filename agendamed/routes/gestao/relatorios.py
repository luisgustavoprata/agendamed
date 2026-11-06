"""Rota do painel de gestão (relatório do período)."""

from agendamed.routes.gestao._comum import OWNER, _auth, _g, _period, _today, bp


@bp.get("/reports/overview")
def overview():
    _auth(*OWNER)
    start, end = _period()
    return _g().overview(start, end, _today())
