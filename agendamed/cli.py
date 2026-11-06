"""Comandos de terminal da Clínica Vida, rodados com `flask --app agendamed <comando>`.

flask init-db   cria as tabelas do banco (e ajusta bancos de versões antigas)
flask seed      cria os dados de demonstração
"""

import click
from flask import Flask

from agendamed.db import get_db, init_db


@click.command("init-db")
def init_db_command() -> None:
    """Cria as tabelas do banco de dados."""
    init_db()
    click.echo("Banco de dados inicializado.")


@click.command("seed")
def seed_command() -> None:
    """Popula o banco com dados de demonstração."""
    from agendamed.seed import seed

    seed(get_db())
    click.echo("Dados de demonstração criados. Login: admin@agendamed.dev / admin12345")


def init_app(app: Flask) -> None:
    """Registra os comandos de terminal acima no Flask (`flask <comando>`)."""
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_command)
