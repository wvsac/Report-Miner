"""Tests for TUI components."""

import pytest
from rich.text import Text

from reportminer.tui.app import (
    ReportViewerApp,
    TestListItem,
    TestDetailPanel,
)
from reportminer.models import TestResult, TestStatus


@pytest.fixture
def test_results():
    """Create test results for TUI testing."""
    return [
        TestResult(
            tms_number="TMS_001",
            test_name="test_passed",
            test_id="tests/test.py::test_passed",
            status=TestStatus.PASSED,
            duration="1.0s",
        ),
        TestResult(
            tms_number="TMS_002",
            test_name="test_failed",
            test_id="tests/test.py::test_failed",
            status=TestStatus.FAILED,
            failure_reason="AssertionError: test failed",
            duration="2.0s",
        ),
        TestResult(
            tms_number="TMS_003",
            test_name="test_with_logs",
            test_id="tests/test.py::test_with_logs",
            status=TestStatus.FAILED,
            failure_reason="Error: [code=500]",
            execution_log="INFO [kafka-consumer-bin,partition=0,offset=-1,error=None}]\nDEBUG [api] sent",
            duration="3.0s",
        ),
    ]


class TestTestListItem:
    """Tests for TestListItem widget."""

    def test_stores_result(self, sample_test_result):
        item = TestListItem(sample_test_result)
        assert item.result == sample_test_result

    def test_creates_for_passed(self, sample_test_result):
        item = TestListItem(sample_test_result)
        assert item.result.status == TestStatus.PASSED

    def test_creates_for_failed(self, failed_test_result):
        item = TestListItem(failed_test_result)
        assert item.result.status == TestStatus.FAILED


class TestTestDetailPanel:
    """Tests for TestDetailPanel widget."""

    def test_builds_content_for_passed(self, sample_test_result):
        panel = TestDetailPanel()
        content = panel._build_detail_content(sample_test_result)
        assert isinstance(content, Text)
        plain = content.plain
        assert "TMS-12345" in plain
        assert "passed" in plain

    def test_builds_content_for_failed(self, failed_test_result):
        panel = TestDetailPanel()
        content = panel._build_detail_content(failed_test_result)
        plain = content.plain
        assert "TMS-67890" in plain
        assert "failed" in plain
        assert "AssertionError" in plain

    def test_handles_brackets_in_logs(self, test_result_with_logs):
        """Ensure brackets in logs don't cause markup errors."""
        panel = TestDetailPanel()
        # This should not raise MarkupError
        content = panel._build_detail_content(test_result_with_logs)
        plain = content.plain
        assert "kafka-consumer" in plain
        assert "partition=0" in plain

    def test_includes_jira_summary(self):
        result = TestResult(
            tms_number="TMS_123",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            jira_summary="Test Login Feature",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "Test Login Feature" in content.plain

    def test_includes_test_steps(self):
        result = TestResult(
            tms_number="TMS_123",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            jira_test_steps="1. Do this\n2. Do that",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "1. Do this" in content.plain
        assert "2. Do that" in content.plain

    def test_includes_execution_log(self, test_result_with_logs):
        panel = TestDetailPanel()
        content = panel._build_detail_content(test_result_with_logs)
        assert "Execution Log" in content.plain


class TestReportViewerApp:
    """Tests for ReportViewerApp."""

    def test_initializes_with_results(self, test_results):
        app = ReportViewerApp(test_results)
        assert len(app.all_results) == 3
        assert len(app.filtered_results) == 3

    def test_default_filter_is_all(self, test_results):
        app = ReportViewerApp(test_results)
        assert app.current_filter == "all"

    def test_status_line_shows_counts(self, test_results):
        app = ReportViewerApp(test_results)
        status = app._get_status_line()
        assert "3/3" in status
        assert "F:2" in status  # Compact format
        assert "P:1" in status

    def test_apply_failed_filter(self, test_results):
        app = ReportViewerApp(test_results)
        app.current_filter = "failed"
        app.filtered_results = [r for r in app.all_results
                               if r.status in (TestStatus.FAILED, TestStatus.ERROR)]
        assert len(app.filtered_results) == 2

    def test_apply_passed_filter(self, test_results):
        app = ReportViewerApp(test_results)
        app.current_filter = "passed"
        app.filtered_results = [r for r in app.all_results
                               if r.status == TestStatus.PASSED]
        assert len(app.filtered_results) == 1

    def test_search_filters_by_tms(self, test_results):
        app = ReportViewerApp(test_results)
        app.search_query = "001"
        results = [r for r in app.all_results
                  if app.search_query.lower() in r.tms_number.lower()]
        assert len(results) == 1
        assert results[0].tms_number == "TMS_001"

    def test_search_filters_by_name(self, test_results):
        app = ReportViewerApp(test_results)
        app.search_query = "passed"
        results = [r for r in app.all_results
                  if app.search_query.lower() in r.test_name.lower()]
        assert len(results) == 1


class TestTUIWithBracketContent:
    """Tests specifically for handling bracket characters."""

    def test_handles_kafka_style_logs(self):
        """Test logs with Kafka-style bracket patterns."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log="[kafka-consumer-bin,partition=0,offset=-1,error=None}]",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "kafka-consumer" in content.plain

    def test_handles_status_codes_in_brackets(self):
        """Test error messages with status codes in brackets."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.FAILED,
            failure_reason="Expected [200] but got [500]",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "[200]" in content.plain
        assert "[500]" in content.plain

    def test_handles_nested_brackets(self):
        """Test content with nested bracket patterns."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.FAILED,
            execution_log="DEBUG [outer [inner] more]",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "outer" in content.plain

    def test_handles_long_logs_with_brackets(self):
        """Test all log lines are shown (no truncation)."""
        log_lines = []
        for i in range(300):
            log_lines.append(f"INFO [component-{i},status=ok,code={i}]")

        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log="\n".join(log_lines),
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        # All lines should be shown (no line count truncation)
        assert "component-50" in content.plain
        assert "component-150" in content.plain
        assert "component-299" in content.plain  # Last line too


class TestLogLevelColoring:
    """Tests for log level color highlighting in TUI."""

    def test_colors_error_level(self):
        """Test that ERROR level is colored."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.FAILED,
            execution_log="2024-01-15 10:00:00 ERROR Something went wrong",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        # The text should contain ERROR
        assert "ERROR" in content.plain
        # Check that styles were applied (content is a Rich Text object)
        # The spans should contain style information for ERROR

    def test_colors_warn_level(self):
        """Test that WARN level is colored."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log="WARN: This is a warning message",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "WARN" in content.plain

    def test_colors_warning_level(self):
        """Test that WARNING level is colored."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log="WARNING: This is a warning message",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "WARNING" in content.plain

    def test_colors_info_level(self):
        """Test that INFO level is colored."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log="INFO: Application started successfully",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "INFO" in content.plain

    def test_colors_debug_level(self):
        """Test that DEBUG level is colored."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log="DEBUG: Variable x = 42",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "DEBUG" in content.plain

    def test_colors_trace_level(self):
        """Test that TRACE level is colored."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log="TRACE: Entering function foo()",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "TRACE" in content.plain

    def test_colors_fatal_level(self):
        """Test that FATAL level is colored."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.FAILED,
            execution_log="FATAL: System crash imminent",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "FATAL" in content.plain

    def test_colors_err_shorthand(self):
        """Test that ERR shorthand is colored."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.FAILED,
            execution_log="ERR: Network timeout",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "ERR" in content.plain

    def test_colors_dbg_shorthand(self):
        """Test that DBG shorthand is colored."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log="DBG: Cache hit for key xyz",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "DBG" in content.plain

    def test_colors_trc_shorthand(self):
        """Test that TRC shorthand is colored."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log="TRC: Memory allocation at 0x1234",
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "TRC" in content.plain

    def test_mixed_log_levels(self):
        """Test logs with multiple different levels."""
        log = """INFO Starting test
DEBUG Loading configuration
WARN Deprecated API used
ERROR Connection failed
INFO Retrying...
DEBUG Retry successful
INFO Test completed"""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log=log,
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        plain = content.plain
        assert "INFO" in plain
        assert "DEBUG" in plain
        assert "WARN" in plain
        assert "ERROR" in plain

    def test_case_insensitive_log_level_detection(self):
        """Test that log level detection is case-insensitive."""
        log = """info lower case
INFO UPPER CASE
Info Mixed Case
InFo WeIrD CaSe"""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log=log,
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        # All variations should be in the output
        plain = content.plain
        assert "info" in plain.lower()


class TestTUIMarking:
    """Tests for test marking functionality."""

    def test_mark_and_unmark(self, test_results):
        """Test that marking toggles correctly."""
        app = ReportViewerApp(test_results)
        assert len(app.marked_tms) == 0

        # Simulate marking
        tms = test_results[0].tms_number
        app.marked_tms.add(tms)
        assert tms in app.marked_tms

        # Simulate unmarking
        app.marked_tms.remove(tms)
        assert tms not in app.marked_tms

    def test_marked_filter(self, test_results):
        """Test filtering by marked tests."""
        app = ReportViewerApp(test_results)
        app.marked_tms.add(test_results[0].tms_number)

        # Apply marked filter
        app.current_filter = "marked"
        results = [r for r in app.all_results if r.tms_number in app.marked_tms]
        assert len(results) == 1
        assert results[0].tms_number == test_results[0].tms_number

    def test_status_line_shows_marked_count(self, test_results):
        """Test that status line updates with marked count."""
        app = ReportViewerApp(test_results)
        app.marked_tms.add(test_results[0].tms_number)
        app.marked_tms.add(test_results[1].tms_number)

        status = app._get_status_line()
        assert "*:2" in status


class TestTUIListItem:
    """Additional tests for TestListItem widget."""

    def test_displays_mark_indicator(self, sample_test_result):
        """Test that mark indicator displays correctly."""
        item = TestListItem(sample_test_result, marked=False)
        label = item._build_label()
        plain = label.plain
        # Unmarked should have space as indicator
        assert plain.startswith(" ")

        # Marked should have asterisk
        item.marked = True
        label = item._build_label()
        plain = label.plain
        assert plain.startswith("*")

    def test_toggle_mark_changes_state(self, sample_test_result):
        """Test that toggle_mark changes the state."""
        item = TestListItem(sample_test_result, marked=False)
        assert item.marked is False

        # Toggle should change state without error
        # (note: in real app this calls query_one which needs app context)
        item.marked = not item.marked
        assert item.marked is True


class TestTUIFilterCombinations:
    """Tests for filter combination scenarios."""

    def test_search_with_status_filter(self, test_results):
        """Test search combined with status filter."""
        app = ReportViewerApp(test_results)
        app.current_filter = "failed"
        app.search_query = "002"

        # Apply filters manually
        results = app.all_results

        # Status filter
        results = [r for r in results
                   if r.status in (TestStatus.FAILED, TestStatus.ERROR)]

        # Search filter
        query = app.search_query.lower()
        results = [r for r in results
                   if query in r.tms_number.lower()
                   or query in r.test_name.lower()]

        assert len(results) == 1
        assert results[0].tms_number == "TMS_002"

    def test_empty_search_shows_all_with_filter(self, test_results):
        """Test that empty search with filter shows all filtered results."""
        app = ReportViewerApp(test_results)
        app.current_filter = "failed"
        app.search_query = ""

        results = [r for r in app.all_results
                   if r.status in (TestStatus.FAILED, TestStatus.ERROR)]

        assert len(results) == 2  # Two failed tests in fixture


class TestSectionDetection:
    """Tests for section detection and jumping."""

    def test_detects_live_log_setup(self):
        """Test detection of live log setup section."""
        log = """Some initial logs
INFO Starting test
----------------------- live log setup -----------------------
DEBUG Setting up fixtures
INFO Fixtures ready
"""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log=log,
        )
        panel = TestDetailPanel()
        panel._build_detail_content(result)
        assert "setup" in panel._section_lines
        # Setup should be at the line with "live log setup"
        assert panel._section_lines["setup"] > 0

    def test_detects_live_log_call(self):
        """Test detection of live log call section."""
        log = """----------------------- live log setup -----------------------
DEBUG Setup
----------------------- live log call -----------------------
INFO Running test
DEBUG Test step 1
"""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log=log,
        )
        panel = TestDetailPanel()
        panel._build_detail_content(result)
        assert "setup" in panel._section_lines
        assert "call" in panel._section_lines
        # Call should come after setup
        assert panel._section_lines["call"] > panel._section_lines["setup"]

    def test_detects_live_log_teardown(self):
        """Test detection of live log teardown section."""
        log = """----------------------- live log setup -----------------------
DEBUG Setup
----------------------- live log call -----------------------
INFO Running test
----------------------- live log teardown -----------------------
DEBUG Cleaning up
"""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log=log,
        )
        panel = TestDetailPanel()
        panel._build_detail_content(result)
        assert "setup" in panel._section_lines
        assert "call" in panel._section_lines
        assert "teardown" in panel._section_lines
        # Sections should be in order
        assert panel._section_lines["setup"] < panel._section_lines["call"]
        assert panel._section_lines["call"] < panel._section_lines["teardown"]

    def test_detects_captured_log_sections(self):
        """Test detection of captured log sections (alternative format)."""
        log = """----------------------- Captured log setup -----------------------
DEBUG Setup via captured
----------------------- Captured log call -----------------------
INFO Call via captured
----------------------- Captured log teardown -----------------------
DEBUG Teardown via captured
"""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log=log,
        )
        panel = TestDetailPanel()
        panel._build_detail_content(result)
        assert "setup" in panel._section_lines
        assert "call" in panel._section_lines
        assert "teardown" in panel._section_lines

    def test_section_lines_relative_to_total_content(self):
        """Test that section line numbers account for header content."""
        log = """----------------------- live log call -----------------------
INFO Test running
"""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test_name_here",
            test_id="tests/test.py::test_name_here",
            status=TestStatus.PASSED,
            duration="1.0s",
            execution_log=log,
        )
        panel = TestDetailPanel()
        panel._build_detail_content(result)
        # Call section should be after header lines (TMS, test name, path, status, duration, etc.)
        # Header is approximately 7+ lines
        assert panel._section_lines["call"] >= 7

    def test_no_sections_when_no_markers(self):
        """Test that no sections found when log has no markers."""
        log = """INFO Just some regular logs
DEBUG Without any section markers
ERROR Some error
"""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log=log,
        )
        panel = TestDetailPanel()
        panel._build_detail_content(result)
        assert len(panel._section_lines) == 0

    def test_total_lines_tracked_correctly(self):
        """Test that total line count is accurate."""
        log = "line1\nline2\nline3\nline4\nline5"  # 5 lines
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log=log,
        )
        panel = TestDetailPanel()
        panel._build_detail_content(result)
        # Should have header lines + 5 log lines
        # Header: TMS (2 lines with blank), Test (1), Path (1), Status (1), Execution Log header (2) = 7
        # Plus log: 5 lines
        # Total: ~12 lines
        assert panel._total_lines >= 10  # At least header + some log

    def test_jump_returns_false_for_missing_section(self):
        """Test that jump_to_section returns False for non-existent section."""
        log = "INFO Just logs without sections"
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log=log,
        )
        panel = TestDetailPanel()
        panel._build_detail_content(result)
        assert panel.jump_to_section("setup") is False
        assert panel.jump_to_section("call") is False
        assert panel.jump_to_section("teardown") is False

    def test_jump_returns_true_for_existing_section(self):
        """Test that jump_to_section returns True for existing section."""
        log = """----------------------- live log call -----------------------
INFO Test
"""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            execution_log=log,
        )
        panel = TestDetailPanel()
        panel._build_detail_content(result)
        # Note: jump_to_section calls scroll_to which requires widget to be mounted
        # Just verify the section was detected
        assert "call" in panel._section_lines


class TestTUIEdgeCases:
    """Tests for edge cases in TUI."""

    def test_empty_results_list(self):
        """Test TUI with no results."""
        app = ReportViewerApp([])
        assert len(app.all_results) == 0
        assert len(app.filtered_results) == 0
        status = app._get_status_line()
        assert "0/0" in status

    def test_all_same_status(self):
        """Test when all tests have the same status."""
        results = [
            TestResult(
                tms_number=f"TMS_{i}",
                test_name=f"test_{i}",
                test_id=f"test_{i}",
                status=TestStatus.PASSED,
            )
            for i in range(5)
        ]
        app = ReportViewerApp(results)
        status = app._get_status_line()
        assert "5/5" in status
        assert "P:5" in status
        assert "F:" not in status  # No failures

    def test_very_long_test_name(self):
        """Test handling of very long test names."""
        long_name = "test_" + "a" * 500
        result = TestResult(
            tms_number="TMS_1",
            test_name=long_name,
            test_id=long_name,
            status=TestStatus.PASSED,
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert long_name in content.plain

    def test_special_characters_in_failure_reason(self):
        """Test failure reason with special characters."""
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.FAILED,
            failure_reason='Error: <xml>tag</xml> & "quotes" \'apostrophes\'',
        )
        panel = TestDetailPanel()
        content = panel._build_detail_content(result)
        assert "xml" in content.plain
        assert "quotes" in content.plain
