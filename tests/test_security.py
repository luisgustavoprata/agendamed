from datetime import timedelta

from tests.base import APITestCase


class LoginRateLimitTest(APITestCase):
    def setUp(self):
        super().setUp()
        self.register()

    def _login(self, password):
        return self.client.post(
            "/auth/login", json={"email": "recepcao@clinica.com", "password": password}
        )

    def test_blocks_after_five_wrong_passwords(self):
        for _ in range(5):
            self.assertEqual(self._login("errada-123").status_code, 401)

        blocked = self._login("senha-forte-123")  # nem a senha certa passa durante o bloqueio
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.headers["Retry-After"], "300")

    def test_block_expires_after_the_window(self):
        for _ in range(5):
            self._login("errada-123")
        self.now += timedelta(minutes=5, seconds=1)
        self.assertEqual(self._login("senha-forte-123").status_code, 200)

    def test_successful_login_resets_the_counter(self):
        for _ in range(4):
            self._login("errada-123")
        self.assertEqual(self._login("senha-forte-123").status_code, 200)
        for _ in range(4):
            self.assertEqual(self._login("errada-123").status_code, 401)

    def test_limit_is_per_email(self):
        for _ in range(5):
            self._login("errada-123")
        other = self.client.post(
            "/auth/login", json={"email": "outra@clinica.com", "password": "qualquer-1"}
        )
        self.assertEqual(other.status_code, 401)


class SecurityHeadersTest(APITestCase):
    def test_security_headers_on_every_response(self):
        for path in ("/", "/health", "/doctors"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(response.headers["X-Frame-Options"], "DENY")
                self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
                response.close()
