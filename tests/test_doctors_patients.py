from tests.base import APITestCase


class DoctorsTest(APITestCase):
    def setUp(self):
        super().setUp()
        self.headers = self.auth_headers()

    def test_create_and_get_doctor(self):
        doctor = self.create_doctor(self.headers, slot_minutes=20)
        self.assertEqual(doctor["work_start"], "08:00")
        response = self.client.get(f"/doctors/{doctor['id']}", headers=self.headers)
        self.assertEqual(response.json["slot_minutes"], 20)

    def test_duplicate_crm_returns_409(self):
        self.create_doctor(self.headers)
        response = self.client.post(
            "/doctors",
            json={"name": "Outro Médico", "specialty": "Clínica", "crm": "123456/SP"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 409)

    def test_rejects_inverted_working_hours(self):
        response = self.client.post(
            "/doctors",
            json={
                "name": "Dr. Teste",
                "specialty": "Clínica",
                "crm": "999999/RJ",
                "work_start": "18:00",
                "work_end": "08:00",
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 422)

    def test_list_filters_by_specialty_and_paginates(self):
        self.create_doctor(self.headers)
        self.create_doctor(self.headers, name="Dr. Rafael", specialty="Pediatria", crm="1111/GO")
        self.create_doctor(self.headers, name="Dr. Bruno", specialty="Pediatria", crm="2222/GO")

        response = self.client.get(
            "/doctors?specialty=pedia&limit=1", headers=self.headers
        )
        self.assertEqual(response.json["total"], 2)
        self.assertEqual(len(response.json["items"]), 1)
        self.assertEqual(response.json["items"][0]["name"], "Dr. Bruno")

    def test_unknown_doctor_returns_404(self):
        response = self.client.get("/doctors/999", headers=self.headers)
        self.assertEqual(response.status_code, 404)


class PatientsTest(APITestCase):
    def setUp(self):
        super().setUp()
        self.headers = self.auth_headers()

    def test_create_patient_normalizes_cpf(self):
        patient = self.create_patient(self.headers, cpf="52998224725")
        self.assertEqual(patient["cpf"], "529.982.247-25")

    def test_invalid_cpf_returns_422(self):
        response = self.client.post(
            "/patients",
            json={
                "name": "Fulano",
                "cpf": "123.456.789-00",
                "email": "f@exemplo.com",
                "birth_date": "1990-01-01",
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json["errors"][0]["message"], "CPF inválido.")

    def test_duplicate_cpf_returns_409(self):
        self.create_patient(self.headers)
        response = self.client.post(
            "/patients",
            json={
                "name": "Outra Pessoa",
                "cpf": "52998224725",
                "email": "outra@exemplo.com",
                "birth_date": "1990-01-01",
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 409)

    def test_search_by_name_or_masked_cpf(self):
        self.create_patient(self.headers)
        self.create_patient(
            self.headers, name="Bruno Lima", cpf="526.018.159-06", email="b@exemplo.com"
        )
        by_name = self.client.get("/patients?q=bruno", headers=self.headers).json
        by_cpf = self.client.get("/patients?q=529.982", headers=self.headers).json
        self.assertEqual([p["name"] for p in by_name["items"]], ["Bruno Lima"])
        self.assertEqual([p["name"] for p in by_cpf["items"]], ["Ana Souza"])

    def test_rejects_non_json_body(self):
        response = self.client.post(
            "/patients", data="não é json", headers=self.headers, content_type="text/plain"
        )
        self.assertEqual(response.status_code, 400)


class PatientUpdateTests(APITestCase):
    def setUp(self) -> None:
        super().setUp()
        self.headers = self.auth_headers()
        self.patient = self.create_patient(self.headers, phone="(11) 98888-7777")

    def patch(self, patient_id, payload):
        return self.client.patch(f"/patients/{patient_id}", json=payload, headers=self.headers)

    def test_updates_only_the_fields_sent(self):
        response = self.patch(
            self.patient["id"], {"name": "Ana Souza Lima", "email": "ANA@novo.com"}
        )
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["name"], "Ana Souza Lima")
        self.assertEqual(response.json["email"], "ana@novo.com")
        self.assertEqual(response.json["cpf"], "529.982.247-25")
        self.assertEqual(response.json["phone"], "(11) 98888-7777")
        again = self.client.get(f"/patients/{self.patient['id']}", headers=self.headers).json
        self.assertEqual(again["name"], "Ana Souza Lima")

    def test_phone_can_be_cleared(self):
        response = self.patch(self.patient["id"], {"phone": None})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertIsNone(response.json["phone"])

    def test_required_field_cannot_be_emptied(self):
        response = self.patch(self.patient["id"], {"name": None})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json["errors"][0]["field"], "name")

    def test_invalid_cpf_returns_422(self):
        response = self.patch(self.patient["id"], {"cpf": "111.111.111-11"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json["errors"][0]["message"], "CPF inválido.")

    def test_cpf_of_another_patient_returns_409(self):
        other = self.create_patient(
            self.headers, name="Bruno Lima", cpf="526.018.159-06", email="b@exemplo.com"
        )
        response = self.patch(other["id"], {"cpf": "52998224725"})
        self.assertEqual(response.status_code, 409)

    def test_keeping_the_same_cpf_is_allowed(self):
        response = self.patch(self.patient["id"], {"cpf": "52998224725", "name": "Ana Souza"})
        self.assertEqual(response.status_code, 200, response.json)

    def test_empty_body_returns_422(self):
        self.assertEqual(self.patch(self.patient["id"], {}).status_code, 422)

    def test_unknown_patient_returns_404(self):
        self.assertEqual(self.patch(9999, {"name": "Fulano de Tal"}).status_code, 404)

    def test_appointments_show_the_new_name(self):
        doctor = self.create_doctor(self.headers)
        booked = self.book(self.headers, doctor["id"], self.patient["id"], "2030-01-08T10:00:00")
        self.assertEqual(booked.status_code, 201, booked.json)
        self.patch(self.patient["id"], {"name": "Ana Souza Lima"})
        appointment = self.client.get(
            f"/appointments/{booked.json['id']}", headers=self.headers
        ).json
        self.assertEqual(appointment["patient"]["name"], "Ana Souza Lima")

    def test_requires_login(self):
        response = self.client.patch(f"/patients/{self.patient['id']}", json={"name": "Fulano"})
        self.assertEqual(response.status_code, 401)
