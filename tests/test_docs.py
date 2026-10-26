import re

from tests.base import APITestCase

UNDOCUMENTED = {"/", "/docs", "/openapi.json", "/static/<path:filename>"}


def to_openapi_path(rule: str) -> str:
    """Converte `/doctors/<int:doctor_id>` em `/doctors/{doctor_id}`."""
    return re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", rule)


class OpenApiTest(APITestCase):
    def setUp(self):
        super().setUp()
        self.spec = self.client.get("/openapi.json").json

    def test_every_route_is_documented(self):
        missing = []
        for rule in self.app.url_map.iter_rules():
            if rule.rule in UNDOCUMENTED:
                continue
            path = to_openapi_path(rule.rule)
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                if method.lower() not in self.spec["paths"].get(path, {}):
                    missing.append(f"{method} {path}")
        self.assertEqual(missing, [], "Rotas sem documentação na especificação OpenAPI")

    def test_request_bodies_come_from_pydantic(self):
        doctor = self.spec["components"]["schemas"]["DoctorCreate"]
        self.assertEqual(doctor["properties"]["crm"]["pattern"], r"^\d{4,7}/[A-Z]{2}$")
        self.assertIn("name", doctor["required"])

    def test_all_references_resolve(self):
        schemas = self.spec["components"]["schemas"]
        refs = re.findall(r'"#/components/schemas/(\w+)"', str(self.spec).replace("'", '"'))
        self.assertTrue(refs)
        self.assertEqual({ref for ref in refs if ref not in schemas}, set())

    def test_swagger_ui_page(self):
        response = self.client.get("/docs")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"swagger-ui", response.data)
