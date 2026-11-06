"""Base para os testes de API: banco temporário isolado e relógio fixo."""

import os
import tempfile
import unittest
from datetime import datetime

from agendamed import create_app

# Segunda-feira, 7 de janeiro de 2030, 09:00 — o "agora" de todos os testes.
NOW = datetime(2030, 1, 7, 9, 0)


class APITestCase(unittest.TestCase):
    """Base dos testes que chamam a API como a interface faria (cliente HTTP do Flask).

    Cada teste tem um banco próprio e o relógio parado em NOW (troque `self.now` para mudar a hora
    "de agora").
    """

    def setUp(self) -> None:
        """Antes de cada teste: banco novo, relógio em NOW e uma aplicação nova."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.remove, db_path)

        self.now = NOW
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": db_path,
                "SECRET_KEY": "chave-de-teste-com-pelo-menos-32-bytes",
                "PASSWORD_HASH_ITERATIONS": 1_000,  # rápido nos testes
                "CLOCK": lambda: self.now,
            }
        )
        self.client = self.app.test_client()

    # --- helpers -----------------------------------------------------------

    def register(self, email="recepcao@clinica.com", password="senha-forte-123"):
        """Cria uma conta de acesso (POST /auth/register)."""
        return self.client.post(
            "/auth/register",
            json={"email": email, "full_name": "Recepção Clínica", "password": password},
        )

    def auth_headers(self) -> dict:
        """Cria a conta da recepção, faz login e devolve o cabeçalho Authorization."""
        self.register()
        response = self.client.post(
            "/auth/login", json={"email": "recepcao@clinica.com", "password": "senha-forte-123"}
        )
        return {"Authorization": f"Bearer {response.json['access_token']}"}

    def create_doctor(self, headers, **overrides) -> dict:
        """Cadastra um médico (por padrão, a Dra. Helena Prado) e devolve o JSON dele."""
        payload = {
            "name": "Dra. Helena Prado",
            "specialty": "Cardiologia",
            "crm": "123456/SP",
            **overrides,
        }
        response = self.client.post("/doctors", json=payload, headers=headers)
        self.assertEqual(response.status_code, 201, response.json)
        return response.json

    def create_patient(self, headers, **overrides) -> dict:
        """Cadastra um paciente (por padrão, Ana Souza) e devolve o JSON dele."""
        payload = {
            "name": "Ana Souza",
            "cpf": "529.982.247-25",
            "email": "ana@exemplo.com",
            "birth_date": "1994-03-12",
            **overrides,
        }
        response = self.client.post("/patients", json=payload, headers=headers)
        self.assertEqual(response.status_code, 201, response.json)
        return response.json

    def book(self, headers, doctor_id, patient_id, start_at, **extra):
        """Marca uma consulta (POST /appointments) e devolve a resposta."""
        return self.client.post(
            "/appointments",
            json={"doctor_id": doctor_id, "patient_id": patient_id, "start_at": start_at, **extra},
            headers=headers,
        )
