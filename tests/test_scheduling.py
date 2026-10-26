"""Testes unitários das regras de agenda (sem banco de dados e sem HTTP)."""

import unittest
from datetime import date, datetime, time

from agendamed.errors import BusinessRuleError
from agendamed.models import Doctor
from agendamed.services.scheduling import free_slots, overlaps, validate_booking

DOCTOR = Doctor(
    id=1,
    name="Dra. Helena",
    specialty="Cardiologia",
    crm="123456/SP",
    slot_minutes=30,
    work_start=time(8, 0),
    work_end=time(12, 0),
)
NOW = datetime(2030, 1, 7, 9, 0)  # segunda-feira
TUESDAY = date(2030, 1, 8)


class OverlapTest(unittest.TestCase):
    def test_back_to_back_intervals_do_not_overlap(self):
        a = (datetime(2030, 1, 8, 9, 0), datetime(2030, 1, 8, 9, 30))
        b = (datetime(2030, 1, 8, 9, 30), datetime(2030, 1, 8, 10, 0))
        self.assertFalse(overlaps(*a, *b))

    def test_partial_overlap(self):
        a = (datetime(2030, 1, 8, 9, 0), datetime(2030, 1, 8, 10, 0))
        b = (datetime(2030, 1, 8, 9, 30), datetime(2030, 1, 8, 10, 30))
        self.assertTrue(overlaps(*a, *b))


class ValidateBookingTest(unittest.TestCase):
    def test_returns_end_time_for_valid_slot(self):
        end = validate_booking(DOCTOR, datetime(2030, 1, 8, 10, 30), NOW)
        self.assertEqual(end, datetime(2030, 1, 8, 11, 0))

    def test_rejects_invalid_slots(self):
        cases = {
            "no passado": datetime(2030, 1, 7, 8, 30),
            "exatamente agora": NOW,
            "sábado": datetime(2030, 1, 12, 10, 0),
            "antes do expediente": datetime(2030, 1, 8, 7, 30),
            "termina depois do expediente": datetime(2030, 1, 8, 11, 45),
            "fora da grade": datetime(2030, 1, 8, 10, 10),
            "com segundos": datetime(2030, 1, 8, 10, 0, 15),
        }
        for reason, start in cases.items():
            with self.subTest(reason), self.assertRaises(BusinessRuleError):
                validate_booking(DOCTOR, start, NOW)


class FreeSlotsTest(unittest.TestCase):
    def test_full_day_without_appointments(self):
        slots = free_slots(DOCTOR, TUESDAY, busy=[], now=NOW)
        self.assertEqual(len(slots), 8)  # 08:00 às 12:00, de 30 em 30 min
        self.assertEqual(slots[0], datetime(2030, 1, 8, 8, 0))
        self.assertEqual(slots[-1], datetime(2030, 1, 8, 11, 30))

    def test_excludes_busy_and_past_slots(self):
        busy = [(datetime(2030, 1, 7, 10, 0), datetime(2030, 1, 7, 10, 30))]
        slots = free_slots(DOCTOR, NOW.date(), busy=busy, now=NOW)
        self.assertEqual(
            [slot.time() for slot in slots],
            [time(9, 30), time(10, 30), time(11, 0), time(11, 30)],
        )

    def test_weekend_has_no_slots(self):
        self.assertEqual(free_slots(DOCTOR, date(2030, 1, 13), busy=[], now=NOW), [])
