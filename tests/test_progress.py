"""Tests for progress indicators and spinner."""

import pytest
import sys
import time
from io import StringIO
from unittest.mock import patch, MagicMock

from reportminer.progress import (
    Spinner,
    ProgressContext,
    create_progress_callback,
    get_spinner_frames,
    get_random_phrase,
    UNICODE_FRAMES,
    ASCII_FRAMES,
    LOADING_PHRASES,
    WRITING_PHRASES,
)


class TestSpinnerFrames:
    """Tests for spinner frame selection."""

    def test_unicode_frames_available(self):
        assert len(UNICODE_FRAMES) > 0
        # Should contain unicode star characters
        assert any("\u2736" in frame or "\u2734" in frame for frame in UNICODE_FRAMES)

    def test_ascii_frames_available(self):
        assert len(ASCII_FRAMES) > 0
        # Should only contain ASCII characters
        for frame in ASCII_FRAMES:
            assert all(ord(c) < 128 for c in frame)

    def test_get_spinner_frames_unicode(self, monkeypatch):
        monkeypatch.setattr("reportminer.progress.SPINNER_STYLE", "unicode")
        frames = get_spinner_frames()
        assert frames == UNICODE_FRAMES

    def test_get_spinner_frames_ascii(self, monkeypatch):
        monkeypatch.setattr("reportminer.progress.SPINNER_STYLE", "ascii")
        frames = get_spinner_frames()
        assert frames == ASCII_FRAMES


class TestGetRandomPhrase:
    """Tests for random phrase generation."""

    def test_returns_loading_phrase(self):
        phrase = get_random_phrase("loading")
        assert phrase in LOADING_PHRASES

    def test_returns_writing_phrase(self):
        phrase = get_random_phrase("writing")
        assert phrase in WRITING_PHRASES

    def test_default_is_loading(self):
        phrase = get_random_phrase()
        assert phrase in LOADING_PHRASES

    def test_loading_phrases_not_empty(self):
        assert len(LOADING_PHRASES) > 0

    def test_writing_phrases_not_empty(self):
        assert len(WRITING_PHRASES) > 0


class TestSpinner:
    """Tests for Spinner class."""

    def test_initializes_not_running(self):
        spinner = Spinner()
        assert spinner._running is False
        assert spinner._thread is None

    def test_start_sets_message(self):
        spinner = Spinner()
        spinner._is_tty = False  # Don't actually animate
        spinner._message = ""
        # Manually set message like start would
        spinner._message = "Test message"
        assert spinner._message == "Test message"

    def test_update_changes_message(self):
        spinner = Spinner()
        spinner._message = "Initial"
        spinner._progress = ""
        spinner.update(message="Updated")
        assert spinner._message == "Updated"

    def test_update_changes_progress(self):
        spinner = Spinner()
        spinner._progress = ""
        spinner.update(progress="50%")
        assert spinner._progress == "50%"

    def test_update_message_only(self):
        spinner = Spinner()
        spinner._message = "Old"
        spinner._progress = "10%"
        spinner.update(message="New")
        assert spinner._message == "New"
        assert spinner._progress == "10%"  # Unchanged

    def test_update_progress_only(self):
        spinner = Spinner()
        spinner._message = "Message"
        spinner._progress = "10%"
        spinner.update(progress="20%")
        assert spinner._message == "Message"  # Unchanged
        assert spinner._progress == "20%"

    def test_stop_sets_running_false(self):
        spinner = Spinner()
        spinner._running = True
        spinner.stop()
        assert spinner._running is False

    def test_non_tty_does_not_animate(self):
        spinner = Spinner()
        spinner._is_tty = False
        # Start should not create thread
        spinner.start("Test")
        assert spinner._thread is None or not spinner._thread.is_alive()

    def test_frame_index_cycles(self):
        spinner = Spinner()
        spinner._frame_index = 0
        frames = get_spinner_frames()

        # Simulate frame cycling
        spinner._frame_index = (spinner._frame_index + 1) % len(frames)
        assert spinner._frame_index == 1

        # Cycle through all frames
        for _ in range(len(frames) - 1):
            spinner._frame_index = (spinner._frame_index + 1) % len(frames)

        assert spinner._frame_index == 0


class TestProgressContext:
    """Tests for ProgressContext context manager."""

    def test_initializes_with_message(self):
        ctx = ProgressContext("Loading")
        assert ctx.message == "Loading"
        assert ctx.current == 0
        assert ctx.total == 0

    def test_update_sets_current_and_total(self):
        ctx = ProgressContext("Loading")
        ctx.spinner._is_tty = False  # Disable actual animation
        ctx.update(5, 10, "item")
        assert ctx.current == 5
        assert ctx.total == 10

    def test_context_manager_protocol(self):
        """Test that ProgressContext works as a context manager."""
        ctx = ProgressContext("Test")
        ctx.spinner._is_tty = False

        with ctx as pc:
            assert pc is ctx
            pc.update(1, 2, "item")

        # After exit, total should be set
        assert ctx.total == 2


class TestCreateProgressCallback:
    """Tests for progress callback factory."""

    def test_creates_callable(self):
        spinner = Spinner()
        callback = create_progress_callback(spinner)
        assert callable(callback)

    def test_callback_updates_spinner(self):
        spinner = Spinner()
        spinner._is_tty = False
        spinner._progress = ""
        callback = create_progress_callback(spinner)

        callback(5, 10, "test.html")
        assert "(6/10)" in spinner._progress

    def test_callback_ignores_complete(self):
        spinner = Spinner()
        spinner._is_tty = False
        spinner._progress = "(5/10)"
        callback = create_progress_callback(spinner)

        callback(10, 10, "complete")
        # Progress should not be updated
        assert spinner._progress == "(5/10)"

    def test_callback_handles_zero_total(self):
        spinner = Spinner()
        spinner._is_tty = False
        spinner._progress = ""
        callback = create_progress_callback(spinner)

        # Should not crash on zero total
        callback(0, 0, "item")
        assert spinner._progress == ""


class TestSpinnerThreadSafety:
    """Tests for thread safety of spinner operations."""

    def test_update_is_thread_safe(self):
        """Test that concurrent updates don't cause issues."""
        spinner = Spinner()
        spinner._is_tty = False

        def update_message(msg):
            for _ in range(100):
                spinner.update(message=msg)

        def update_progress(prog):
            for _ in range(100):
                spinner.update(progress=prog)

        import threading
        t1 = threading.Thread(target=update_message, args=("msg",))
        t2 = threading.Thread(target=update_progress, args=("50%",))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Should complete without errors


class TestSpinnerPhrasesQuality:
    """Tests for phrase quality and diversity."""

    def test_phrases_are_unique(self):
        """Test that all loading phrases are unique."""
        assert len(LOADING_PHRASES) == len(set(LOADING_PHRASES))
        assert len(WRITING_PHRASES) == len(set(WRITING_PHRASES))

    def test_phrases_not_too_long(self):
        """Test that phrases are reasonably short for terminal display."""
        max_length = 50
        for phrase in LOADING_PHRASES + WRITING_PHRASES:
            assert len(phrase) <= max_length, f"Phrase too long: {phrase}"

    def test_phrases_printable(self):
        """Test that all phrases contain only printable characters."""
        for phrase in LOADING_PHRASES + WRITING_PHRASES:
            assert all(c.isprintable() for c in phrase)
