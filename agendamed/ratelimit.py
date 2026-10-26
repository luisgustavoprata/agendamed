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
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
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
        with self._lock:
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
