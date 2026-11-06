"""Repasse: a parte de cada médico sobre o que a clínica recebeu pelas consultas dele."""

from __future__ import annotations

from datetime import date

from agendamed.gestao.schemas import PayoutRuleSet


class RepasseMixin:
    """Regras de repasse (percentual por médico e procedimento) e o cálculo do período."""

    def payout_rules(self) -> list[dict]:
        rows = self.db.all(
            """SELECT r.id, r.doctor_id, d.name AS doctor_name, r.procedure_id,
                      p.name AS procedure_name, r.percent
               FROM payout_rules r JOIN doctors d ON d.id = r.doctor_id
               LEFT JOIN procedures p ON p.id = r.procedure_id
               WHERE r.clinic_id = ? ORDER BY d.name, p.name""",
            (self.clinic_id,),
        )
        return [dict(r) for r in rows]

    def set_payout_rule(self, data: PayoutRuleSet) -> list[dict]:
        self.require_doctor(data.doctor_id)
        if data.procedure_id is not None:
            self.procedure(data.procedure_id)
        proc_clause = "procedure_id = ?" if data.procedure_id else "procedure_id IS NULL"
        params = (data.doctor_id, data.procedure_id) if data.procedure_id else (data.doctor_id,)
        self.db.execute(
            f"DELETE FROM payout_rules WHERE clinic_id = ? AND doctor_id = ? AND {proc_clause}",
            (self.clinic_id, *params),
        )
        self.db.execute(
            "INSERT INTO payout_rules (clinic_id, doctor_id, procedure_id, percent) "
            "VALUES (?, ?, ?, ?)",
            (self.clinic_id, data.doctor_id, data.procedure_id, data.percent),
        )
        return self.payout_rules()

    def delete_payout_rule(self, rule_id: int) -> None:
        self.db.execute(
            "DELETE FROM payout_rules WHERE id = ? AND clinic_id = ?", (rule_id, self.clinic_id)
        )

    def payouts(self, start: date, end: date, today: str) -> list[dict]:
        """Repasse de cada médico sobre o que foi RECEBIDO no período."""
        rules = {(r["doctor_id"], r["procedure_id"]): r["percent"] for r in self.payout_rules()}
        report: dict[int, dict] = {}
        for tx in self.transactions(
            start=start, end=end, today=today, kind="income", status="paid"
        ):
            if not tx["doctor_id"]:
                continue
            percent = rules.get(
                (tx["doctor_id"], tx["procedure_id"]), rules.get((tx["doctor_id"], None), 0)
            )
            share = round(tx["amount_cents"] * percent / 100)
            doc = report.setdefault(
                tx["doctor_id"],
                {
                    "doctor_id": tx["doctor_id"],
                    "doctor_name": tx["doctor_name"],
                    "received_cents": 0,
                    "payout_cents": 0,
                    "items": [],
                },
            )
            doc["received_cents"] += tx["amount_cents"]
            doc["payout_cents"] += share
            doc["items"].append(
                {
                    "transaction_id": tx["id"],
                    "date": tx["paid_on"],
                    "description": tx["description"],
                    "amount_cents": tx["amount_cents"],
                    "percent": percent,
                    "payout_cents": share,
                }
            )
        return sorted(report.values(), key=lambda d: d["doctor_name"])
