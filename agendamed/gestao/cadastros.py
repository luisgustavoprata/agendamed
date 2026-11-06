"""Cadastros da gestão: procedimentos (com preço), convênios e contas (Caixa, Banco...)."""

from __future__ import annotations

from agendamed.errors import ConflictError
from agendamed.gestao.base import _bools
from agendamed.gestao.schemas import FinanceAccountCreate, HealthPlanCreate, ProcedureCreate


class CadastrosMixin:
    """Listar, criar e alterar procedimentos, convênios e contas."""

    def procedures(self, only_active=False) -> list[dict]:
        return self._list(
            "procedures", "id, name, tuss_code, price_cents, active", only_active=only_active
        )

    def health_plans(self, only_active=False) -> list[dict]:
        return self._list("health_plans", "id, name, ans_code, active", only_active=only_active)

    def accounts(self) -> list[dict]:
        rows = self.db.all(
            """SELECT a.id, a.name, a.active,
                      COALESCE(SUM(CASE WHEN t.kind = 'income' THEN t.amount_cents
                                        ELSE -t.amount_cents END), 0) AS balance_cents
               FROM finance_accounts a
               LEFT JOIN finance_transactions t
                      ON t.account_id = a.id AND t.paid_on IS NOT NULL
               WHERE a.clinic_id = ? GROUP BY a.id, a.name, a.active ORDER BY a.name""",
            (self.clinic_id,),
        )
        return [_bools(dict(r), "active") for r in rows]

    def procedure(self, procedure_id: int) -> dict:
        return self._get(
            "procedures",
            "id, name, tuss_code, price_cents, active",
            procedure_id,
            "Procedimento não encontrado.",
        )

    def health_plan(self, plan_id: int) -> dict:
        return self._get(
            "health_plans", "id, name, ans_code, active", plan_id, "Convênio não encontrado."
        )

    def save_procedure(self, data: ProcedureCreate, procedure_id: int | None = None) -> dict:
        values = (data.name, data.tuss_code, data.price_cents, int(data.active))
        conflict = "Já existe um procedimento com este nome."
        if procedure_id is None:
            procedure_id = self._insert(
                "INSERT INTO procedures (name, tuss_code, price_cents, active, clinic_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (*values, self.clinic_id),
                conflict,
            )
        else:
            self.procedure(procedure_id)
            try:
                self.db.execute(
                    "UPDATE procedures SET name = ?, tuss_code = ?, price_cents = ?, active = ? "
                    "WHERE id = ? AND clinic_id = ?",
                    (*values, procedure_id, self.clinic_id),
                )
            except self.db.integrity_errors as exc:
                raise ConflictError(conflict) from exc
        return self.procedure(procedure_id)

    def save_health_plan(self, data: HealthPlanCreate, plan_id: int | None = None) -> dict:
        values = (data.name, data.ans_code, int(data.active))
        conflict = "Já existe um convênio com este nome."
        if plan_id is None:
            plan_id = self._insert(
                "INSERT INTO health_plans (name, ans_code, active, clinic_id) VALUES (?, ?, ?, ?)",
                (*values, self.clinic_id),
                conflict,
            )
        else:
            self.health_plan(plan_id)
            try:
                self.db.execute(
                    "UPDATE health_plans SET name = ?, ans_code = ?, active = ? "
                    "WHERE id = ? AND clinic_id = ?",
                    (*values, plan_id, self.clinic_id),
                )
            except self.db.integrity_errors as exc:
                raise ConflictError(conflict) from exc
        return self.health_plan(plan_id)

    def add_account(self, data: FinanceAccountCreate) -> dict:
        new_id = self._insert(
            "INSERT INTO finance_accounts (name, clinic_id) VALUES (?, ?)",
            (data.name, self.clinic_id),
            "Já existe uma conta com este nome.",
        )
        return next(a for a in self.accounts() if a["id"] == new_id)
