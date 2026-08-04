"""Almacén en memoria thread-safe para rastrear JTIs consumidos/revocados."""

import threading
import time


class InMemoryJtiStore:
    """
    Rastrea tokens por su JTI para evitar re-uso o permitir revocación.
    Los elementos expirados se limpian automáticamente.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jtis: dict[str, int] = {}

    def _purge(self, now: int | None = None) -> None:
        """Limpia elementos vencidos. NO usar fuera de bloques lock."""
        ts = now if now is not None else int(time.time())
        expired = [j for j, exp in self._jtis.items() if exp <= ts]
        for j in expired:
            self._jtis.pop(j, None)

    def is_consumed_or_mark(self, jti: str, exp: int = 0, mark: bool = False) -> bool:
        """
        Retorna True si el JTI ya existe en el store (fue revocado/consumido).
        Si mark=True y no existe, lo agrega de forma atómica.
        """
        if not jti:
            return False
        with self._lock:
            self._purge()
            if jti in self._jtis:
                return True
            if mark:
                self._jtis[jti] = int(exp)
            return False

    def add(self, jti: str, exp: int) -> None:
        """Agrega directamente un JTI al store."""
        if not jti:
            return
        with self._lock:
            self._purge()
            self._jtis[jti] = int(exp)

    def contains(self, jti: str) -> bool:
        """Verifica si un JTI está en el store sin modificarlo."""
        if not jti:
            return False
        with self._lock:
            self._purge()
            return jti in self._jtis
