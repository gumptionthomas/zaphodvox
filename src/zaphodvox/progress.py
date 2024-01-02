from types import TracebackType
from typing import Optional, Type

from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


class ProgressBar():
    """Represents a progress bar object."""

    def __init__(self, title: str, total: int, completed: int = 0) -> None:
        """Initialize a `ProgressBar` object.

        Args:
            title: The title of the progress bar.
            total: The total number of tasks to be completed.
            completed: The number of tasks already completed. Defaults to `0`.
        """
        self._progress = Progress(
            BarColumn(),
            TextColumn('{task.completed}/{task.total}'),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            TextColumn('['),
            TimeElapsedColumn(),
            TextColumn(']')
        )
        self._task_id = self._progress.add_task(
            title, total=total, completed=completed
        )
        self._live = Live(
            Panel.fit(self._progress, title=title), refresh_per_second=8
        )

    def next(self, n: int = 1) -> None:
        """Advances the progress by the specified amount.

        Args:
            n: The amount by which to advance the progress. Defaults to `1`.
        """
        self._progress.advance(self._task_id, advance=n)

    def __enter__(self):
        """Enter method for context manager."""
        self._live.__enter__()
        return self

    def __exit__(
            self, exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional[TracebackType]
        ) -> None:
            """Exit the context manager and handle any exceptions raised
            within the context.

            Args:
                exc_type: The type of the exception raised, if any.
                exc_val: The exception instance raised, if any.
                exc_tb: The traceback of the exception raised, if any.
            """
            self._live.__exit__(exc_type, exc_val, exc_tb)
