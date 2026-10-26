"""Validadores reutilizáveis."""

import re

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def is_valid_cpf(cpf: str) -> bool:
    """Valida um CPF pelos dois dígitos verificadores (aceita com ou sem máscara)."""
    digits = [int(char) for char in only_digits(cpf)]
    if len(digits) != 11 or len(set(digits)) == 1:
        return False

    for position in (9, 10):
        weights = range(position + 1, 1, -1)
        pairs = zip(digits[:position], weights, strict=True)
        total = sum(digit * weight for digit, weight in pairs)
        check_digit = (total * 10) % 11 % 10
        if digits[position] != check_digit:
            return False
    return True


def format_cpf(cpf: str) -> str:
    d = only_digits(cpf)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
