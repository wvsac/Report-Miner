"""Clipboard utilities."""

import subprocess
import sys


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard. Returns True if successful."""
    try:
        if sys.platform == "darwin":
            # macOS
            process = subprocess.Popen(
                ["pbcopy"],
                stdin=subprocess.PIPE,
            )
            process.communicate(text.encode("utf-8"))
            return process.returncode == 0

        elif sys.platform == "linux":
            # Linux - try xclip first, then xsel
            for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
                try:
                    process = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                    )
                    process.communicate(text.encode("utf-8"))
                    if process.returncode == 0:
                        return True
                except FileNotFoundError:
                    continue
            return False

        elif sys.platform == "win32":
            # Windows
            process = subprocess.Popen(
                ["clip"],
                stdin=subprocess.PIPE,
            )
            process.communicate(text.encode("utf-8"))
            return process.returncode == 0

        else:
            return False

    except Exception:
        return False
