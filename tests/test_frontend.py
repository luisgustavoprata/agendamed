from tests.base import APITestCase


class FrontendTest(APITestCase):
    def test_index_serves_web_app(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        self.assertIn(b"/static/app.js", response.data)
        response.close()

    def test_static_assets_are_served(self):
        for path in ("/static/app.js", "/static/styles.css", "/static/icon.svg"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                response.close()

    def test_validation_messages_are_translated(self):
        response = self.client.post("/auth/register", json={"email": "a@b.com"})
        messages = {error["field"]: error["message"] for error in response.json["errors"]}
        self.assertEqual(messages["password"], "Campo obrigatório.")
