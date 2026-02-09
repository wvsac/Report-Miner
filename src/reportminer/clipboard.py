"""Clipboard utilities."""

import os
import subprocess
import sys


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard. Returns True if successful."""
    try:
        if sys.platform == "darwin":
            return _run_clipboard_cmd(["pbcopy"], text)

        elif sys.platform == "linux":
            # Try multiple clipboard tools in order of preference
            commands = []

            # Wayland
            if os.environ.get("WAYLAND_DISPLAY"):
                commands.append(["wl-copy"])

            # X11 - xsel is more reliable than xclip for piped input
            # (xclip can lose clipboard when process exits)
            commands.extend([
                ["xsel", "--clipboard", "--input"],
                ["xclip", "-selection", "clipboard"],
            ])

            for cmd in commands:
                try:
                    if _run_clipboard_cmd(cmd, text):
                        return True
                except FileNotFoundError:
                    continue
            return False

        elif sys.platform == "win32":
            return _run_clipboard_cmd(["clip"], text)

        else:
            return False

    except Exception:
        return False


def _run_clipboard_cmd(cmd: list[str], text: str) -> bool:
    """Run a clipboard command, piping text to stdin."""
    result = subprocess.run(
        cmd,
        input=text.encode("utf-8"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )
    return result.returncode == 0
