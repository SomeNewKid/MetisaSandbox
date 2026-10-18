"""Utility functions for working with the terminal."""

from __future__ import annotations

import shutil
import sys
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import TextIO

SUCCESS_INDICATOR = "✔"
FAILURE_INDICATOR = "x"

_SPINNER_FRAMES = tuple("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
_SPINNER_INTERVAL_SECONDS = 0.1


class TerminalStatus:
    """Track whether an operation has failed."""

    def __init__(self) -> None:
        """Initialize the terminal status."""
        self._failed = False

    @property
    def failed(self) -> bool:
        """Return whether failure was explicitly reported."""
        return self._failed

    def fail(self) -> None:
        """Mark the operation as failed."""
        self._failed = True


@contextmanager
def terminal_status(
    *,
    running: str,
    success: str,
    failure: str,
    stream: TextIO | None = None,
) -> Generator[TerminalStatus, None, None]:
    """Display progress and a final result without suppressing exceptions."""
    status = TerminalStatus()
    output = stream if stream is not None else sys.stdout

    if output is None:
        yield status
        return

    animated = output.isatty()
    stop_event = threading.Event()
    spinner_thread: threading.Thread | None = None

    indicator = SUCCESS_INDICATOR
    final_message = success

    if animated:
        frames = _get_spinner_frames(output)
        _write_status_line(output, frames[0], running)

        def _animate() -> None:
            frame_index = 1

            while not stop_event.wait(_SPINNER_INTERVAL_SECONDS):
                frame = frames[frame_index % len(frames)]
                _write_status_line(output, frame, running)
                frame_index += 1

        spinner_thread = threading.Thread(
            target=_animate,
            name="terminal-status",
            daemon=True,
        )

    started_at = time.monotonic()

    try:
        if spinner_thread is not None:
            spinner_thread.start()

        yield status

    except BaseException:
        indicator = FAILURE_INDICATOR
        final_message = failure
        raise

    finally:
        stop_event.set()

        if spinner_thread is not None and spinner_thread.ident is not None:
            spinner_thread.join()

        if status.failed:
            indicator = FAILURE_INDICATOR
            final_message = failure

        elapsed_seconds = int(time.monotonic() - started_at)
        duration = _format_duration(elapsed_seconds)

        if duration:
            final_message = f"{final_message} {duration}"

        if animated:
            _write_status_line(output, indicator, final_message)
            output.write("\n")
        else:
            message = _single_line(final_message)
            output.write(f"{indicator} {message}\n")

        output.flush()


def _get_spinner_frames(stream: TextIO) -> tuple[str, ...]:
    encoding = stream.encoding or "utf-8"

    try:
        "".join(_SPINNER_FRAMES).encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return ("|", "/", "-", "\\")

    return _SPINNER_FRAMES


def _write_status_line(
    stream: TextIO,
    indicator: str,
    message: str,
) -> None:
    message = _single_line(message)
    text = f"{indicator} {message}"

    terminal_width = shutil.get_terminal_size(fallback=(80, 24)).columns
    available_width = max(terminal_width - 1, 1)

    if len(text) > available_width:
        text = text[:available_width]

    stream.write(f"\r\x1b[2K{text}")
    stream.flush()


def _single_line(message: str) -> str:
    return " ".join(message.splitlines())


def _format_duration(elapsed_seconds: int) -> str:
    if elapsed_seconds < 1:
        return ""

    minutes, seconds = divmod(elapsed_seconds, 60)

    if minutes:
        return f"[{minutes}m {seconds}s]"

    return f"[{seconds}s]"
