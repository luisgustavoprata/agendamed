"""Contas de acesso da equipe, definidas por variáveis de ambiente.

Cada perfil usa três variáveis: <PERFIL>_EMAIL, <PERFIL>_PASSWORD e <PERFIL>_NAME
(ex.: ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME). Perfis sem e-mail ou senha são ignorados.

As contas são garantidas a cada inicialização: se não existem, são criadas; se já existem,
nome e senha são atualizados com o valor das variáveis. Assim, para trocar a senha de alguém,
basta mudar a variável no painel do Render e reiniciar o serviço.
"""

import os
import sqlite3

from flask import current_app

from agendamed.errors import ConflictError
from agendamed.repositories import UserRepository
from agendamed.security import hash_password, verify_password

# (prefixo das variáveis, nome padrão)
PROFILES = [
    ("ADMIN", "Administrador"),
    ("DOCTOR", "Médico"),
    ("SECRETARY", "Secretária"),
]


def configured_accounts(environ=None) -> list[tuple[str, str, str]]:
    """Lista (e-mail, senha, nome) dos perfis com e-mail e senha definidos."""
    environ = os.environ if environ is None else environ
    accounts = []
    for prefix, default_name in PROFILES:
        email = environ.get(f"{prefix}_EMAIL", "").strip().lower()
        password = environ.get(f"{prefix}_PASSWORD", "")
        if not email or not password:
            continue
        if len(password) < 8:
            raise ValueError(f"{prefix}_PASSWORD precisa ter ao menos 8 caracteres.")
        name = environ.get(f"{prefix}_NAME", "").strip() or default_name
        accounts.append((email, password, name))
    return accounts


def ensure_accounts(conn: sqlite3.Connection, accounts) -> None:
    """Cria ou atualiza as contas da equipe."""
    users = UserRepository(conn)
    iterations = current_app.config["PASSWORD_HASH_ITERATIONS"]
    for email, password, name in accounts:
        user = users.get_by_email(email)
        if user is None:
            try:
                users.create(email, name, hash_password(password, iterations))
            except ConflictError:
                pass  # outro processo do servidor criou a mesma conta ao mesmo tempo
            continue
        if user.full_name != name or not verify_password(password, user.password_hash):
            conn.execute(
                "UPDATE users SET full_name = ?, password_hash = ? WHERE id = ?",
                (name, hash_password(password, iterations), user.id),
            )
