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
    """Uma página de resultados: os itens, o total de registros e a posição.

    `limit` é quantos itens vêm por página e `offset`, quantos foram pulados.
    """

    items: list
    total: int
    limit: int
    offset: int

    def to_dict(self) -> dict:
        """A página no formato JSON da API."""
        return {
            "items": [item.to_dict() for item in self.items],
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
        }


class Repository:
    """Base dos repositórios: guarda a conexão e tem ajudantes de SQL."""

    def __init__(self, conn: sqlite3.Connection):
        """Guarda a conexão com o banco (sqlite3)."""
        self.conn = conn

    def _insert(self, sql: str, params: tuple, conflict_message: str) -> int:
        """Executa um INSERT e devolve o id criado. Se o banco recusar por duplicidade (ex.: CPF
        já cadastrado), lança ConflictError com `conflict_message`.
        """
        try:
            cursor = self.conn.execute(sql, params)
        except sqlite3.IntegrityError as exc:
            raise ConflictError(conflict_message) from exc
        return cursor.lastrowid

    def _page(self, base_sql, where, params, model, order_by, limit, offset) -> Page:
        """Busca uma página de resultados: conta o total com os mesmos filtros (`where`) e traz
        só os itens da página, na ordem `order_by`, convertidos com `model.from_row`.
        """
        where_sql = f" WHERE {' AND '.join(where)}" if where else ""
        total = self.conn.execute(
            f"SELECT COUNT(*) FROM ({base_sql}{where_sql})", params
        ).fetchone()[0]
        rows = self.conn.execute(
            f"{base_sql}{where_sql} ORDER BY {order_by} LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return Page([model.from_row(row) for row in rows], total, limit, offset)
