"""Base da gestão: a conexão, a clínica e as conferências usadas por todas as partes.

Esta versão atende uma clínica só, com o banco SQLite da agenda: CLINIC_ID é sempre 1, e
GestaoDb adapta a conexão sqlite3 aos métodos (`one`, `all`, `insert`...) que a gestão usa.
Mesmo assim, todo o SQL da gestão inclui o `clinic_id`. As funções `_row`, `_bools` e
`_iso` convertem valores entre o banco e o JSON.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date

from agendamed.errors import ConflictError, NotFoundError


def _row(row) -> dict | None:
    """Converte uma linha do banco em dicionário (ou devolve None se não houver linha)."""
    return dict(row) if row is not None else None


def _bools(item: dict, *names: str) -> dict:
    """Converte para verdadeiro/falso os campos informados (o SQLite guarda 0 e 1)."""
    for name in names:
        if name in item:
            item[name] = bool(item[name])
    return item


def _iso(value: date | None) -> str | None:
    """Data no formato "AAAA-MM-DD", ou None se não houver data."""
    return value.isoformat() if value else None


# Nesta versão há uma clínica só. As tabelas de gestão (e pacientes, médicos e consultas)
# têm a coluna clinic_id sempre igual a 1, o que mantém o SQL igual ao da versão para
# várias clínicas.
CLINIC_ID = 1


class GestaoDb:
    """Adapta a conexão sqlite3 desta versão à interface usada pelo repositório."""

    integrity_errors = (sqlite3.IntegrityError,)

    def __init__(self, conn: sqlite3.Connection):
        """Guarda a conexão sqlite3 aberta pela agenda."""
        self.raw = conn

    def execute(self, sql: str, params=()):
        """Executa um comando SQL com os parâmetros e devolve o cursor."""
        return self.raw.execute(sql, tuple(params))

    def one(self, sql: str, params=()):
        """Executa uma consulta e devolve a primeira linha (ou None se não houver)."""
        return self.execute(sql, params).fetchone()

    def all(self, sql: str, params=()) -> list:
        """Executa uma consulta e devolve todas as linhas numa lista."""
        return self.execute(sql, params).fetchall()

    def insert(self, sql: str, params=()) -> int:
        """Executa um INSERT e devolve o id da linha criada."""
        return self.execute(sql, params).lastrowid

    @contextmanager
    def transaction(self, *, lock_keys=()):
        """Tudo ou nada: se algo falhar no meio, nada é gravado. Com `lock_keys`, reserva o banco
        para escrita já no começo (BEGIN IMMEDIATE).
        """
        self.raw.execute("BEGIN IMMEDIATE" if lock_keys else "BEGIN")
        try:
            yield
        except BaseException:
            self.raw.execute("ROLLBACK")
            raise
        self.raw.execute("COMMIT")


class GestaoBase:
    """Guarda a conexão e a clínica e confere se cada registro é dela."""

    def __init__(self, db, clinic_id: int):
        """Guarda a conexão e a clínica dona de todos os dados da gestão."""
        self.db = db
        self.clinic_id = clinic_id

    def _insert(self, sql: str, params: tuple, conflict: str) -> int:
        """Executa um INSERT e devolve o id. Duplicidade (ex.: nome repetido) vira ConflictError
        com a mensagem `conflict`.
        """
        try:
            return self.db.insert(sql, params)
        except self.db.integrity_errors as exc:
            raise ConflictError(conflict) from exc

    def require_patient(self, patient_id: int) -> dict:
        """Dados básicos do paciente, se ele for desta clínica; senão, erro 404."""
        row = self.db.one(
            "SELECT id, name, cpf, birth_date FROM patients WHERE id = ? AND clinic_id = ?",
            (patient_id, self.clinic_id),
        )
        if row is None:
            raise NotFoundError("Paciente não encontrado.")
        return dict(row)

    def require_doctor(self, doctor_id: int) -> dict:
        """Dados básicos do médico (nome, especialidade e CRM), se ele for desta clínica; senão,
        erro 404.
        """
        row = self.db.one(
            "SELECT id, name, specialty, crm FROM doctors WHERE id = ? AND clinic_id = ?",
            (doctor_id, self.clinic_id),
        )
        if row is None:
            raise NotFoundError("Médico não encontrado.")
        return dict(row)

    def require_appointment(self, appointment_id: int) -> dict:
        """Dados da consulta com os nomes do médico e do paciente, se ela for desta clínica;
        senão, erro 404.
        """
        row = self.db.one(
            """SELECT a.id, a.doctor_id, a.patient_id, a.start_at, a.status,
                      d.name AS doctor_name, p.name AS patient_name
               FROM appointments a JOIN doctors d ON d.id = a.doctor_id
               JOIN patients p ON p.id = a.patient_id
               WHERE a.id = ? AND a.clinic_id = ?""",
            (appointment_id, self.clinic_id),
        )
        if row is None:
            raise NotFoundError("Consulta não encontrada.")
        return dict(row)

    def _require_in_clinic(self, table: str, item_id: int | None, message: str) -> None:
        """Confere se o registro da tabela é desta clínica (erro 404 se não for). Sem id (None),
        não há o que conferir.
        """
        if item_id is None:
            return
        if (
            self.db.one(
                f"SELECT id FROM {table} WHERE id = ? AND clinic_id = ?", (item_id, self.clinic_id)
            )
            is None
        ):
            raise NotFoundError(message)

    def _get(self, table: str, columns: str, item_id: int, message: str) -> dict:
        """Um registro de `table` desta clínica, como dicionário; senão, erro 404 com `message`."""
        row = self.db.one(
            f"SELECT {columns} FROM {table} WHERE id = ? AND clinic_id = ?",
            (item_id, self.clinic_id),
        )
        if row is None:
            raise NotFoundError(message)
        return _bools(dict(row), "active")

    def _list(self, table: str, columns: str, *, only_active: bool) -> list[dict]:
        """Os registros de `table` desta clínica em ordem alfabética (só os ativos, se
        `only_active`).
        """
        where = "clinic_id = ?" + (" AND active = 1" if only_active else "")
        rows = self.db.all(
            f"SELECT {columns} FROM {table} WHERE {where} ORDER BY name", (self.clinic_id,)
        )
        return [_bools(dict(r), "active") for r in rows]
