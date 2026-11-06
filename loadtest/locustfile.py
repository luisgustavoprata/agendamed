"""Teste de carga do AgendaMed com Locust.

Cada usuário virtual é uma pessoa da clínica: entra uma vez e depois fica consultando a
agenda, buscando pacientes e vendo horários livres, com pausas de 3 a 10 segundos entre
uma ação e outra (o ritmo de alguém atendendo telefone e balcão).

Uso (servidor local já rodando com SEED_DEMO_DATA=true):

    locust -f loadtest/locustfile.py --host http://127.0.0.1:8000 \
        --headless -u 1000 -r 50 -t 3m --csv loadtest/resultado

Contra o site publicado, use poucos usuários (ex.: -u 30 -r 2 -t 2m).
"""

import os
import random
from datetime import date, timedelta

from locust import HttpUser, between, task

EMAIL = os.environ.get("LOADTEST_EMAIL", "admin@agendamed.dev")
PASSWORD = os.environ.get("LOADTEST_PASSWORD", "admin12345")
SEARCHES = ["ana", "bruno", "carla", "silva", "529", "mar"]


def next_working_days(count: int) -> list[str]:
    """Os próximos `count` dias úteis a partir de hoje, como "AAAA-MM-DD"."""
    days, day = [], date.today()
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day.isoformat())
        day += timedelta(days=1)
    return days


class Receptionist(HttpUser):
    """Uma pessoa virtual da recepção: entra uma vez e depois repete as ações abaixo, com pausas
    de 3 a 10 segundos. O número em @task é o peso: day_agenda (5) acontece cinco vezes mais
    que page_load (1).
    """

    wait_time = between(3, 10)
    # Depois de 30 s sem resposta, a pessoa desiste (conta como falha).
    network_timeout = 30.0
    connection_timeout = 10.0

    def on_start(self):
        """Ao começar: faz login, guarda o token e anota os médicos e os próximos dias úteis."""
        response = self.client.post(
            "/auth/login", json={"email": EMAIL, "password": PASSWORD}, name="POST /auth/login"
        )
        token = response.json().get("access_token") if response.ok else None
        self.client.headers["Authorization"] = f"Bearer {token}"
        doctors = self.client.get("/doctors?limit=100", name="GET /doctors").json().get("items", [])
        self.doctor_ids = [d["id"] for d in doctors] or [1]
        self.days = next_working_days(10)

    @task(5)
    def day_agenda(self):
        """Abre a agenda de um médico num dia (horários livres e consultas)."""
        doctor, day = random.choice(self.doctor_ids), random.choice(self.days)
        self.client.get(
            f"/doctors/{doctor}/availability?date={day}", name="GET /doctors/:id/availability"
        )
        self.client.get(
            f"/appointments?doctor_id={doctor}&date={day}&limit=100", name="GET /appointments (dia)"
        )

    @task(3)
    def search_patient(self):
        """Busca pacientes por um pedaço do nome ou do CPF."""
        self.client.get(f"/patients?q={random.choice(SEARCHES)}&limit=8", name="GET /patients?q")

    @task(2)
    def list_appointments(self):
        """Lista a primeira página de consultas."""
        self.client.get("/appointments?limit=20", name="GET /appointments")

    @task(1)
    def page_load(self):
        """Recarrega a página: o HTML, um dos scripts (app.js) e os dados de quem está logado."""
        self.client.get("/", name="GET / (página)")
        self.client.get("/static/app.js", name="GET /static/*")
        self.client.get("/auth/me", name="GET /auth/me")
