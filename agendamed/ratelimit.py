"""Limite de tentativas de login (proteção contra força bruta).

Guarda, por chave (IP + e-mail), os horários das tentativas que falharam dentro de uma
janela deslizante. Ao atingir o limite, novas tentativas são recusadas até a mais antiga
sair da janela.

A contagem fica em memória, por processo. Em produção com vários servidores, o mesmo
algoritmo usaria um armazenamento compartilhado, como o Redis.
"""

import math
import threading
from collections import defaultdict, deque


class LoginRateLimiter:
    """Conta tentativas que falharam e bloqueia quem passa do limite.

    Apesar do nome, também limita outros abusos (pedidos de nova senha, agendamentos pela página
    pública). Cada uso tem a sua instância, criada em `create_app` e guardada em `app.extensions`.
    """

    def __init__(self, max_attempts: int, window_seconds: int):
        """`max_attempts` falhas são aceitas dentro de cada janela de `window_seconds`."""
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        """Descarta as falhas que já saíram da janela e devolve as que sobraram."""
        attempts = self._failures[key]
        while attempts and attempts[0] <= now - self.window_seconds:
            attempts.popleft()
        return attempts

    def retry_after(self, key: str, now: float) -> int | None:
        """Segundos até poder tentar de novo, ou None se a tentativa está liberada."""
        with self._lock:
            attempts = self._prune(key, now)
            if len(attempts) < self.max_attempts:
                return None
            return max(1, math.ceil(attempts[0] + self.window_seconds - now))

    def register_failure(self, key: str, now: float) -> None:
        """Registra uma falha da chave no horário `now`."""
        with self._lock:
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        """Zera a contagem da chave (ex.: depois de um login correto)."""
        with self._lock:
            self._failures.pop(key, None)
