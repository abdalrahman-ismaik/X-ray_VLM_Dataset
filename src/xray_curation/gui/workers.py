from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Thread
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class WorkerHandle:
    thread: Thread

    def is_alive(self) -> bool:
        return self.thread.is_alive()


def run_tk_worker(
    root,
    work: Callable[[], T],
    on_success: Callable[[T], None],
    on_error: Callable[[BaseException], None],
) -> WorkerHandle:
    def runner() -> None:
        try:
            result = work()
        except BaseException as exc:
            root.after(0, lambda: on_error(exc))
        else:
            root.after(0, lambda: on_success(result))

    thread = Thread(target=runner, daemon=True)
    thread.start()
    return WorkerHandle(thread=thread)


def run_operation(
    root,
    operation_name: str,
    work: Callable[[], T],
    on_success: Callable[[T], None],
    on_error: Callable[[BaseException], None],
) -> WorkerHandle:
    return run_tk_worker(root, work, on_success, on_error)
