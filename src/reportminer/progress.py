"""Progress indicators with spinner animation."""

import random
import sys
import threading
import time
from typing import Optional

from .config import SPINNER_STYLE


# Unicode spinner - fancy stars animation
UNICODE_FRAMES = [".", "*", "\u2736", "\u2734", "\u2733", "\u273a", "\u2739", "\u2735"]

# ASCII spinner - works on any terminal
ASCII_FRAMES = [".", "o", "O", "@", "*", ".", "o", "O"]

SPINNER_INTERVAL = 0.1

LOADING_PHRASES = [
    "Brewing some test results",
    "Hunting for failed tests",
    "Interrogating HTML files",
    "Decoding test mysteries",
    "Extracting the juice",
    "Crunching test data",
    "Summoning test spirits",
    "Reading the tea leaves",
    "Consulting the oracle",
    "Waking up the parser",
    "Doing the heavy lifting",
    "Making sense of chaos",
    "Untangling test results",
    "Performing dark magic",
    "Channeling inner pytest",
]

WRITING_PHRASES = [
    "Scribbling results",
    "Saving the goods",
    "Writing it down",
    "Exporting findings",
]


def get_spinner_frames() -> list[str]:
    """Return spinner frames based on config setting."""
    if SPINNER_STYLE == "ascii":
        return ASCII_FRAMES
    return UNICODE_FRAMES


def get_random_phrase(phrase_type: str = "loading") -> str:
    """Return a random phrase for the given type."""
    if phrase_type == "writing":
        return random.choice(WRITING_PHRASES)
    return random.choice(LOADING_PHRASES)


class Spinner:
    """Animated spinner for showing progress."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_index = 0
        self._message = ""
        self._progress = ""
        self._lock = threading.Lock()
        self._is_tty = sys.stderr.isatty()
        self._frames = get_spinner_frames()

    def _animate(self):
        """Animation loop that runs in a separate thread."""
        while self._running:
            if self._is_tty:
                with self._lock:
                    frame = self._frames[self._frame_index]
                    line = f"\r{frame} {self._message} {self._progress}"
                    sys.stderr.write(line)
                    sys.stderr.flush()

                    # Move to next frame, skip first frame (dot) after initial show
                    self._frame_index = (self._frame_index + 1) % len(self._frames)
                    if self._frame_index == 0:
                        self._frame_index = 1

            time.sleep(SPINNER_INTERVAL)

    def start(self, message: str = ""):
        """Start the spinner with given message."""
        if not self._is_tty:
            return

        self._running = True
        self._frame_index = 0
        self._message = message
        self._progress = ""
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def update(self, message: Optional[str] = None, progress: Optional[str] = None):
        """Update the spinner message or progress text."""
        with self._lock:
            if message is not None:
                self._message = message
            if progress is not None:
                self._progress = progress

    def stop(self, final_message: Optional[str] = None):
        """Stop the spinner and optionally show a final message."""
        self._running = False

        if self._thread:
            self._thread.join(timeout=0.5)
            self._thread = None

        if self._is_tty:
            # Clear the line
            sys.stderr.write("\r" + " " * 80 + "\r")
            if final_message:
                checkmark = "+" if SPINNER_STYLE == "ascii" else "\u2713"
                sys.stderr.write(f"{checkmark} {final_message}\n")
            sys.stderr.flush()


class ProgressContext:
    """Context manager for tracking progress of an operation."""

    def __init__(self, message: str):
        self.message = message
        self.spinner = Spinner()
        self.current = 0
        self.total = 0

    def __enter__(self):
        self.spinner.start(self.message)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.spinner.stop(f"Done. {self.total} items processed.")
        else:
            self.spinner.stop("Failed.")
        return False

    def update(self, current: int, total: int, item: str = ""):
        """Update the progress counter."""
        self.current = current
        self.total = total
        if total > 0:
            pct = int((current / total) * 100)
            progress = f"{pct}%"
            if item and item != "complete":
                progress = f"({current}/{total})"
            self.spinner.update(progress=progress)


def create_progress_callback(spinner: Spinner):
    """Create a callback function for tracking parsing progress."""
    def callback(current: int, total: int, item: str = ""):
        if item == "complete":
            return
        if total > 0:
            progress = f"({current + 1}/{total})"
            spinner.update(progress=progress)
    return callback
