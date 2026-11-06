"""Segurança: tentativas de login, limites, cabeçalhos e cadastro aberto ou fechado."""

from datetime import timedelta

from tests.base import APITestCase


class LoginRateLimitTest(APITestCase):
    """Bloqueio depois de muitas senhas erradas (por e-mail e por IP)."""

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

    def test_limit_per_ip_across_many_emails(self):
        self.app.extensions["login_ip_limiter"].max_attempts = 3
        for i in range(3):
            response = self.client.post(
                "/auth/login", json={"email": f"teste{i}@clinica.com", "password": "qualquer-1"}
            )
            self.assertEqual(response.status_code, 401)
        blocked = self.client.post(
            "/auth/login", json={"email": "outra@clinica.com", "password": "qualquer-1"}
        )
        self.assertEqual(blocked.status_code, 429)


class SignupTest(APITestCase):
    """O cadastro de contas pode ser fechado (ALLOW_SIGNUP)."""

    def test_signup_can_be_closed(self):
        self.app.config["ALLOW_SIGNUP"] = False
        response = self.client.post(
            "/auth/register",
            json={
                "email": "nova@clinica.com",
                "full_name": "Pessoa Nova",
                "password": "senha-forte-123",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertIs(self.client.get("/health").json["signup"], False)


class RequestLimitsTest(APITestCase):
    """Corpo grande demais é recusado e respostas da API não ficam em cache."""

    def test_rejects_oversized_body(self):
        response = self.client.post(
            "/auth/login", data="x" * (70 * 1024), content_type="application/json"
        )
        self.assertEqual(response.status_code, 413)

    def test_api_responses_are_not_cached(self):
        response = self.client.get("/doctors")
        self.assertEqual(response.headers["Cache-Control"], "no-store")


class SecurityHeadersTest(APITestCase):
    """Os cabeçalhos de segurança aparecem em todas as respostas."""

    def test_security_headers_on_every_response(self):
        for path in ("/", "/health", "/doctors"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(response.headers["X-Frame-Options"], "DENY")
                self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
                response.close()


class MalformedInputTest(APITestCase):
    """Números gigantes recebem 400/404/422, nunca erro 500."""

    def setUp(self):
        super().setUp()
        self.headers = self.auth_headers()
        self.doctor = self.create_doctor(self.headers)
        self.patient = self.create_patient(self.headers)

    def test_huge_ids_in_the_address_are_not_found(self):
        huge = "99999999999999999999"
        for path in (
            f"/doctors/{huge}",
            f"/patients/{huge}",
            f"/appointments/{huge}",
            f"/patients/{huge}/record",
            f"/prescriptions/{huge}",
        ):
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.headers)
                self.assertEqual(response.status_code, 404)

    def test_huge_numbers_in_the_query_string_are_rejected(self):
        huge = "99999999999999999999"
        for path in (
            f"/patients?offset={huge}",
            f"/appointments?patient_id={huge}",
            f"/finance/transactions?account_id={huge}",
        ):
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.headers)
                self.assertEqual(response.status_code, 400)

    def test_huge_ids_in_the_body_are_rejected(self):
        response = self.book(self.headers, 2**63, self.patient["id"], "2030-01-08T10:00")
        self.assertEqual(response.status_code, 422)
        response = self.book(self.headers, self.doctor["id"], 2**63, "2030-01-08T10:00")
        self.assertEqual(response.status_code, 422)


class AbsurdDateTest(APITestCase):
    """Datas fora do intervalo aceito (de 1900 a 2100) recebem 400/422, nunca erro 500."""

    def setUp(self):
        super().setUp()
        self.headers = self.auth_headers()
        self.doctor = self.create_doctor(self.headers)
        self.patient = self.create_patient(self.headers)

    def test_absurd_dates_in_the_query_string_are_rejected(self):
        for path in (
            f"/doctors/{self.doctor['id']}/availability?date=9999-12-31",
            "/appointments?date=9999-12-31",
            "/appointments?date=1899-12-31",
            "/finance/transactions?start=9999-12-01",
            "/finance/cashflow?start=9999-12-01",
            "/finance/payouts?start=9999-12-01",
            "/finance/tiss?health_plan_id=1&start=9999-12-01",
            "/reports/overview?start=9999-12-01",
        ):
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.headers)
                self.assertEqual(response.status_code, 400)
        response = self.client.get("/appointments?date=9999-12-31", headers=self.headers)
        self.assertEqual(
            response.json["detail"], "O parâmetro 'date' deve ser uma data entre 1900 e 2100."
        )

    def test_absurd_appointment_times_are_rejected(self):
        for start_at in ("9999-12-31T23:30", "2101-01-03T10:00"):
            with self.subTest(start_at=start_at):
                response = self.book(self.headers, self.doctor["id"], self.patient["id"], start_at)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(
                    response.json["errors"][0]["message"], "Informe uma data entre 1900 e 2100."
                )

    def test_dates_at_the_edges_of_the_range_still_work(self):
        for day in ("1900-01-01", "2100-12-31"):
            with self.subTest(day=day):
                response = self.client.get(f"/appointments?date={day}", headers=self.headers)
                self.assertEqual(response.status_code, 200)
        response = self.book(
            self.headers, self.doctor["id"], self.patient["id"], "2100-12-31T10:00"
        )
        self.assertEqual(response.status_code, 201)


class SecretKeyTest(APITestCase):
    """O sistema não sobe em produção com a SECRET_KEY de exemplo ou curta."""

    def test_refuses_to_start_with_default_or_short_key(self):
        from agendamed import EXAMPLE_SECRET_KEY, create_app
        from agendamed.config import DEFAULT_SECRET_KEY

        for key in (DEFAULT_SECRET_KEY, EXAMPLE_SECRET_KEY, "curta"):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                create_app({"SECRET_KEY": key, "DATABASE": ":memory:"})

    def test_a_long_key_starts_normally(self):
        from agendamed import create_app

        app = create_app({"SECRET_KEY": "k" * 48, "DATABASE": ":memory:"})
        self.assertFalse(app.config.get("TESTING"))
