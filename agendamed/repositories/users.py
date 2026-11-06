"""Repositório dos acessos da equipe (usuários)."""

from agendamed.models import User
from agendamed.repositories.base import Repository


class UserRepository(Repository):
    """SQL dos acessos da equipe (tabela `users`)."""

    def create(self, email: str, full_name: str, password_hash: str) -> User:
        """Cria um acesso. E-mail repetido vira ConflictError."""
        user_id = self._insert(
            "INSERT INTO users (email, full_name, password_hash) VALUES (?, ?, ?)",
            (email, full_name, password_hash),
            "Já existe um usuário com este e-mail.",
        )
        return self.get(user_id)

    def get(self, user_id: int) -> User | None:
        """O usuário pelo id, ou None."""
        row = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return User.from_row(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        """O usuário pelo e-mail, ou None."""
        row = self.conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return User.from_row(row) if row else None
