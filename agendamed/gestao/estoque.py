"""Estoque: materiais da clínica, entradas e saídas, e o alerta de estoque baixo."""

from __future__ import annotations

from agendamed.errors import BusinessRuleError, ConflictError
from agendamed.gestao.base import _bools
from agendamed.gestao.schemas import StockItemCreate, StockItemUpdate, StockMovementCreate


class EstoqueMixin:
    """Itens de estoque e o histórico de movimentações de cada um."""

    def stock_items(self) -> list[dict]:
        """Os itens de estoque (os ativos primeiro), com o aviso `low` de estoque baixo."""
        rows = self.db.all(
            "SELECT id, name, unit, quantity, min_quantity, active FROM stock_items "
            "WHERE clinic_id = ? ORDER BY active DESC, name",
            (self.clinic_id,),
        )
        return [
            _bools({**dict(r), "low": r["quantity"] <= r["min_quantity"]}, "active") for r in rows
        ]

    def stock_item(self, item_id: int) -> dict:
        """Um item pelo id, com o aviso de estoque baixo; senão, erro 404."""
        item = self._get(
            "stock_items",
            "id, name, unit, quantity, min_quantity, active",
            item_id,
            "Item de estoque não encontrado.",
        )
        item["low"] = item["quantity"] <= item["min_quantity"]
        return item

    def add_stock_item(self, data: StockItemCreate) -> dict:
        """Cadastra um item (começa com quantidade zero)."""
        new_id = self._insert(
            "INSERT INTO stock_items (clinic_id, name, unit, min_quantity) VALUES (?, ?, ?, ?)",
            (self.clinic_id, data.name, data.unit, data.min_quantity),
            "Já existe um item com este nome.",
        )
        return self.stock_item(new_id)

    def update_stock_item(self, item_id: int, data: StockItemUpdate) -> dict:
        """Altera os campos enviados do item (nome, unidade, mínimo ou ativo)."""
        self.stock_item(item_id)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        if "active" in changes:
            changes["active"] = int(changes["active"])
        if changes:
            sets = ", ".join(f"{name} = ?" for name in changes)
            try:
                self.db.execute(
                    f"UPDATE stock_items SET {sets} WHERE id = ? AND clinic_id = ?",
                    (*changes.values(), item_id, self.clinic_id),
                )
            except self.db.integrity_errors as exc:
                raise ConflictError("Já existe um item com este nome.") from exc
        return self.stock_item(item_id)

    def move_stock(self, item_id: int, data: StockMovementCreate, user_id: int, now: str) -> dict:
        """Registra uma entrada (positivo) ou saída (negativo) e atualiza a quantidade.

        A trava da transação impede que duas saídas ao mesmo tempo deixem o estoque negativo; a
        saída maior que o saldo é recusada.
        """
        with self.db.transaction(lock_keys=(f"stock:{item_id}",)):
            item = self.stock_item(item_id)
            if item["quantity"] + data.delta < 0:
                raise BusinessRuleError(
                    f"Estoque insuficiente: há {item['quantity']} {item['unit']} de "
                    f"{item['name']}."
                )
            self.db.execute(
                "UPDATE stock_items SET quantity = quantity + ? WHERE id = ? AND clinic_id = ?",
                (data.delta, item_id, self.clinic_id),
            )
            self.db.execute(
                "INSERT INTO stock_movements (clinic_id, item_id, delta, reason, created_by, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (self.clinic_id, item_id, data.delta, data.reason, user_id, now),
            )
        return self.stock_item(item_id)

    def stock_movements(self, item_id: int) -> list[dict]:
        """As últimas 200 movimentações do item, da mais nova à mais antiga."""
        self.stock_item(item_id)
        rows = self.db.all(
            """SELECT m.id, m.delta, m.reason, m.created_at, u.full_name AS author
               FROM stock_movements m JOIN users u ON u.id = m.created_by
               WHERE m.item_id = ? AND m.clinic_id = ? ORDER BY m.created_at DESC, m.id DESC
               LIMIT 200""",
            (item_id, self.clinic_id),
        )
        return [dict(r) for r in rows]
