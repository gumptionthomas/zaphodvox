from typing import Optional

from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


class ProgressBar():
    """Represents a progress bar object."""

    def __init__(
        self, title: str, total: Optional[int], completed: int = 0,
    ) -> None:
        """Initialize a `ProgressBar` object.

        Args:
            title: The title of the progress bar.
            total: The total number of tasks to be completed.
            completed: The number of tasks already completed. Defaults to `0`.
        """
        args: list[ProgressColumn] = [BarColumn()]
        if total is not None:
            args.append(TextColumn('{task.completed}/{task.total}'))
            args.append(TaskProgressColumn())
            args.append(TimeRemainingColumn())
        args.append(TextColumn('['))
        args.append(TimeElapsedColumn())
        args.append(TextColumn(']'))
        self._progress = Progress(*args)
        self._task_id = self._progress.add_task(
            title, total=total, completed=completed
        )
        self._live = Live(Panel.fit(self._progress, title=title))

    @property
    def console(self):
        """The console object for the progress bar."""
        return self._progress.console

    def next(self, n: int = 1) -> None:
        """Advances the progress by the specified amount.

        Args:
            n: The amount by which to advance the progress. Defaults to `1`.
        """
        self._progress.advance(self._task_id, advance=n)

    def stop(self) -> None:
        """Completes and stops the progress bar."""

        self._progress.update(self._task_id, total=0)
        self._progress.stop()

    def __enter__(self):
        """Enter method for context manager."""
        self._live.__enter__()
        return self

    def __exit__(self, *args) -> None:
        """Exit the context manager and handle any exceptions raised
        within the context.
        """
        self._live.__exit__(*args)
