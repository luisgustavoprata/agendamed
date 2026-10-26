import os
import tempfile
import unittest

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
