"""Garante que requisições simultâneas não agendam o mesmo horário duas vezes."""

import threading
import time
from collections import Counter
from unittest import mock

from agendamed.repositories import AppointmentRepository
from tests.base import APITestCase

PARALLEL_REQUESTS = 10

_original_find_overlapping = AppointmentRepository.find_overlapping


def _slow_find_overlapping(self, *args, **kwargs):
    """Atrasa a checagem de conflito para alargar a janela da condição de corrida.

    Sem a transação `BEGIN IMMEDIATE`, várias threads passariam pela checagem antes
    de qualquer uma inserir, e o teste falharia com mais de um agendamento.
    """
    result = _original_find_overlapping(self, *args, **kwargs)
    time.sleep(0.02)
    return result


class ConcurrentBookingTest(APITestCase):
    @mock.patch.object(AppointmentRepository, "find_overlapping", _slow_find_overlapping)
    def test_only_one_of_many_simultaneous_bookings_succeeds(self):
        headers = self.auth_headers()
        doctor = self.create_doctor(headers)
        patients = [
            self.create_patient(headers, name=f"Paciente {i}", cpf=cpf, email=f"p{i}@ex.com")
            for i, cpf in enumerate(_valid_cpfs(PARALLEL_REQUESTS))
        ]

        barrier = threading.Barrier(PARALLEL_REQUESTS)
        statuses: list[int] = []
        lock = threading.Lock()

        def book(patient_id: int) -> None:
            client = self.app.test_client()
            barrier.wait()  # todas as threads disparam ao mesmo tempo
            response = client.post(
                "/appointments",
                json={
                    "doctor_id": doctor["id"],
                    "patient_id": patient_id,
                    "start_at": "2030-01-08T10:00",
                },
                headers=headers,
            )
            with lock:
                statuses.append(response.status_code)

        threads = [threading.Thread(target=book, args=(p["id"],)) for p in patients]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(Counter(statuses), {201: 1, 409: PARALLEL_REQUESTS - 1})


def _valid_cpfs(quantity: int) -> list[str]:
    """Gera CPFs válidos e distintos a partir de uma base numérica."""
    cpfs = []
    for base in range(100_000_001, 100_000_001 + quantity):
        digits = [int(d) for d in str(base)]
        for position in (9, 10):
            total = sum(d * w for d, w in zip(digits, range(position + 1, 1, -1), strict=False))
            digits.append((total * 10) % 11 % 10)
        cpfs.append("".join(map(str, digits)))
    return cpfs
