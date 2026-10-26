from datetime import datetime

from tests.base import APITestCase


class AppointmentsTest(APITestCase):
    def setUp(self):
        super().setUp()
        self.headers = self.auth_headers()
        self.doctor = self.create_doctor(self.headers)
        self.patient = self.create_patient(self.headers)

    def _book(self, start_at, doctor=None, patient=None):
        doctor_id = (doctor or self.doctor)["id"]
        patient_id = (patient or self.patient)["id"]
        return self.book(self.headers, doctor_id, patient_id, start_at)

    def test_book_appointment(self):
        response = self._book("2030-01-08T10:00")
        self.assertEqual(response.status_code, 201, response.json)
        body = response.json
        self.assertEqual(body["end_at"], "2030-01-08T10:30")
        self.assertEqual(body["status"], "scheduled")
        self.assertEqual(body["doctor"]["name"], "Dra. Helena Prado")
        self.assertEqual(body["patient"]["name"], "Ana Souza")
        self.assertEqual(response.headers["Location"], f"/appointments/{body['id']}")

    def test_business_rules_return_422(self):
        cases = {
            "passado": "2030-01-07T08:30",
            "fim de semana": "2030-01-12T10:00",
            "fora do expediente": "2030-01-08T19:00",
            "fora da grade": "2030-01-08T10:15",
        }
        for reason, start_at in cases.items():
            with self.subTest(reason):
                self.assertEqual(self._book(start_at).status_code, 422)

    def test_timezone_aware_datetime_is_rejected(self):
        self.assertEqual(self._book("2030-01-08T10:00:00-03:00").status_code, 422)

    def test_unknown_doctor_or_patient_returns_404(self):
        self.assertEqual(self._book("2030-01-08T10:00", doctor={"id": 999}).status_code, 404)
        self.assertEqual(self._book("2030-01-08T10:00", patient={"id": 999}).status_code, 404)

    def test_doctor_cannot_be_double_booked(self):
        other = self.create_patient(
            self.headers, name="Bruno Lima", cpf="526.018.159-06", email="b@exemplo.com"
        )
        self.assertEqual(self._book("2030-01-08T10:00").status_code, 201)
        response = self._book("2030-01-08T10:00", patient=other)
        self.assertEqual(response.status_code, 409)
        self.assertIn("médico", response.json["detail"])

    def test_patient_cannot_be_in_two_places_at_once(self):
        other_doctor = self.create_doctor(
            self.headers, name="Dr. Rafael", specialty="Pediatria", crm="654321/GO",
            slot_minutes=60,
        )
        self.assertEqual(self._book("2030-01-08T10:00").status_code, 201)
        # 09:00–10:00 não conflita (termina quando a outra começa)...
        self.assertEqual(self._book("2030-01-08T09:00", doctor=other_doctor).status_code, 201)
        # ...mas 10:00–11:00 com outro médico conflita com a consulta das 10:00.
        response = self._book("2030-01-08T10:00", doctor=other_doctor)
        self.assertEqual(response.status_code, 409)
        self.assertIn("paciente", response.json["detail"])

    def test_cancel_frees_the_slot(self):
        appointment = self._book("2030-01-08T10:00").json
        response = self.client.post(
            f"/appointments/{appointment['id']}/cancel", headers=self.headers
        )
        self.assertEqual(response.json["status"], "cancelled")
        self.assertEqual(self._book("2030-01-08T10:00").status_code, 201)

    def test_cannot_cancel_twice(self):
        appointment = self._book("2030-01-08T10:00").json
        url = f"/appointments/{appointment['id']}/cancel"
        self.client.post(url, headers=self.headers)
        self.assertEqual(self.client.post(url, headers=self.headers).status_code, 409)

    def test_complete_only_after_start(self):
        appointment = self._book("2030-01-08T10:00").json
        url = f"/appointments/{appointment['id']}/complete"
        self.assertEqual(self.client.post(url, headers=self.headers).status_code, 409)

        self.now = datetime(2030, 1, 8, 10, 20)  # o tempo passa...
        response = self.client.post(url, headers=self.headers)
        self.assertEqual(response.json["status"], "completed")

        cancel = self.client.post(
            f"/appointments/{appointment['id']}/cancel", headers=self.headers
        )
        self.assertEqual(cancel.status_code, 409)

    def test_availability_hides_booked_and_past_slots(self):
        self._book("2030-01-07T10:00")
        response = self.client.get(
            f"/doctors/{self.doctor['id']}/availability?date=2030-01-07", headers=self.headers
        )
        slots = response.json["available_slots"]
        self.assertEqual(slots[0], "2030-01-07T09:30")  # 09:00 é "agora"
        self.assertNotIn("2030-01-07T10:00", slots)
        self.assertEqual(slots[-1], "2030-01-07T17:30")

    def test_availability_requires_valid_date(self):
        url = f"/doctors/{self.doctor['id']}/availability"
        self.assertEqual(self.client.get(url, headers=self.headers).status_code, 400)
        response = self.client.get(f"{url}?date=07/01/2030", headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_list_filters(self):
        self._book("2030-01-08T10:00")
        cancelled = self._book("2030-01-08T11:00").json
        self._book("2030-01-09T10:00")
        self.client.post(f"/appointments/{cancelled['id']}/cancel", headers=self.headers)

        def ids(query):
            response = self.client.get(f"/appointments?{query}", headers=self.headers)
            return [item["start_at"] for item in response.json["items"]]

        self.assertEqual(ids("date=2030-01-08"), ["2030-01-08T10:00", "2030-01-08T11:00"])
        self.assertEqual(ids("status=cancelled"), ["2030-01-08T11:00"])
        self.assertEqual(ids("date=2030-01-08&status=scheduled"), ["2030-01-08T10:00"])
        bad = self.client.get("/appointments?status=xyz", headers=self.headers)
        self.assertEqual(bad.status_code, 400)
