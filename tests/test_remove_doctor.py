import sqlite3
from datetime import timedelta

from agendamed.db import get_db, init_db
from tests.base import APITestCase


class RemoveDoctorTest(APITestCase):
    def setUp(self):
        super().setUp()
        self.headers = self.auth_headers()
        self.doctor = self.create_doctor(self.headers)
        self.patient = self.create_patient(self.headers)

    def remove(self, doctor_id=None):
        doctor_id = doctor_id or self.doctor["id"]
        return self.client.delete(f"/doctors/{doctor_id}", headers=self.headers)

    def test_removed_doctor_leaves_lists_and_cannot_be_booked(self):
        self.assertEqual(self.remove().status_code, 204)

        listing = self.client.get("/doctors", headers=self.headers).json
        self.assertEqual(listing["total"], 0)
        self.assertEqual(
            self.client.get(f"/doctors/{self.doctor['id']}", headers=self.headers).status_code, 404
        )
        booked = self.book(self.headers, self.doctor["id"], self.patient["id"], "2030-01-08T10:00")
        self.assertEqual(booked.status_code, 404)
        self.assertEqual(self.remove().status_code, 404)

    def test_refuses_while_there_are_future_appointments(self):
        self.book(self.headers, self.doctor["id"], self.patient["id"], "2030-01-08T10:00")
        self.book(self.headers, self.doctor["id"], self.patient["id"], "2030-01-08T10:30")

        response = self.remove()
        self.assertEqual(response.status_code, 409)
        self.assertIn("2 consultas marcadas", response.json["detail"])
        self.assertEqual(self.client.get("/doctors", headers=self.headers).json["total"], 1)

    def test_cancelled_appointments_do_not_block(self):
        booked = self.book(self.headers, self.doctor["id"], self.patient["id"], "2030-01-08T10:00")
        self.client.post(f"/appointments/{booked.json['id']}/cancel", headers=self.headers)
        self.assertEqual(self.remove().status_code, 204)

    def test_history_is_kept(self):
        booked = self.book(self.headers, self.doctor["id"], self.patient["id"], "2030-01-07T10:00")
        self.now += timedelta(hours=2)  # a consulta já passou
        self.assertEqual(self.remove().status_code, 204)

        history = self.client.get("/appointments", headers=self.headers).json
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["items"][0]["doctor"]["name"], self.doctor["name"])
        detail = self.client.get(f"/appointments/{booked.json['id']}", headers=self.headers)
        self.assertEqual(detail.status_code, 200)

    def test_same_crm_brings_the_doctor_back(self):
        self.remove()
        again = self.create_doctor(self.headers, name="Dra. Helena Prado Lima")
        self.assertEqual(again["id"], self.doctor["id"])
        self.assertEqual(again["name"], "Dra. Helena Prado Lima")

    def test_requires_login(self):
        self.assertEqual(self.client.delete(f"/doctors/{self.doctor['id']}").status_code, 401)


class UpgradeOldDatabaseTest(APITestCase):
    def test_adds_active_column_to_existing_database(self):
        with self.app.app_context():
            conn = get_db()
            conn.executescript(
                "DROP TABLE appointments; DROP TABLE doctors;"
                "CREATE TABLE doctors (id INTEGER PRIMARY KEY, name TEXT, specialty TEXT,"
                " crm TEXT UNIQUE, slot_minutes INTEGER, work_start TEXT, work_end TEXT);"
                "INSERT INTO doctors VALUES (1, 'Dr. Antigo', 'Clínica', '1111/SP', 30,"
                " '08:00', '12:00');"
            )
            init_db()
            row = conn.execute("SELECT active FROM doctors WHERE id = 1").fetchone()
            self.assertIsInstance(row, sqlite3.Row)
            self.assertEqual(row["active"], 1)
