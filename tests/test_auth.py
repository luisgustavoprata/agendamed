from datetime import UTC, datetime, timedelta

import jwt

from tests.base import APITestCase


class AuthTest(APITestCase):
    def test_register_returns_user_without_password(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["email"], "recepcao@clinica.com")
        self.assertNotIn("password", response.json)
        self.assertNotIn("password_hash", response.json)

    def test_register_duplicate_email_returns_409(self):
        self.register()
        response = self.register()
        self.assertEqual(response.status_code, 409)

    def test_register_validates_payload(self):
        response = self.client.post(
            "/auth/register", json={"email": "invalido", "full_name": "A", "password": "123"}
        )
        self.assertEqual(response.status_code, 422)
        fields = {error["field"] for error in response.json["errors"]}
        self.assertEqual(fields, {"email", "full_name", "password"})

    def test_login_with_wrong_password_returns_401(self):
        self.register()
        response = self.client.post(
            "/auth/login", json={"email": "recepcao@clinica.com", "password": "errada-123"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["detail"], "E-mail ou senha incorretos.")

    def test_me_returns_logged_user(self):
        response = self.client.get("/auth/me", headers=self.auth_headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["full_name"], "Recepção Clínica")

    def test_protected_routes_require_token(self):
        for path in ("/doctors", "/patients", "/appointments", "/auth/me"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)

    def test_invalid_and_expired_tokens_are_rejected(self):
        self.register()
        expired = jwt.encode(
            {"sub": "1", "exp": datetime.now(UTC) - timedelta(minutes=1)},
            "chave-de-teste-com-pelo-menos-32-bytes",
            algorithm="HS256",
        )
        forged = jwt.encode(
            {"sub": "1"}, "outra-chave-tambem-com-mais-de-32-bytes", algorithm="HS256"
        )
        for token in (expired, forged, "lixo"):
            with self.subTest(token=token[:12]):
                response = self.client.get(
                    "/auth/me", headers={"Authorization": f"Bearer {token}"}
                )
                self.assertEqual(response.status_code, 401)
