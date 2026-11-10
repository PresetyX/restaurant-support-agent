"""Fila de transferência para atendimento humano (em memória, para demo)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any


class HandoffQueue:
    def __init__(self) -> None:
        self._tickets: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def create(self, session_id: str, reason: str, summary: str) -> dict[str, Any]:
        with self._lock:
            ticket = {
                "ticket_id": f"ATD-{len(self._tickets) + 1:04d}",
                "session_id": session_id,
                "reason": reason,
                "summary": summary[:500],
                "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
            self._tickets.append(ticket)
        return ticket

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._tickets)
