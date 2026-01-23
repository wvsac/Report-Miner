"""Main Textual application for test result viewer."""

import re
import webbrowser

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Static, Input, ListView, ListItem, Label
from textual.timer import Timer
from textual import events
from rich.text import Text

from ..clipboard import copy_to_clipboard
from ..models import TestResult, TestStatus


# Pre-compiled regex for log level detection
LOG_LEVEL_PATTERN = re.compile(
    r'\b(FATAL|ERROR|ERR|WARNING|WARN|INFO|DEBUG|DBG|TRACE|TRC)\b',
    re.IGNORECASE
)

# Patterns for pytest sections
SECTION_PATTERNS = [
    (re.compile(r'-+\s*live log setup\s*-+', re.IGNORECASE), "setup"),
    (re.compile(r'-+\s*live log call\s*-+', re.IGNORECASE), "call"),
    (re.compile(r'-+\s*live log teardown\s*-+', re.IGNORECASE), "teardown"),
    (re.compile(r'-+\s*Captured log setup\s*-+', re.IGNORECASE), "setup"),
    (re.compile(r'-+\s*Captured log call\s*-+', re.IGNORECASE), "call"),
    (re.compile(r'-+\s*Captured log teardown\s*-+', re.IGNORECASE), "teardown"),
]

LOG_COLORS = {
    "FATAL": "bold red reverse",
    "ERROR": "bold red",
    "ERR": "bold red",
    "WARNING": "yellow",
    "WARN": "yellow",
    "INFO": "green",
    "DEBUG": "blue",
    "DBG": "blue",
    "TRACE": "dim cyan",
    "TRC": "dim cyan",
}

STATUS_COLORS = {
    TestStatus.PASSED: "green",
    TestStatus.FAILED: "red",
    TestStatus.SKIPPED: "yellow",
    TestStatus.ERROR: "red bold",
    TestStatus.XFAILED: "dim yellow",
    TestStatus.XPASSED: "dim green",
}

STATUS_ICONS = {
    TestStatus.PASSED: "+",
    TestStatus.FAILED: "x",
    TestStatus.SKIPPED: "-",
    TestStatus.ERROR: "!",
    TestStatus.XFAILED: "~",
    TestStatus.XPASSED: "~",
}

def normalize_tms(text: str) -> str:
    """Normalize TMS format - treat TMS-123 and TMS_123 as equivalent."""
    return text.lower().replace("-", "_")


class TestListItem(ListItem):
    """Single test item in the list."""

    def __init__(self, result: TestResult, marked: bool = False):
        super().__init__()
        self.result = result
        self.marked = marked

    def compose(self) -> ComposeResult:
        yield Label(self._build_label())

    def _build_label(self) -> Text:
        """Build the label text for this item."""
        color = STATUS_COLORS.get(self.result.status, "white")
        status_icon = STATUS_ICONS.get(self.result.status, "?")
        mark_indicator = "*" if self.marked else " "

        text = Text()
        text.append(f"{mark_indicator}[{status_icon}] ", style=color)
        text.append(f"{self.result.tms_jira_format} ", style="bold")
        text.append(self.result.test_name_readable, style="dim")

        return text

    def toggle_mark(self):
        """Toggle the marked state."""
        self.marked = not self.marked
        self.query_one(Label).update(self._build_label())


class TestDetailPanel(VerticalScroll):
    """Panel showing detailed test information with keyboard scrolling."""

    can_focus = True

    BINDINGS = [
        Binding("up", "scroll_up", "Scroll Up", show=False),
        Binding("down", "scroll_down", "Scroll Down", show=False),
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
        Binding("home", "scroll_home", "Top", show=False),
        Binding("end", "scroll_end", "Bottom", show=False),
        Binding("j", "scroll_down", "Scroll Down", show=False),
        Binding("k", "scroll_up", "Scroll Up", show=False),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_test: TestResult | None = None
        self._content_cache: dict[str, Text] = {}
        self._raw_log: str = ""
        self._section_lines: dict[str, int] = {}
        self._search_query: str = ""
        self._search_matches: list[int] = []
        self._current_match: int = -1
        self._total_lines: int = 0

    def compose(self) -> ComposeResult:
        yield Static("Select a test to view details", id="detail-content")

    def show_test(self, result: TestResult):
        """Display details for a test result."""
        self.current_test = result
        self._raw_log = result.execution_log or ""
        self._search_query = ""
        self._search_matches = []
        self._current_match = -1

        cache_key = result.tms_number
        if cache_key in self._content_cache:
            content = self._content_cache[cache_key]
        else:
            content = self._build_detail_content(result)
            if len(self._content_cache) < 100:
                self._content_cache[cache_key] = content

        self.query_one("#detail-content", Static).update(content)
        self.scroll_home(animate=False)

    def jump_to_section(self, section: str) -> bool:
        """Jump to a section (setup/call/teardown). Returns True if found."""
        if section not in self._section_lines:
            return False

        line_num = self._section_lines[section]

        # Map line number to virtual scroll position proportionally
        # virtual_size.height may differ from _total_lines due to rendering
        if self._total_lines > 0 and self.virtual_size.height > 0:
            ratio = max(0, line_num - 1) / self._total_lines
            target_y = ratio * self.virtual_size.height
            self.scroll_to(y=target_y, animate=False)

        return True

    def search_log(self, query: str) -> int:
        """Search for text in log, returns number of matches."""
        self._search_query = query.lower()
        self._search_matches = []
        self._current_match = -1

        if not query or not self._raw_log:
            # Rebuild content without highlights
            if self.current_test:
                # Clear cache to rebuild without highlights
                cache_key = self.current_test.tms_number
                if cache_key in self._content_cache:
                    del self._content_cache[cache_key]
                content = self._build_detail_content(self.current_test)
                self._content_cache[cache_key] = content
                self.query_one("#detail-content", Static).update(content)
            return 0

        # Find all match positions (line numbers in log)
        lines = self._raw_log.split("\n")
        for i, line in enumerate(lines):
            if self._search_query in line.lower():
                self._search_matches.append(i)

        # Rebuild content with highlights (don't cache highlighted version)
        if self.current_test:
            cache_key = self.current_test.tms_number
            if cache_key in self._content_cache:
                del self._content_cache[cache_key]
            content = self._build_detail_content(self.current_test, highlight=query)
            self.query_one("#detail-content", Static).update(content)

        if self._search_matches:
            self._current_match = 0
            self._scroll_to_match(0)

        return len(self._search_matches)

    def next_match(self) -> bool:
        """Go to next search match. Returns True if moved."""
        if not self._search_matches:
            return False
        self._current_match = (self._current_match + 1) % len(self._search_matches)
        self._scroll_to_match(self._current_match)
        return True

    def prev_match(self) -> bool:
        """Go to previous search match. Returns True if moved."""
        if not self._search_matches:
            return False
        self._current_match = (self._current_match - 1) % len(self._search_matches)
        self._scroll_to_match(self._current_match)
        return True

    def _scroll_to_match(self, match_idx: int):
        """Scroll to a specific match."""
        if 0 <= match_idx < len(self._search_matches) and self._total_lines > 0:
            log_line = self._search_matches[match_idx]
            # Estimate header takes about 15 lines before log content
            header_lines = 15
            target_line = header_lines + log_line
            ratio = target_line / self._total_lines
            target_y = ratio * self.virtual_size.height
            self.scroll_to(y=target_y, animate=False)

    def action_scroll_down(self) -> None:
        self.scroll_down(animate=False)

    def action_scroll_up(self) -> None:
        self.scroll_up(animate=False)

    def action_page_up(self) -> None:
        self.scroll_page_up(animate=False)

    def action_page_down(self) -> None:
        self.scroll_page_down(animate=False)

    def action_scroll_home(self) -> None:
        self.scroll_home(animate=False)

    def action_scroll_end(self) -> None:
        self.scroll_end(animate=False)

    def _build_detail_content(self, r: TestResult, highlight: str = "") -> Text:
        """Build rich Text content for test details."""
        text = Text()
        self._section_lines = {}
        line_count = 0

        text.append(r.tms_jira_format, style="bold cyan")
        text.append("\n\n")
        line_count += 2

        if r.jira_summary:
            text.append("Title: ", style="cyan")
            text.append(r.jira_summary)
            text.append("\n")
            line_count += 1

        text.append("Test: ", style="cyan")
        text.append(r.test_name)
        text.append("\n")
        line_count += 1

        text.append("Path: ", style="cyan")
        text.append(r.test_id)
        text.append("\n")
        line_count += 1

        text.append("Status: ", style="cyan")
        status_color = STATUS_COLORS.get(r.status, "white")
        text.append(r.status.value, style=status_color)
        text.append("\n")
        line_count += 1

        if r.duration:
            text.append("Duration: ", style="cyan")
            text.append(r.duration)
            text.append("\n")
            line_count += 1

        if r.failure_reason:
            text.append("\n")
            text.append("Failure Reason:\n", style="yellow bold")
            text.append(r.failure_reason)
            text.append("\n")
            line_count += r.failure_reason.count("\n") + 3

        if r.jira_test_steps:
            text.append("\n")
            text.append("Test Steps:\n", style="green bold")
            text.append(r.jira_test_steps)
            text.append("\n")
            line_count += r.jira_test_steps.count("\n") + 3

        if r.execution_log:
            text.append("\n")
            text.append("Execution Log:\n", style="magenta bold")
            line_count += 2
            log_start_line = line_count
            log_lines = self._append_colored_log(text, r.execution_log, highlight, log_start_line)
            line_count += log_lines

        self._total_lines = line_count
        return text

    def _append_colored_log(self, text: Text, log: str, highlight: str, start_line: int) -> int:
        """Append log content with colored log levels. Returns line count."""
        highlight_lower = highlight.lower() if highlight else ""

        # For very large logs, skip coloring to maintain performance
        skip_coloring = len(log) > 500000  # 500KB+

        lines = log.split("\n")
        for i, line in enumerate(lines):
            current_line = start_line + i

            # Check for section headers first
            for pattern, section_name in SECTION_PATTERNS:
                if pattern.search(line):
                    if section_name not in self._section_lines:
                        self._section_lines[section_name] = current_line
                    text.append(line + "\n", style="bold magenta reverse")
                    break
            else:
                # Not a section header
                if skip_coloring:
                    if highlight_lower and highlight_lower in line.lower():
                        self._append_highlighted_line(text, line, highlight_lower)
                    else:
                        text.append(line + "\n")
                elif highlight_lower and highlight_lower in line.lower():
                    self._append_highlighted_line(text, line, highlight_lower)
                else:
                    match = LOG_LEVEL_PATTERN.search(line)
                    if match:
                        level = match.group(1).upper()
                        color = LOG_COLORS.get(level, "white")
                        idx = match.start()
                        level_end = match.end()

                        if idx > 0:
                            text.append(line[:idx])
                        text.append(line[idx:level_end], style=color)
                        if level_end < len(line):
                            text.append(line[level_end:])
                        text.append("\n")
                    else:
                        text.append(line + "\n")

        return len(lines)

    def _append_highlighted_line(self, text: Text, line: str, highlight_lower: str) -> None:
        """Append a line with search term highlighted."""
        line_lower = line.lower()
        pos = 0
        while True:
            idx = line_lower.find(highlight_lower, pos)
            if idx == -1:
                text.append(line[pos:] + "\n")
                break
            if idx > pos:
                text.append(line[pos:idx])
            text.append(line[idx:idx + len(highlight_lower)], style="black on yellow")
            pos = idx + len(highlight_lower)


class ReportViewerApp(App):
    """Interactive viewer for test results."""

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 100%;
    }

    #left-panel {
        width: 40%;
        min-width: 30;
        border-right: solid $primary;
    }

    #left-panel.hidden {
        display: none;
    }

    #search-input {
        margin: 1;
        width: 100%;
    }

    #search-input:focus {
        border: tall $accent;
    }

    #status-line {
        padding: 0 1;
        background: $surface-darken-1;
        color: $text-muted;
        height: 1;
    }

    #test-list {
        height: 1fr;
        scrollbar-gutter: stable;
    }

    #test-list:focus {
        border: tall $accent;
    }

    #detail-panel {
        width: 60%;
        padding: 1 2;
    }

    #detail-panel.fullscreen {
        width: 100%;
    }

    #detail-panel:focus {
        border: tall $success;
    }

    #detail-content {
        width: 100%;
    }

    #log-search-container {
        layer: overlay;
        dock: bottom;
        height: auto;
        width: 50;
        margin-bottom: 1;
        margin-left: 2;
        background: $surface;
        border: round $accent;
        padding: 0 1;
        display: none;
    }

    #log-search-container.visible {
        display: block;
    }

    #log-search {
        width: 100%;
        border: none;
    }

    #loading-indicator {
        dock: bottom;
        height: 1;
        display: none;
        text-align: center;
    }

    #loading-indicator.visible {
        display: block;
    }

    TestListItem {
        padding: 0 1;
    }

    TestListItem:hover {
        background: $surface-lighten-1;
    }

    Toast {
        width: auto;
        max-width: 40;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("/", "focus_search", "Search"),
        Binding("a", "show_all", "All"),
        Binding("p", "show_passed", "Passed"),
        Binding("f", "show_failed", "Failed"),
        Binding("s", "show_skipped", "Skipped"),
        Binding("e", "show_error", "Errors"),
        Binding("space", "toggle_mark", "Mark", show=False),
        Binding("m", "show_marked", "Marked"),
        Binding("y", "copy_marked", "Copy"),
        Binding("c", "copy_current", "Copy TMS", show=False),
        Binding("o", "open_jira", "Jira"),
        Binding("enter", "focus_detail", "Logs"),
        Binding("tab", "switch_focus", "Switch", show=False),
        Binding("1", "jump_setup", "Setup", show=False),
        Binding("2", "jump_call", "Call", show=False),
        Binding("3", "jump_teardown", "Teardown", show=False),
    ]

    def __init__(self, results: list[TestResult], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.all_results = results
        self.filtered_results = results.copy()
        self.current_filter = "all"
        self.search_query = ""
        self.marked_tms: set[str] = set()
        self._search_timer: Timer | None = None
        self._status_counts = self._compute_status_counts()
        self._panel_hidden = False
        self._log_search_active = False

    def _compute_status_counts(self) -> dict:
        counts = {
            "total": len(self.all_results),
            "failed": 0,
            "passed": 0,
            "skipped": 0,
            "error": 0,
        }
        for r in self.all_results:
            if r.status == TestStatus.FAILED:
                counts["failed"] += 1
            elif r.status == TestStatus.ERROR:
                counts["error"] += 1
            elif r.status == TestStatus.PASSED:
                counts["passed"] += 1
            elif r.status == TestStatus.SKIPPED:
                counts["skipped"] += 1
        return counts

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(
                Vertical(
                    Input(placeholder="Search (TMS-xxx or test name)...", id="search-input"),
                    Static(self._get_status_line(), id="status-line"),
                    ListView(id="test-list"),
                    id="left-panel",
                ),
                TestDetailPanel(id="detail-panel"),
                id="main-container",
            ),
        )
        yield Container(
            Input(placeholder="Search log (Enter=next, Esc=close)...", id="log-search"),
            id="log-search-container",
        )
        yield Static("Loading...", id="loading-indicator")
        yield Footer()

    def on_mount(self):
        self._populate_list()
        self.query_one("#test-list", ListView).focus()

    def _populate_list(self):
        list_view = self.query_one("#test-list", ListView)
        list_view.clear()

        for result in self.filtered_results:
            item = TestListItem(result, marked=result.tms_number in self.marked_tms)
            list_view.append(item)

    def _get_status_line(self) -> str:
        shown = len(self.filtered_results)
        total = self._status_counts["total"]
        failed = self._status_counts["failed"]
        passed = self._status_counts["passed"]
        skipped = self._status_counts["skipped"]
        error = self._status_counts["error"]
        marked = len(self.marked_tms)

        parts = [f"{shown}/{total}"]
        if failed:
            parts.append(f"F:{failed}")
        if error:
            parts.append(f"E:{error}")
        if passed:
            parts.append(f"P:{passed}")
        if skipped:
            parts.append(f"S:{skipped}")
        if marked:
            parts.append(f"*:{marked}")
        parts.append(f"[{self.current_filter}]")

        return " " + " | ".join(parts)

    def _apply_filters(self):
        results = self.all_results

        if self.current_filter == "failed":
            results = [r for r in results if r.status == TestStatus.FAILED]
        elif self.current_filter == "passed":
            results = [r for r in results if r.status == TestStatus.PASSED]
        elif self.current_filter == "skipped":
            results = [r for r in results if r.status == TestStatus.SKIPPED]
        elif self.current_filter == "error":
            results = [r for r in results if r.status == TestStatus.ERROR]
        elif self.current_filter == "marked":
            results = [r for r in results if r.tms_number in self.marked_tms]

        if self.search_query:
            query = normalize_tms(self.search_query)
            results = [r for r in results
                      if query in normalize_tms(r.tms_number)
                      or query in r.test_name.lower()
                      or (r.jira_summary and query in r.jira_summary.lower())]

        self.filtered_results = results
        self._populate_list()
        self.query_one("#status-line", Static).update(self._get_status_line())

    def _show_panel(self):
        """Show the left panel."""
        if self._panel_hidden:
            left_panel = self.query_one("#left-panel")
            detail_panel = self.query_one("#detail-panel")
            left_panel.remove_class("hidden")
            detail_panel.remove_class("fullscreen")
            self._panel_hidden = False

    def _hide_panel(self):
        """Hide the left panel for fullscreen detail view."""
        if not self._panel_hidden:
            left_panel = self.query_one("#left-panel")
            detail_panel = self.query_one("#detail-panel")
            left_panel.add_class("hidden")
            detail_panel.add_class("fullscreen")
            self._panel_hidden = True

    def _show_loading(self):
        """Show loading indicator."""
        self.query_one("#loading-indicator").add_class("visible")

    def _hide_loading(self):
        """Hide loading indicator."""
        self.query_one("#loading-indicator").remove_class("visible")

    def _show_log_search(self):
        """Show log search input."""
        container = self.query_one("#log-search-container")
        log_search = self.query_one("#log-search", Input)
        container.add_class("visible")
        log_search.value = ""
        log_search.focus()
        self._log_search_active = True

    def _hide_log_search(self):
        """Hide log search input."""
        container = self.query_one("#log-search-container")
        log_search = self.query_one("#log-search", Input)
        container.remove_class("visible")
        log_search.value = ""
        self._log_search_active = False
        # Clear search highlights
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)
        detail_panel.search_log("")

    def on_key(self, event: events.Key) -> None:
        """Handle key events."""
        search_input = self.query_one("#search-input", Input)
        log_search = self.query_one("#log-search", Input)
        test_list = self.query_one("#test-list", ListView)
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)

        # Log search input handling
        if log_search.has_focus:
            if event.key == "escape":
                self._hide_log_search()
                detail_panel.focus()
                event.prevent_default()
                event.stop()
                return
            if event.key == "enter":
                if not detail_panel.next_match():
                    self.notify("No matches", timeout=1)
                event.prevent_default()
                event.stop()
                return
            return

        # When in search input, allow arrow keys to navigate list
        if search_input.has_focus:
            if event.key in ("down", "up"):
                test_list.focus()
                return
            if event.key == "enter":
                test_list.focus()
                event.prevent_default()
                event.stop()
                return

        # 'l' key - toggle panel visibility
        if event.key == "l" and not search_input.has_focus:
            if self._panel_hidden:
                self._show_panel()
                test_list.focus()
            else:
                self._hide_panel()
                detail_panel.focus()
            event.prevent_default()
            event.stop()
            return

        # 'n' for next match, 'N' for previous match
        if detail_panel.has_focus:
            if event.key == "n":
                detail_panel.next_match()
                event.prevent_default()
                event.stop()
                return
            if event.key == "N":
                detail_panel.prev_match()
                event.prevent_default()
                event.stop()
                return

        # Escape key handling
        if event.key == "escape":
            if self._log_search_active:
                self._hide_log_search()
                detail_panel.focus()
                event.prevent_default()
                event.stop()
            elif search_input.has_focus:
                if search_input.value:
                    search_input.value = ""
                    self.search_query = ""
                    self._apply_filters()
                test_list.focus()
                event.prevent_default()
                event.stop()
            elif detail_panel.has_focus:
                if self._panel_hidden:
                    self._show_panel()
                test_list.focus()
                event.prevent_default()
                event.stop()
            elif self._panel_hidden:
                self._show_panel()
                test_list.focus()
                event.prevent_default()
                event.stop()

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "search-input":
            self.search_query = event.value
            if self._search_timer is not None:
                self._search_timer.stop()
            self._search_timer = self.set_timer(0.2, self._debounced_search)

        elif event.input.id == "log-search":
            if self._search_timer is not None:
                self._search_timer.stop()
            self._search_timer = self.set_timer(0.3, lambda: self._do_log_search(event.value))

    def _do_log_search(self, query: str):
        """Perform log search."""
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)
        count = detail_panel.search_log(query)
        if query and count == 0:
            self.notify("No matches", timeout=1)
        elif count > 0:
            self.notify(f"{count} matches", timeout=1)

    def action_jump_setup(self):
        """Jump to setup section."""
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)
        if detail_panel.has_focus or self._panel_hidden:
            if not detail_panel.jump_to_section("setup"):
                self.notify("No setup", timeout=1)
        else:
            detail_panel.focus()
            if not detail_panel.jump_to_section("setup"):
                self.notify("No setup", timeout=1)

    def action_jump_call(self):
        """Jump to call section."""
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)
        if detail_panel.has_focus or self._panel_hidden:
            if not detail_panel.jump_to_section("call"):
                self.notify("No call", timeout=1)
        else:
            detail_panel.focus()
            if not detail_panel.jump_to_section("call"):
                self.notify("No call", timeout=1)

    def action_jump_teardown(self):
        """Jump to teardown section."""
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)
        if detail_panel.has_focus or self._panel_hidden:
            if not detail_panel.jump_to_section("teardown"):
                self.notify("No teardown", timeout=1)
        else:
            detail_panel.focus()
            if not detail_panel.jump_to_section("teardown"):
                self.notify("No teardown", timeout=1)

    def action_focus_detail(self):
        """Focus detail panel for scrolling (Enter key)."""
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)
        if detail_panel.current_test:
            detail_panel.focus()
            self.notify("/ search, 1/2/3 jump", timeout=1)

    def action_switch_focus(self):
        """Switch focus between list and detail panel (Tab key)."""
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)
        test_list = self.query_one("#test-list", ListView)

        if detail_panel.has_focus:
            if self._panel_hidden:
                self._show_panel()
            test_list.focus()
        else:
            if detail_panel.current_test:
                detail_panel.focus()

    def action_show_all(self):
        self.current_filter = "all"
        self._apply_filters()

    def action_show_passed(self):
        self.current_filter = "passed"
        self._apply_filters()

    def action_show_failed(self):
        self.current_filter = "failed"
        self._apply_filters()

    def action_show_skipped(self):
        self.current_filter = "skipped"
        self._apply_filters()

    def action_show_error(self):
        self.current_filter = "error"
        self._apply_filters()

    def action_show_marked(self):
        self.current_filter = "marked"
        self._apply_filters()

    def action_toggle_mark(self):
        list_view = self.query_one("#test-list", ListView)
        if list_view.highlighted_child and isinstance(list_view.highlighted_child, TestListItem):
            item = list_view.highlighted_child
            tms = item.result.tms_number
            if tms in self.marked_tms:
                self.marked_tms.remove(tms)
            else:
                self.marked_tms.add(tms)
            item.toggle_mark()
            self.query_one("#status-line", Static).update(self._get_status_line())
            if self.current_filter == "marked" and tms not in self.marked_tms:
                self._apply_filters()

    def action_copy_marked(self):
        if not self.marked_tms:
            self.notify("No marked", timeout=1)
            return

        marked_results = [r for r in self.all_results if r.tms_number in self.marked_tms]
        text = ", ".join(r.tms_number for r in marked_results)

        if copy_to_clipboard(text):
            self.notify(f"Copied {len(marked_results)}", timeout=1)
        else:
            self.notify("Copy failed", timeout=1)

    def action_copy_current(self):
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)
        if detail_panel.current_test:
            r = detail_panel.current_test
            text = f"{r.tms_number}: {r.test_name}"
            if r.failure_reason:
                text += f"\n{r.failure_reason}"
            if copy_to_clipboard(text):
                self.notify("Copied", timeout=1)
            else:
                self.notify("Copy failed", timeout=1)
        else:
            self.notify("No test", timeout=1)

    def action_open_jira(self):
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)
        if detail_panel.current_test:
            url = detail_panel.current_test.jira_url
            webbrowser.open(url)
            self.notify("Opening Jira", timeout=1)
        else:
            self.notify("No test", timeout=1)

    def action_focus_search(self):
        """Focus search - TMS search from list, log search from detail panel."""
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)

        # If detail panel has focus, open log search instead
        if detail_panel.has_focus and detail_panel.current_test:
            self._show_log_search()
            return

        # Otherwise focus TMS search
        if self._panel_hidden:
            self._show_panel()
        self.query_one("#search-input", Input).focus()

    def _debounced_search(self):
        self._apply_filters()

    def on_list_view_highlighted(self, event: ListView.Highlighted):
        if event.item and isinstance(event.item, TestListItem):
            detail_panel = self.query_one("#detail-panel", TestDetailPanel)
            result = event.item.result

            # Show loading for large logs
            if result.execution_log and len(result.execution_log) > 100000:
                self._show_loading()
                self.call_later(lambda: self._load_and_hide(result))
            else:
                detail_panel.show_test(result)

    def _load_and_hide(self, result: TestResult):
        """Load test and hide loading indicator."""
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)
        detail_panel.show_test(result)
        self._hide_loading()

    def on_list_view_selected(self, event: ListView.Selected):
        """Enter on list item focuses detail panel for scrolling."""
        if isinstance(event.item, TestListItem):
            detail_panel = self.query_one("#detail-panel", TestDetailPanel)
            detail_panel.show_test(event.item.result)
            detail_panel.focus()
            self.notify("/ search, 1/2/3 jump", timeout=1)
