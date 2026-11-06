"""Conexão com o SQLite, controle de transações e comandos de linha de comando."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from flask import Flask, current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
GESTAO_SCHEMA_PATH = Path(__file__).with_name("schema_gestao.sql")


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
    conn = get_db()
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _upgrade(conn)


def _upgrade(conn) -> None:
    """Ajusta bancos criados por versões anteriores (CREATE TABLE IF NOT EXISTS não altera)."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(doctors)")}
    if "active" not in columns:
        conn.execute("ALTER TABLE doctors ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
    # Módulos de gestão: usam clinic_id (sempre 1 nesta versão de uma clínica só).
    for table in ("patients", "doctors", "appointments"):
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if "clinic_id" not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN clinic_id INTEGER NOT NULL DEFAULT 1")
    conn.executescript(GESTAO_SCHEMA_PATH.read_text(encoding="utf-8"))
    _allow_medical_report(conn)


def _allow_medical_report(conn) -> None:
    """Bancos antigos: a tabela de prescrições não aceitava o tipo "relatorio".

    O SQLite não altera um CHECK, então a tabela é recriada com os mesmos dados.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'prescriptions'"
    ).fetchone()
    if row is None or "relatorio" in row["sql"]:
        return
    new_sql = (
        row["sql"]
        .replace("'exames')", "'exames', 'relatorio')")
        .replace("CREATE TABLE prescriptions", "CREATE TABLE prescriptions_new", 1)
    )
    conn.executescript(f"""
        BEGIN;
        {new_sql};
        INSERT INTO prescriptions_new SELECT * FROM prescriptions;
        DROP TABLE prescriptions;
        ALTER TABLE prescriptions_new RENAME TO prescriptions;
        CREATE INDEX IF NOT EXISTS idx_prescriptions_patient
            ON prescriptions (clinic_id, patient_id, created_at);
        COMMIT;
    """)


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)
