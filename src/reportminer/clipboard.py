"""Clipboard utilities."""

import os
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
            # Linux - try multiple clipboard tools
            # Order: wl-copy (Wayland), xclip, xsel
            clipboard_commands = []

            # Check for Wayland
            if os.environ.get("WAYLAND_DISPLAY"):
                clipboard_commands.append(["wl-copy"])

            # X11 clipboard tools
            clipboard_commands.extend([
                ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"],
            ])

            for cmd in clipboard_commands:
                try:
                    process = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
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
