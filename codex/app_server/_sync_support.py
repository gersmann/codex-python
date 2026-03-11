from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, TypeVar, cast

_T = TypeVar("_T")


class _SyncRunner:
    def __init__(self, runner: Callable[[Coroutine[Any, Any, Any]], Any]) -> None:
        self._runner = runner

    def _run(self, coro: Coroutine[Any, Any, _T]) -> _T:
        return cast(_T, self._runner(coro))
