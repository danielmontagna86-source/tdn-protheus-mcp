"""Harness-independent adapter boundary for explicit snapshot refreshes."""

from __future__ import annotations

import time
from typing import Callable

from .contracts import PolicyRefusal
from .mutations import RefreshPlan


class SnapshotRefreshAdapter:
    def __init__(
        self,
        collector: Callable[..., dict[str, int]],
        *,
        clock: Callable[[], float] = time.monotonic,
        default_timeout_seconds: float | None = None,
    ) -> None:
        self._collector = collector
        self._clock = clock
        self._default_timeout_seconds = default_timeout_seconds

    def __call__(
        self, plan: RefreshPlan, *, cancelled: Callable[[], bool] | None = None, timeout_seconds: float | None = None
    ) -> dict[str, int]:
        if timeout_seconds is None:
            timeout_seconds = self._default_timeout_seconds
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise PolicyRefusal("POLICY_REFRESH_TIMEOUT", "o prazo de atualização expirou antes de iniciar")
        deadline = self._clock() + timeout_seconds if timeout_seconds is not None else None

        def check_cancelled() -> bool:
            if cancelled and cancelled():
                return True
            if deadline is not None and self._clock() >= deadline:
                raise PolicyRefusal("POLICY_REFRESH_TIMEOUT", "o prazo de atualização expirou durante a coleta")
            return False

        if check_cancelled():
            raise PolicyRefusal("POLICY_REFRESH_CANCELLED", "atualização cancelada antes de iniciar")
        return self._collector(plan, cancelled=check_cancelled)
