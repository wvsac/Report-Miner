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

    def compose(self) -> ComposeResult:
        yield Static("Select a test to view details", id="detail-content")

    def show_test(self, result: TestResult):
        """Display details for a test result."""
        self.current_test = result

        cache_key = result.tms_number
        if cache_key in self._content_cache:
            content = self._content_cache[cache_key]
        else:
            content = self._build_detail_content(result)
            if len(self._content_cache) < 100:
                self._content_cache[cache_key] = content

        self.query_one("#detail-content", Static).update(content)
        self.scroll_home(animate=False)

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

    def _build_detail_content(self, r: TestResult) -> Text:
        """Build rich Text content for test details."""
        text = Text()

        text.append(r.tms_jira_format, style="bold cyan")
        text.append("\n\n")

        if r.jira_summary:
            text.append("Title: ", style="cyan")
            text.append(r.jira_summary)
            text.append("\n")

        text.append("Test: ", style="cyan")
        text.append(r.test_name)
        text.append("\n")

        text.append("Path: ", style="cyan")
        text.append(r.test_id)
        text.append("\n")

        text.append("Status: ", style="cyan")
        status_color = STATUS_COLORS.get(r.status, "white")
        text.append(r.status.value, style=status_color)
        text.append("\n")

        if r.duration:
            text.append("Duration: ", style="cyan")
            text.append(r.duration)
            text.append("\n")

        if r.failure_reason:
            text.append("\n")
            text.append("Failure Reason:\n", style="yellow bold")
            text.append(r.failure_reason)
            text.append("\n")

        if r.jira_test_steps:
            text.append("\n")
            text.append("Test Steps:\n", style="green bold")
            text.append(r.jira_test_steps)
            text.append("\n")

        if r.execution_log:
            text.append("\n")
            text.append("Execution Log:\n", style="magenta bold")
            self._append_colored_log(text, r.execution_log)

        return text

    def _append_colored_log(self, text: Text, log: str) -> None:
        """Append log content with colored log levels - show full logs."""
        # For very large logs, skip coloring to maintain performance
        if len(log) > 500000:  # 500KB+
            text.append(log)
            return

        lines = log.split("\n")
        for line in lines:
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

    TestListItem {
        padding: 0 1;
    }

    TestListItem:hover {
        background: $surface-lighten-1;
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
        Binding("enter", "focus_detail", "View Logs"),
        Binding("tab", "switch_focus", "Switch", show=False),
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
            # Normalize query - treat TMS-xxx and TMS_xxx as equivalent
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

    def on_key(self, event: events.Key) -> None:
        """Handle key events."""
        search_input = self.query_one("#search-input", Input)
        test_list = self.query_one("#test-list", ListView)
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)

        # When in search input, allow arrow keys to navigate list
        if search_input.has_focus:
            if event.key in ("down", "up"):
                # Move focus to list and let it handle navigation
                test_list.focus()
                # Don't prevent default - let the list handle the key
                return
            if event.key == "enter":
                # Enter in search focuses list
                test_list.focus()
                event.prevent_default()
                event.stop()
                return

        # 'l' key - toggle panel visibility (works everywhere except search)
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

        # Escape key handling
        if event.key == "escape":
            if search_input.has_focus:
                # Clear search and go to list
                if search_input.value:
                    search_input.value = ""
                    self.search_query = ""
                    self._apply_filters()
                test_list.focus()
                event.prevent_default()
                event.stop()
            elif detail_panel.has_focus:
                # From detail panel: show panel if hidden, then go to list
                if self._panel_hidden:
                    self._show_panel()
                test_list.focus()
                event.prevent_default()
                event.stop()
            elif self._panel_hidden:
                # Panel hidden but list somehow focused - show panel
                self._show_panel()
                test_list.focus()
                event.prevent_default()
                event.stop()
            # Otherwise quit (default)

    def action_focus_detail(self):
        """Focus detail panel for scrolling (Enter key)."""
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)
        if detail_panel.current_test:
            detail_panel.focus()
            self.notify("↑↓/j/k scroll, PgUp/PgDn fast, Esc back", timeout=2)

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
            self.notify("No tests marked. Use Space to mark.", severity="warning")
            return

        marked_results = [r for r in self.all_results if r.tms_number in self.marked_tms]
        text = ", ".join(r.tms_number for r in marked_results)

        if copy_to_clipboard(text):
            self.notify(f"Copied {len(marked_results)} TMS numbers")
        else:
            self.notify("Clipboard copy failed", severity="error")

    def action_copy_current(self):
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)
        if detail_panel.current_test:
            r = detail_panel.current_test
            text = f"{r.tms_number}: {r.test_name}"
            if r.failure_reason:
                text += f"\n{r.failure_reason}"
            if copy_to_clipboard(text):
                self.notify("Copied to clipboard")
            else:
                self.notify("Clipboard copy failed", severity="error")
        else:
            self.notify("No test selected", severity="warning")

    def action_open_jira(self):
        detail_panel = self.query_one("#detail-panel", TestDetailPanel)
        if detail_panel.current_test:
            url = detail_panel.current_test.jira_url
            webbrowser.open(url)
            self.notify(f"Opening {detail_panel.current_test.tms_jira_format}")
        else:
            self.notify("No test selected", severity="warning")

    def action_focus_search(self):
        if self._panel_hidden:
            self._show_panel()
        self.query_one("#search-input", Input).focus()

    def _debounced_search(self):
        self._apply_filters()

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "search-input":
            self.search_query = event.value

            if self._search_timer is not None:
                self._search_timer.stop()

            self._search_timer = self.set_timer(0.2, self._debounced_search)

    def on_list_view_highlighted(self, event: ListView.Highlighted):
        if event.item and isinstance(event.item, TestListItem):
            detail_panel = self.query_one("#detail-panel", TestDetailPanel)
            detail_panel.show_test(event.item.result)

    def on_list_view_selected(self, event: ListView.Selected):
        """Enter on list item focuses detail panel for scrolling."""
        if isinstance(event.item, TestListItem):
            detail_panel = self.query_one("#detail-panel", TestDetailPanel)
            detail_panel.show_test(event.item.result)
            detail_panel.focus()
            self.notify("↑↓/j/k scroll, PgUp/PgDn fast, Esc back", timeout=2)
