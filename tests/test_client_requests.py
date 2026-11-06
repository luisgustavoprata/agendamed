"""Pedidos de um médico que usava outro sistema (e os problemas que ele tinha lá).

1. O mesmo login aberto no celular e no computador ao mesmo tempo.
2. Receita e pedido de exame sem precisar "iniciar atendimento": a agenda não muda.
3. Agenda que nunca trava: consulta concluída pode ser reaberta e consulta passada, cancelada.
4. Relatório médico entre os documentos para imprimir.
"""

import sqlite3
from datetime import datetime

from agendamed import create_app
from tests.base import APITestCase


class ClientRequestsTest(APITestCase):
    def setUp(self):
        super().setUp()
        self.headers = self.auth_headers()
        self.doctor = self.create_doctor(self.headers)
        self.patient = self.create_patient(self.headers)

    def booked(self, start_at) -> dict:
        response = self.book(self.headers, self.doctor["id"], self.patient["id"], start_at)
        self.assertEqual(response.status_code, 201, response.json)
        return response.json

    def test_same_user_on_two_devices(self):
        phone = self.headers
        computer = {
            "Authorization": "Bearer "
            + self.client.post(
                "/auth/login", json={"email": "recepcao@clinica.com", "password": "senha-forte-123"}
            ).json["access_token"]
        }
        for headers in (phone, computer, phone):
            self.assertEqual(self.client.get("/appointments", headers=headers).status_code, 200)

    def test_document_before_the_appointment_keeps_the_agenda_free(self):
        appointment = self.booked("2030-01-10T10:00")
        response = self.client.post(
            f"/patients/{self.patient['id']}/prescriptions",
            headers=self.headers,
            json={
                "kind": "exames",
                "doctor_id": self.doctor["id"],
                "items": [{"name": "Hemograma completo"}],
            },
        )
        self.assertEqual(response.status_code, 201, response.json)
        url = f"/appointments/{appointment['id']}"
        self.assertEqual(self.client.get(url, headers=self.headers).json["status"], "scheduled")
        cancelled = self.client.post(f"{url}/cancel", headers=self.headers)
        self.assertEqual(cancelled.json["status"], "cancelled")

    def test_completed_by_mistake_can_be_reopened(self):
        appointment = self.booked("2030-01-07T10:00")
        url = f"/appointments/{appointment['id']}"
        self.now = datetime(2030, 1, 7, 10, 5)
        self.client.post(f"{url}/complete", headers=self.headers)
        reopened = self.client.post(f"{url}/reopen", headers=self.headers)
        self.assertEqual(reopened.json["status"], "scheduled")
        # Já passou do horário, mas ainda dá para desmarcar (ex.: o paciente faltou).
        cancelled = self.client.post(f"{url}/cancel", headers=self.headers)
        self.assertEqual(cancelled.json["status"], "cancelled")

    def test_only_completed_can_be_reopened(self):
        appointment = self.booked("2030-01-08T10:00")
        response = self.client.post(
            f"/appointments/{appointment['id']}/reopen", headers=self.headers
        )
        self.assertEqual(response.status_code, 409)

    def test_medical_report(self):
        response = self.client.post(
            f"/patients/{self.patient['id']}/prescriptions",
            headers=self.headers,
            json={
                "kind": "relatorio",
                "doctor_id": self.doctor["id"],
                "text": "Paciente em acompanhamento desde 2029.",
            },
        )
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(response.json["kind_label"], "Relatório médico")


class CancelledChargeTest(ClientRequestsTest):
    def test_cancelled_appointment_leaves_the_receivables(self):
        procedure = self.client.post(
            "/procedures", headers=self.headers, json={"name": "Consulta", "price_cents": 30000}
        ).json
        appointment = self.booked("2030-01-10T10:00")
        charge = self.client.post(
            f"/appointments/{appointment['id']}/charge",
            headers=self.headers,
            json={"procedure_id": procedure["id"]},
        )
        self.assertEqual(charge.status_code, 201, charge.json)
        self.client.post(f"/appointments/{appointment['id']}/cancel", headers=self.headers)
        totals = self.client.get(
            "/finance/cashflow?start=2030-01-01&end=2030-01-31", headers=self.headers
        ).json["totals"]
        self.assertEqual(totals["income_open"], 0)


class OldDatabaseTest(APITestCase):
    def test_old_prescriptions_table_accepts_reports_after_upgrade(self):
        db_path = self.app.config["DATABASE"]
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            DROP TABLE prescriptions;
            CREATE TABLE prescriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, clinic_id INTEGER NOT NULL DEFAULT 1,
                patient_id INTEGER NOT NULL, doctor_id INTEGER NOT NULL,
                kind TEXT NOT NULL
                     CHECK (kind IN ('simples', 'controle_especial', 'atestado', 'exames')),
                items TEXT NOT NULL DEFAULT '[]', text TEXT, created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')));
            INSERT INTO prescriptions (patient_id, doctor_id, kind, created_by)
            VALUES (1, 1, 'simples', 1);
        """)
        conn.close()
        create_app({**self.app.config, "CLOCK": lambda: self.now})  # roda o ajuste
        conn = sqlite3.connect(db_path)
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'prescriptions'").fetchone()[
            0
        ]
        self.assertIn("relatorio", sql)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM prescriptions").fetchone()[0], 1)
        conn.close()
