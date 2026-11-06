import os
import tempfile
import unittest

from agendamed import create_app
from agendamed.accounts import configured_accounts

ENV = {
    "ADMIN_EMAIL": " Dono@Clinica.com ",
    "ADMIN_PASSWORD": "senha-do-adm",
    "DOCTOR_EMAIL": "medico@clinica.com",
    "DOCTOR_PASSWORD": "senha-do-medico",
    "DOCTOR_NAME": "Dr. Fulano",
    "SECRETARY_EMAIL": "secretaria@clinica.com",  # sem senha: ignorada
}


class AccountsTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.remove, self.db_path)

    def make_app(self, env):
        return create_app(
            {
                "TESTING": True,
                "DATABASE": self.db_path,
                "PASSWORD_HASH_ITERATIONS": 1_000,
                "STAFF_ACCOUNTS": configured_accounts(env),
            }
        )

    def login(self, app, email, password):
        return app.test_client().post("/auth/login", json={"email": email, "password": password})

    def test_reads_profiles_from_environment(self):
        self.assertEqual(
            configured_accounts(ENV),
            [
                ("dono@clinica.com", "senha-do-adm", "Administrador"),
                ("medico@clinica.com", "senha-do-medico", "Dr. Fulano"),
            ],
        )

    def test_short_password_is_rejected(self):
        with self.assertRaises(ValueError):
            configured_accounts({"ADMIN_EMAIL": "a@b.com", "ADMIN_PASSWORD": "curta"})

    def test_accounts_are_created_and_password_change_applies_on_restart(self):
        app = self.make_app(ENV)
        self.assertEqual(self.login(app, "dono@clinica.com", "senha-do-adm").status_code, 200)
        self.assertEqual(self.login(app, "medico@clinica.com", "senha-do-medico").status_code, 200)

        app = self.make_app({**ENV, "ADMIN_PASSWORD": "nova-senha-adm"})  # reinício
        self.assertEqual(self.login(app, "dono@clinica.com", "senha-do-adm").status_code, 401)
        self.assertEqual(self.login(app, "dono@clinica.com", "nova-senha-adm").status_code, 200)

    def test_demo_account_is_not_created_without_demo_data(self):
        app = self.make_app(ENV)
        self.assertEqual(self.login(app, "admin@agendamed.dev", "admin12345").status_code, 401)
