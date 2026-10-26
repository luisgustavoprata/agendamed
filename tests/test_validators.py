import unittest

from agendamed.validators import format_cpf, is_valid_cpf


class CpfValidatorTest(unittest.TestCase):
    def test_accepts_valid_cpf_with_or_without_mask(self):
        for cpf in ("529.982.247-25", "52998224725", "083.016.613-05"):
            with self.subTest(cpf=cpf):
                self.assertTrue(is_valid_cpf(cpf))

    def test_rejects_invalid_cpf(self):
        cases = {
            "dígito verificador errado": "529.982.247-26",
            "todos os dígitos iguais": "111.111.111-11",
            "curto demais": "123.456.789",
            "vazio": "",
        }
        for reason, cpf in cases.items():
            with self.subTest(reason):
                self.assertFalse(is_valid_cpf(cpf))

    def test_format_cpf(self):
        self.assertEqual(format_cpf("52998224725"), "529.982.247-25")
