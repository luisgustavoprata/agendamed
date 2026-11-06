"""Relatórios de gestão: o painel do mês e as guias de convênio para imprimir em lote."""

from __future__ import annotations

from datetime import date


class RelatoriosMixin:
    """Painel de gestão (consultas, faturamento, estoque) e lote de guias TISS."""

    def overview(self, start: date, end: date, today: str) -> dict:
        """O painel de gestão do período.

        Junta as consultas por situação (inclusive as prováveis faltas), os pacientes novos, o fluxo
        de caixa, o faturamento por médico e por convênio e os itens com estoque baixo.
        """
        # Limites do período como texto, para comparar com start_at (o dia final inteiro conta).
        start_s, end_s = start.isoformat(), f"{end.isoformat()}T23:59:59"
        # Consultas do período, contadas por situação: {"scheduled": 10, "completed": 25, ...}.
        by_status = {
            r["status"]: r["total"]
            for r in self.db.all(
                "SELECT status, COUNT(*) AS total FROM appointments WHERE clinic_id = ? "
                "AND start_at BETWEEN ? AND ? GROUP BY status",
                (self.clinic_id, start_s, end_s),
            )
        }
        # Agendadas cujo horário já passou e ninguém concluiu: provável falta.
        missed = self.db.one(
            "SELECT COUNT(*) AS total FROM appointments WHERE clinic_id = ? AND status = "
            "'scheduled' AND start_at BETWEEN ? AND ? AND start_at < ?",
            (self.clinic_id, start_s, end_s, today),
        )["total"]
        # Cada médico ativo, com quantas consultas teve no período (concluídas e canceladas).
        doctors = self.db.all(
            """SELECT d.id, d.name,
                      SUM(CASE WHEN a.status = 'completed' THEN 1 ELSE 0 END) AS completed,
                      SUM(CASE WHEN a.status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
                      COUNT(a.id) AS total
               FROM doctors d LEFT JOIN appointments a ON a.doctor_id = d.id
                    AND a.start_at BETWEEN ? AND ?
               WHERE d.clinic_id = ? AND d.active = 1 GROUP BY d.id, d.name ORDER BY d.name""",
            (start_s, end_s, self.clinic_id),
        )
        # Faturamento: soma o que foi RECEBIDO no período por médico e por convênio (ou
        # "Particular").
        revenue = {}
        by_plan: dict[str, int] = {}
        for tx in self.transactions(
            start=start, end=end, today=today, kind="income", status="paid"
        ):
            if tx["doctor_id"]:
                revenue[tx["doctor_id"]] = revenue.get(tx["doctor_id"], 0) + tx["amount_cents"]
            plan = tx["health_plan_name"] or "Particular"
            by_plan[plan] = by_plan.get(plan, 0) + tx["amount_cents"]
        # Pacientes novos: aqueles cuja PRIMEIRA consulta (não cancelada) caiu no período.
        new_patients = self.db.one(
            """SELECT COUNT(*) AS total FROM (
                   SELECT patient_id, MIN(start_at) AS first FROM appointments
                   WHERE clinic_id = ? AND status <> 'cancelled' GROUP BY patient_id) f
               WHERE f.first BETWEEN ? AND ?""",
            (self.clinic_id, start_s, end_s),
        )["total"]
        total = sum(by_status.values())
        cash = self.cashflow(start, end, today)["totals"]
        low_stock = [i for i in self.stock_items() if i["active"] and i["low"]]
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "appointments": {
                "total": total,
                "scheduled": by_status.get("scheduled", 0),
                "completed": by_status.get("completed", 0),
                "cancelled": by_status.get("cancelled", 0),
                "missed": missed,
                "cancel_rate": round(100 * by_status.get("cancelled", 0) / total, 1)
                if total
                else 0,
            },
            "new_patients": new_patients,
            "finance": cash,
            "doctors": [
                {
                    **dict(d),
                    "completed": d["completed"] or 0,
                    "cancelled": d["cancelled"] or 0,
                    "revenue_cents": revenue.get(d["id"], 0),
                }
                for d in doctors
            ],
            "revenue_by_plan": [
                {"name": k, "amount_cents": v}
                for k, v in sorted(by_plan.items(), key=lambda i: -i[1])
            ],
            "low_stock": low_stock,
        }

    def tiss_batch(self, plan_id: int, start: date, end: date, today: str) -> dict:
        """Guias de consulta de um convênio no período, prontas para imprimir em lote."""
        plan = self.health_plan(plan_id)
        # Reaproveita a busca padrão de lançamentos (_TX_SELECT, em financeiro.py) e põe no
        # começo da lista de colunas os dados que a guia precisa: a data da consulta, o CRM e
        # a especialidade do médico, o CPF e o nascimento do paciente.
        rows = self.db.all(
            f"""{self._TX_SELECT.replace('SELECT t.id,', '''SELECT a.start_at,
                   d.crm AS doctor_crm, d.specialty AS doctor_specialty, p.cpf AS patient_cpf,
                   p.birth_date AS patient_birth_date, t.id,''')}
                JOIN appointments a ON a.id = t.appointment_id
                WHERE t.clinic_id = ? AND t.health_plan_id = ?
                  AND a.start_at BETWEEN ? AND ?
                ORDER BY a.start_at""",
            (self.clinic_id, plan_id, start.isoformat(), f"{end.isoformat()}T23:59:59"),
        )
        guides = [self._tx(r, today) for r in rows]
        return {
            "health_plan": plan,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "total_cents": sum(g["amount_cents"] for g in guides),
            "guides": guides,
        }
