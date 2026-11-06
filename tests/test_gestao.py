"""Prontuário, prescrições, financeiro, repasse, guias de convênio, estoque e relatórios."""

from datetime import datetime

from tests.base import APITestCase


class GestaoBase(APITestCase):
    def setUp(self):
        super().setUp()
        self.headers = self.auth_headers()
        self.helena = self.create_doctor(self.headers)
        self.rafael = self.create_doctor(self.headers, name="Dr. Rafael Moura", crm="654321/GO")
        self.patient = self.create_patient(self.headers)

    def post(self, url, body, status=201):
        response = self.client.post(url, json=body, headers=self.headers)
        self.assertEqual(response.status_code, status, response.json)
        return response.json

    def get(self, url, status=200, headers=None):
        response = self.client.get(url, headers=self.headers if headers is None else headers)
        self.assertEqual(response.status_code, status, response.json)
        return response.json

    def appointment(self, start="2030-01-08T10:00", doctor=None):
        response = self.book(self.headers, (doctor or self.helena)["id"], self.patient["id"], start)
        self.assertEqual(response.status_code, 201, response.json)
        return response.json


class RecordTest(GestaoBase):
    def test_record_summary_and_entries(self):
        pid = self.patient["id"]
        self.client.put(
            f"/patients/{pid}/record/summary",
            headers=self.headers,
            json={"allergies": "Dipirona", "blood_type": "O+"},
        )
        entry = self.post(
            f"/patients/{pid}/record/entries",
            {
                "kind": "evolucao",
                "content": "Paciente estável.",
                "doctor_id": self.helena["id"],
            },
        )
        self.assertEqual(entry["doctor_name"], "Dra. Helena Prado")
        record = self.get(f"/patients/{pid}/record")
        self.assertEqual(record["summary"]["allergies"], "Dipirona")
        self.assertEqual(len(record["entries"]), 1)

    def test_requires_login(self):
        self.get(f"/patients/{self.patient['id']}/record", status=401, headers={})

    def test_unknown_patient(self):
        self.get("/patients/999/record", status=404)


class PrescriptionTest(GestaoBase):
    def test_prescription_needs_doctor_and_content(self):
        pid = self.patient["id"]
        self.post(
            f"/patients/{pid}/prescriptions", {"kind": "atestado", "text": "Repouso."}, status=422
        )
        self.post(
            f"/patients/{pid}/prescriptions",
            {"kind": "simples", "doctor_id": self.helena["id"]},
            status=422,
        )
        rx = self.post(
            f"/patients/{pid}/prescriptions",
            {
                "kind": "simples",
                "doctor_id": self.helena["id"],
                "items": [{"name": "Amoxicilina 500 mg", "instructions": "8/8h por 7 dias"}],
            },
        )
        full = self.get(f"/prescriptions/{rx['id']}")
        self.assertEqual(
            (full["doctor_crm"], full["items"][0]["name"]), ("123456/SP", "Amoxicilina 500 mg")
        )


class FinanceTest(GestaoBase):
    def setUp(self):
        super().setUp()
        self.consulta = self.post(
            "/procedures", {"name": "Consulta", "price_cents": 30000, "tuss_code": "10101012"}
        )
        self.plan = self.post("/health-plans", {"name": "Unimed", "ans_code": "123456"})
        self.caixa = self.post("/finance/accounts", {"name": "Caixa"})

    def test_charge_pay_and_cashflow(self):
        ap = self.appointment()
        tx = self.post(f"/appointments/{ap['id']}/charge", {"procedure_id": self.consulta["id"]})
        self.assertEqual((tx["amount_cents"], tx["status"]), (30000, "open"))
        self.post(
            f"/appointments/{ap['id']}/charge", {"procedure_id": self.consulta["id"]}, status=409
        )
        self.post(
            f"/finance/transactions/{tx['id']}/pay",
            {"paid_on": "2030-01-08", "account_id": self.caixa["id"]},
            status=200,
        )
        self.post(
            "/finance/transactions",
            {
                "kind": "expense",
                "description": "Aluguel",
                "category": "Aluguel",
                "amount_cents": 100000,
                "due_date": "2030-01-10",
            },
        )
        flow = self.get("/finance/cashflow?start=2030-01-01&end=2030-01-31")
        self.assertEqual(flow["totals"]["income_paid"], 30000)
        self.assertEqual(flow["totals"]["balance_forecast"], -70000)
        self.assertEqual(flow["accounts"][0]["balance_cents"], 30000)

    def test_payout_and_tiss(self):
        self.client.put(
            "/finance/payout-rules",
            headers=self.headers,
            json={"doctor_id": self.helena["id"], "percent": 40},
        )
        ap = self.appointment()
        self.post(
            f"/appointments/{ap['id']}/charge",
            {
                "procedure_id": self.consulta["id"],
                "health_plan_id": self.plan["id"],
                "amount_cents": 15000,
                "plan_card": "0001234",
                "paid_on": "2030-01-09",
            },
        )
        payouts = self.get("/finance/payouts?start=2030-01-01&end=2030-01-31")["items"]
        self.assertEqual(payouts[0]["payout_cents"], 6000)
        batch = self.get(
            f"/finance/tiss?health_plan_id={self.plan['id']}" "&start=2030-01-01&end=2030-01-31"
        )
        self.assertEqual(batch["guides"][0]["plan_card"], "0001234")

    def test_overview(self):
        self.appointment()
        report = self.get("/reports/overview?start=2030-01-01&end=2030-01-31")
        self.assertEqual(report["appointments"]["total"], 1)
        self.assertEqual(report["new_patients"], 1)


class StockTest(GestaoBase):
    def test_movements(self):
        item = self.post("/stock/items", {"name": "Luvas", "unit": "cx", "min_quantity": 2})
        item = self.post(f"/stock/items/{item['id']}/movements", {"delta": 5})
        self.assertEqual((item["quantity"], item["low"]), (5, False))
        self.post(f"/stock/items/{item['id']}/movements", {"delta": -9}, status=422)


class PeriodTest(GestaoBase):
    def test_default_period_is_current_month(self):
        self.now = datetime(2030, 2, 15, 9, 0)
        self.app.config["CLOCK"] = lambda: self.now
        flow = self.get("/finance/cashflow")
        self.assertEqual((flow["start"], flow["end"]), ("2030-02-01", "2030-02-28"))
