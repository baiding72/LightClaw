"""Small retry helpers for transient LLM/provider failures."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


TRANSIENT_MARKERS = (
    "429",
    "rate limit",
    "rate_limit",
    "temporarily unavailable",
    "timeout",
    "connection",
    "server error",
    "503",
    "502",
    "500",
)


def is_transient_error(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in TRANSIENT_MARKERS)


def call_with_retry(fn: Callable[[], T], *, attempts: int = 3, base_delay: float = 1.0) -> T:
    last_exc: BaseException | None = None
    for index in range(max(1, attempts)):
        try:
            return fn()
        except BaseException as exc:
            last_exc = exc
            if index >= attempts - 1 or not is_transient_error(exc):
                raise
            time.sleep(base_delay * (2**index))
    assert last_exc is not None
    raise last_exc
