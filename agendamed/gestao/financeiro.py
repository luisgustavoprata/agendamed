"""Financeiro: contas a pagar e a receber, faturamento das consultas e fluxo de caixa.

Cada lançamento é uma receita (income) ou uma despesa (expense). Ele fica "em aberto" até
receber a data de pagamento (`paid_on`) e fica "vencido" se a data de vencimento passou.
"""

from __future__ import annotations

from datetime import date

from agendamed.errors import BusinessRuleError, ConflictError, NotFoundError
from agendamed.gestao.base import _iso
from agendamed.gestao.schemas import (
    AppointmentCharge,
    TransactionCreate,
    TransactionPay,
    TransactionUpdate,
)


class FinanceiroMixin:
    """Lançamentos, faturamento de consultas e fluxo de caixa."""

    _TX_SELECT = """
        SELECT t.id, t.kind, t.description, t.category, t.amount_cents, t.due_date, t.paid_on,
               t.payment_method, t.account_id, fa.name AS account_name,
               t.doctor_id, d.name AS doctor_name, t.patient_id, p.name AS patient_name,
               t.appointment_id, t.procedure_id, pc.name AS procedure_name,
               pc.tuss_code AS procedure_tuss, t.health_plan_id, hp.name AS health_plan_name,
               t.plan_card, t.plan_guide
        FROM finance_transactions t
        LEFT JOIN finance_accounts fa ON fa.id = t.account_id
        LEFT JOIN doctors d ON d.id = t.doctor_id
        LEFT JOIN patients p ON p.id = t.patient_id
        LEFT JOIN procedures pc ON pc.id = t.procedure_id
        LEFT JOIN health_plans hp ON hp.id = t.health_plan_id
    """

    @staticmethod
    def _tx(row, today: str) -> dict:
        item = dict(row)
        if item["paid_on"]:
            item["status"] = "paid"
        else:
            item["status"] = "overdue" if item["due_date"] < today else "open"
        return item

    def transaction(self, tx_id: int, today: str) -> dict:
        row = self.db.one(
            f"{self._TX_SELECT} WHERE t.id = ? AND t.clinic_id = ?", (tx_id, self.clinic_id)
        )
        if row is None:
            raise NotFoundError("Lançamento não encontrado.")
        return self._tx(row, today)

    def transactions(
        self,
        *,
        start: date,
        end: date,
        today: str,
        kind: str | None = None,
        status: str | None = None,
        account_id: int | None = None,
        health_plan_id: int | None = None,
    ) -> list[dict]:
        # Pago: entra pela data do pagamento. Em aberto: pela data de vencimento.
        where = ["t.clinic_id = ?", "COALESCE(t.paid_on, t.due_date) BETWEEN ? AND ?"]
        params: list = [self.clinic_id, start.isoformat(), end.isoformat()]
        if kind:
            where.append("t.kind = ?")
            params.append(kind)
        if status == "paid":
            where.append("t.paid_on IS NOT NULL")
        elif status == "open":
            where.append("t.paid_on IS NULL")
        if account_id:
            where.append("t.account_id = ?")
            params.append(account_id)
        if health_plan_id:
            where.append("t.health_plan_id = ?")
            params.append(health_plan_id)
        rows = self.db.all(
            f"{self._TX_SELECT} WHERE {' AND '.join(where)} "
            "ORDER BY COALESCE(t.paid_on, t.due_date), t.id",
            params,
        )
        return [self._tx(r, today) for r in rows]

    def _check_links(self, *, account_id=None, doctor_id=None, patient_id=None) -> None:
        self._require_in_clinic("finance_accounts", account_id, "Conta não encontrada.")
        self._require_in_clinic("doctors", doctor_id, "Médico não encontrado.")
        self._require_in_clinic("patients", patient_id, "Paciente não encontrado.")

    def add_transaction(self, data: TransactionCreate, today: str) -> dict:
        self._check_links(
            account_id=data.account_id, doctor_id=data.doctor_id, patient_id=data.patient_id
        )
        tx_id = self.db.insert(
            """INSERT INTO finance_transactions (clinic_id, kind, description, category,
                   amount_cents, due_date, paid_on, payment_method, account_id, doctor_id,
                   patient_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self.clinic_id,
                data.kind,
                data.description,
                data.category,
                data.amount_cents,
                data.due_date.isoformat(),
                _iso(data.paid_on),
                data.payment_method,
                data.account_id,
                data.doctor_id,
                data.patient_id,
            ),
        )
        return self.transaction(tx_id, today)

    def update_transaction(self, tx_id: int, data: TransactionUpdate, today: str) -> dict:
        self.transaction(tx_id, today)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        if changes:
            if "due_date" in changes:
                changes["due_date"] = changes["due_date"].isoformat()
            sets = ", ".join(f"{name} = ?" for name in changes)
            self.db.execute(
                f"UPDATE finance_transactions SET {sets} WHERE id = ? AND clinic_id = ?",
                (*changes.values(), tx_id, self.clinic_id),
            )
        return self.transaction(tx_id, today)

    def pay_transaction(self, tx_id: int, data: TransactionPay, today: str) -> dict:
        tx = self.transaction(tx_id, today)
        if tx["paid_on"]:
            raise ConflictError("Este lançamento já foi pago.")
        self._check_links(account_id=data.account_id)
        self.db.execute(
            """UPDATE finance_transactions SET paid_on = ?, account_id = COALESCE(?, account_id),
               payment_method = COALESCE(?, payment_method) WHERE id = ? AND clinic_id = ?""",
            (data.paid_on.isoformat(), data.account_id, data.payment_method, tx_id, self.clinic_id),
        )
        return self.transaction(tx_id, today)

    def unpay_transaction(self, tx_id: int, today: str) -> dict:
        self.transaction(tx_id, today)
        self.db.execute(
            "UPDATE finance_transactions SET paid_on = NULL WHERE id = ? AND clinic_id = ?",
            (tx_id, self.clinic_id),
        )
        return self.transaction(tx_id, today)

    def delete_transaction(self, tx_id: int, today: str) -> None:
        tx = self.transaction(tx_id, today)
        if tx["paid_on"]:
            raise ConflictError("Desfaça o pagamento antes de excluir o lançamento.")
        self.db.execute(
            "DELETE FROM finance_transactions WHERE id = ? AND clinic_id = ?",
            (tx_id, self.clinic_id),
        )

    def charge_appointment(self, appointment_id: int, data: AppointmentCharge, today: str) -> dict:
        """Cria a conta a receber de uma consulta (uma por consulta)."""
        appointment = self.require_appointment(appointment_id)
        if appointment["status"] == "cancelled":
            raise ConflictError("Consulta cancelada não pode ser faturada.")
        procedure = self.procedure(data.procedure_id)
        plan = self.health_plan(data.health_plan_id) if data.health_plan_id else None
        amount = data.amount_cents if data.amount_cents is not None else procedure["price_cents"]
        if amount <= 0:
            raise BusinessRuleError("Informe o valor da consulta.")
        self._check_links(account_id=data.account_id)
        description = f"{procedure['name']} — {appointment['patient_name']}"
        method = data.payment_method or ("convenio" if plan else None)
        tx_id = self._insert(
            """INSERT INTO finance_transactions (clinic_id, kind, description, category,
                   amount_cents, due_date, paid_on, payment_method, account_id, doctor_id,
                   patient_id, appointment_id, procedure_id, health_plan_id, plan_card,
                   plan_guide)
               VALUES (?, 'income', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                self.clinic_id,
                description,
                "Convênio" if plan else "Consultas particulares",
                amount,
                appointment["start_at"][:10],
                _iso(data.paid_on),
                method,
                data.account_id,
                appointment["doctor_id"],
                appointment["patient_id"],
                appointment_id,
                procedure["id"],
                plan["id"] if plan else None,
                data.plan_card,
                data.plan_guide,
            ),
            "Esta consulta já foi faturada.",
        )
        return self.transaction(tx_id, today)

    def appointment_charge(self, appointment_id: int, today: str) -> dict | None:
        row = self.db.one(
            f"{self._TX_SELECT} WHERE t.appointment_id = ? AND t.clinic_id = ?",
            (appointment_id, self.clinic_id),
        )
        return self._tx(row, today) if row else None

    def release_appointment_charge(self, appointment_id: int) -> None:
        """Consulta cancelada: a cobrança em aberto sai do financeiro.

        Se já foi paga, fica (o dinheiro entrou; devolução é um lançamento à parte).
        """
        self.db.execute(
            """DELETE FROM finance_transactions
               WHERE appointment_id = ? AND clinic_id = ? AND paid_on IS NULL""",
            (appointment_id, self.clinic_id),
        )

    def cashflow(self, start: date, end: date, today: str) -> dict:
        """Fluxo de caixa: realizado (pago) e previsto (em aberto), por dia e por categoria."""
        txs = self.transactions(start=start, end=end, today=today)
        days: dict[str, dict] = {}
        categories: dict[tuple[str, str], int] = {}
        totals = {
            "income_paid": 0,
            "expense_paid": 0,
            "income_open": 0,
            "expense_open": 0,
            "overdue_income": 0,
            "overdue_expense": 0,
        }
        for tx in txs:
            paid = tx["status"] == "paid"
            key = f"{tx['kind']}_{'paid' if paid else 'open'}"
            totals[key] += tx["amount_cents"]
            if tx["status"] == "overdue":
                totals[f"overdue_{tx['kind']}"] += tx["amount_cents"]
            day = days.setdefault(
                tx["paid_on"] or tx["due_date"], {"income_cents": 0, "expense_cents": 0}
            )
            day[f"{tx['kind']}_cents"] += tx["amount_cents"]
            if paid:
                cat = (tx["kind"], tx["category"])
                categories[cat] = categories.get(cat, 0) + tx["amount_cents"]
        totals["balance_paid"] = totals["income_paid"] - totals["expense_paid"]
        totals["balance_forecast"] = (
            totals["balance_paid"] + totals["income_open"] - totals["expense_open"]
        )
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "totals": totals,
            "days": [{"date": d, **v} for d, v in sorted(days.items())],
            "categories": [
                {"kind": k, "category": c, "amount_cents": v}
                for (k, c), v in sorted(categories.items(), key=lambda i: -i[1])
            ],
            "accounts": self.accounts(),
        }
