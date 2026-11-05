import os
import tempfile
import unittest
from datetime import datetime

from agendamed import create_app
from tests.base import NOW


class SeedTest(unittest.TestCase):
    def test_demo_data_is_created_once_on_startup(self):
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.remove, db_path)
        config = {
            "TESTING": True,
            "DATABASE": db_path,
            "SEED_DEMO_DATA": True,
            "PASSWORD_HASH_ITERATIONS": 1_000,
            "CLOCK": lambda: NOW,  # segunda-feira, 09:00
        }

        create_app(config)
        app = create_app(config)  # reiniciar não duplica os dados

        client = app.test_client()
        token = client.post(
            "/auth/login", json={"email": "admin@agendamed.dev", "password": "admin12345"}
        ).json["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        self.assertEqual(client.get("/doctors", headers=headers).json["total"], 3)
        today = client.get("/appointments?date=2030-01-07", headers=headers).json
        tomorrow = client.get("/appointments?date=2030-01-08", headers=headers).json
        # Hoje, a consulta das 09:00 já não pode ser marcada (é "agora"); amanhã entram todas.
        self.assertEqual(today["total"], 6)
        self.assertEqual(tomorrow["total"], 7)


class ExampleDataTest(unittest.TestCase):
    """Exemplos do prontuário, financeiro, estoque e gestão, com ou sem a conta pública."""

    def make_app(self, **config):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.remove, path)
        self.now = datetime(2030, 1, 7, 9, 0)
        return create_app({"TESTING": True, "DATABASE": path, "SEED_DEMO_DATA": True,
                           "SECRET_KEY": "chave-de-teste-com-pelo-menos-32-bytes",
                           "PASSWORD_HASH_ITERATIONS": 1_000, "CLOCK": lambda: self.now,
                           **config})

    def login(self, client, email, password):
        token = client.post("/auth/login", json={"email": email, "password": password}
                            ).json["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_examples_fill_finance_stock_and_record(self):
        client = self.make_app(STAFF_ACCOUNTS=[]).test_client()
        headers = self.login(client, "admin@agendamed.dev", "admin12345")
        flow = client.get("/finance/cashflow?start=2029-12-01&end=2030-01-31",
                          headers=headers).json["totals"]
        self.assertGreater(flow["income_paid"], 0)
        self.assertGreater(flow["expense_paid"], 0)
        report = client.get("/reports/overview?start=2029-12-01&end=2030-01-31",
                            headers=headers).json
        self.assertGreater(report["appointments"]["completed"], 0)
        self.assertEqual([i["name"] for i in report["low_stock"]], ["Eletrodos descartáveis"])
        record = client.get("/patients/1/record", headers=headers).json
        self.assertEqual(record["summary"]["allergies"], "Dipirona")
        self.assertEqual(len(client.get("/patients/1/prescriptions", headers=headers
                                        ).json["items"]), 2)

    def test_with_staff_accounts_there_is_no_public_demo_login(self):
        staff = [("dono@clinicavida.com", "senha-forte-123", "Dono")]
        client = self.make_app(STAFF_ACCOUNTS=staff).test_client()
        refused = client.post("/auth/login", json={"email": "admin@agendamed.dev",
                                                   "password": "admin12345"})
        self.assertEqual(refused.status_code, 401)
        headers = self.login(client, "dono@clinicavida.com", "senha-forte-123")
        self.assertGreater(client.get("/doctors", headers=headers).json["total"], 0)
