"""Rotas do estoque: itens, entradas e saídas."""

from agendamed.gestao.schemas import StockItemCreate, StockItemUpdate, StockMovementCreate
from agendamed.routes._helpers import parse_body
from agendamed.routes.gestao._comum import FINANCE, _auth, _g, _now, bp, current_user


@bp.get("/stock/items")
def list_stock():
    _auth(*FINANCE)
    return {"items": _g().stock_items()}


@bp.post("/stock/items")
def create_stock_item():
    _auth(*FINANCE)
    return _g().add_stock_item(parse_body(StockItemCreate)), 201


@bp.patch("/stock/items/<int:item_id>")
def update_stock_item(item_id: int):
    _auth(*FINANCE)
    return _g().update_stock_item(item_id, parse_body(StockItemUpdate))


@bp.get("/stock/items/<int:item_id>/movements")
def stock_movements(item_id: int):
    _auth(*FINANCE)
    return {"items": _g().stock_movements(item_id)}


@bp.post("/stock/items/<int:item_id>/movements")
def move_stock(item_id: int):
    _auth(*FINANCE)
    return _g().move_stock(item_id, parse_body(StockMovementCreate), current_user().id, _now()), 201
