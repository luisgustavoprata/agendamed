"""Peças comuns dos repositórios: a página de resultados e a classe base.

Um repositório é a classe que conversa com o banco de dados: todo o SQL de um assunto
fica no repositório dele. As rotas e os serviços nunca escrevem SQL, só chamam métodos
como `PatientRepository(conn).get(patient_id)`.
"""

import sqlite3
from dataclasses import dataclass

from agendamed.errors import ConflictError


@dataclass(frozen=True, slots=True)
class Page:
    items: list
    total: int
    limit: int
    offset: int

    def to_dict(self) -> dict:
        return {
            "items": [item.to_dict() for item in self.items],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
        }


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _insert(self, sql: str, params: tuple, conflict_message: str) -> int:
        try:
            cursor = self.conn.execute(sql, params)
        except sqlite3.IntegrityError as exc:
            raise ConflictError(conflict_message) from exc
        return cursor.lastrowid

    def _page(self, base_sql, where, params, model, order_by, limit, offset) -> Page:
        where_sql = f" WHERE {' AND '.join(where)}" if where else ""
        total = self.conn.execute(
            f"SELECT COUNT(*) FROM ({base_sql}{where_sql})", params
        ).fetchone()[0]
        rows = self.conn.execute(
            f"{base_sql}{where_sql} ORDER BY {order_by} LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return Page([model.from_row(row) for row in rows], total, limit, offset)
