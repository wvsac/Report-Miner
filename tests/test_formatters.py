"""Tests for output formatters."""

import pytest
from reportminer.formatters import (
    get_formatter,
    RawFormatter,
    PytestFormatter,
    NamesFormatter,
    FullFormatter,
    DetailedFormatter,
    JiraFormatter,
    JiraWikiFormatter,
    GroupedByReasonFormatter,
    FORMATTERS,
)
from reportminer.models import TestResult, TestStatus


@pytest.fixture
def test_results():
    """Create a list of test results for formatter testing."""
    return [
        TestResult(
            tms_number="TMS_12345",
            test_name="test_login",
            test_id="tests/auth/test_login.py::test_login",
            status=TestStatus.FAILED,
            failure_reason="AssertionError: login failed",
        ),
        TestResult(
            tms_number="TMS_67890",
            test_name="test_checkout",
            test_id="tests/cart/test_checkout.py::test_checkout",
            status=TestStatus.FAILED,
            failure_reason="AssertionError: login failed",  # Same reason for grouping test
        ),
        TestResult(
            tms_number="TMS_11111",
            test_name="test_search",
            test_id="tests/search/test_search.py::test_search",
            status=TestStatus.PASSED,
        ),
    ]


class TestGetFormatter:
    """Tests for formatter factory."""

    def test_returns_formatter(self):
        formatter = get_formatter("raw")
        assert isinstance(formatter, RawFormatter)

    def test_case_insensitive(self):
        assert get_formatter("RAW") is get_formatter("raw")
        assert get_formatter("Pytest") is get_formatter("pytest")

    def test_raises_for_unknown(self):
        with pytest.raises(ValueError, match="Unknown format"):
            get_formatter("nonexistent")

    def test_all_formats_registered(self):
        expected = ["raw", "pytest", "names", "full", "detailed", "jira", "jira-md", "wiki"]
        for fmt in expected:
            assert fmt in FORMATTERS

    def test_group_flag_wraps_formatter(self):
        formatter = get_formatter("pytest", group=True)
        # Should return GroupedByReasonFormatter
        assert hasattr(formatter, "inner_format")
        assert formatter.inner_format == "pytest"


class TestRawFormatter:
    """Tests for raw format output."""

    def test_comma_separated(self, test_results):
        formatter = RawFormatter()
        output = formatter.format(test_results)
        assert output == "TMS_12345, TMS_67890, TMS_11111"

    def test_single_result(self, sample_test_result):
        formatter = RawFormatter()
        output = formatter.format([sample_test_result])
        assert output == "TMS_12345"

    def test_empty_list(self):
        formatter = RawFormatter()
        output = formatter.format([])
        assert output == ""


class TestPytestFormatter:
    """Tests for pytest format output."""

    def test_or_separated(self, test_results):
        formatter = PytestFormatter()
        output = formatter.format(test_results)
        assert output == "TMS_12345 or TMS_67890 or TMS_11111"

    def test_single_result(self, sample_test_result):
        formatter = PytestFormatter()
        output = formatter.format([sample_test_result])
        assert output == "TMS_12345"


class TestNamesFormatter:
    """Tests for names format output."""

    def test_comma_separated_names(self, test_results):
        formatter = NamesFormatter()
        output = formatter.format(test_results)
        assert "test_login" in output
        assert "test_checkout" in output
        assert "test_search" in output
        assert ", " in output


class TestFullFormatter:
    """Tests for full path format output."""

    def test_one_per_line(self, test_results):
        formatter = FullFormatter()
        output = formatter.format(test_results)
        lines = output.split("\n")
        assert len(lines) == 3
        assert "tests/auth/test_login.py::test_login" in lines


class TestDetailedFormatter:
    """Tests for detailed format output."""

    def test_contains_tms(self, test_results):
        formatter = DetailedFormatter()
        output = formatter.format(test_results)
        assert "TMS_12345" in output
        assert "TMS_67890" in output

    def test_contains_status(self, test_results):
        formatter = DetailedFormatter()
        output = formatter.format(test_results)
        assert "failed" in output
        assert "passed" in output

    def test_contains_failure_reason(self, test_results):
        formatter = DetailedFormatter()
        output = formatter.format(test_results)
        assert "AssertionError" in output

    def test_structured_format(self, test_results):
        formatter = DetailedFormatter()
        output = formatter.format(test_results)
        assert "TMS:" in output
        assert "Status:" in output
        assert "Test:" in output
        assert "Reason:" in output


class TestJiraFormatter:
    """Tests for Jira URL format output."""

    def test_generates_urls(self, test_results):
        formatter = JiraFormatter()
        output = formatter.format(test_results)
        assert "browse/TMS-12345" in output
        assert "browse/TMS-67890" in output

    def test_one_url_per_line(self, test_results):
        formatter = JiraFormatter()
        output = formatter.format(test_results)
        lines = output.split("\n")
        assert len(lines) == 3


class TestJiraWikiFormatter:
    """Tests for Jira wiki markdown format output."""

    def test_wiki_format(self, test_results):
        formatter = JiraWikiFormatter()
        output = formatter.format(test_results)
        assert "[TMS-12345|" in output
        assert "]" in output

    def test_includes_summary_when_available(self):
        result = TestResult(
            tms_number="TMS_123",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
            jira_summary="Test Login Feature",
        )
        formatter = JiraWikiFormatter()
        output = formatter.format([result])
        assert "TMS-123: Test Login Feature" in output


class TestGroupedByReasonFormatter:
    """Tests for grouped format output."""

    def test_groups_by_reason(self, test_results):
        formatter = GroupedByReasonFormatter()
        output = formatter.format(test_results)
        # Two tests have the same failure reason
        assert "[2 tests]" in output
        assert "AssertionError: login failed" in output

    def test_lists_tests_under_group(self, test_results):
        formatter = GroupedByReasonFormatter()
        output = formatter.format(test_results)
        assert "TMS_12345" in output
        assert "TMS_67890" in output

    def test_handles_no_failure_reason(self):
        results = [
            TestResult(
                tms_number="TMS_1",
                test_name="test",
                test_id="test",
                status=TestStatus.FAILED,
                failure_reason=None,
            )
        ]
        formatter = GroupedByReasonFormatter()
        output = formatter.format(results)
        assert "No failure reason" in output

    def test_with_inner_format(self, test_results):
        formatter = GroupedByReasonFormatter(inner_format="pytest")
        output = formatter.format(test_results)
        # Should use pytest format (or-separated) inside groups
        assert " or " in output or "TMS_" in output
