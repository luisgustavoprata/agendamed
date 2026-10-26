"""Conexão com o SQLite, controle de transações e comandos de linha de comando."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import click
from flask import Flask, current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_db() -> sqlite3.Connection:
    """Retorna a conexão da requisição atual, abrindo-a na primeira chamada."""
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"])
        conn.row_factory = sqlite3.Row
        # Modo autocommit: as transações são abertas explicitamente em `transaction()`.
        conn.isolation_level = None
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection, *, immediate: bool = False) -> Iterator[None]:
    """Executa um bloco dentro de uma transação, com rollback em caso de erro.

    `immediate=True` reserva o banco para escrita já no início da transação. Isso
    impede que duas requisições simultâneas passem pela checagem de conflito e
    acabem agendando o mesmo horário.
    """
    conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def init_db() -> None:
    get_db().executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


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
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_command)
