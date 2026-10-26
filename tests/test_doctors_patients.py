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
