"""Tests for report comparison."""

import pytest
from reportminer.compare import compare_reports, format_compare_result, CompareResult
from reportminer.models import TestResult, TestStatus


@pytest.fixture
def old_results():
    """Create old test results."""
    return [
        TestResult(
            tms_number="TMS_001",
            test_name="test_stable",
            test_id="test_stable",
            status=TestStatus.PASSED,
        ),
        TestResult(
            tms_number="TMS_002",
            test_name="test_was_failing",
            test_id="test_was_failing",
            status=TestStatus.FAILED,
            failure_reason="Old error",
        ),
        TestResult(
            tms_number="TMS_003",
            test_name="test_still_failing",
            test_id="test_still_failing",
            status=TestStatus.FAILED,
            failure_reason="Persistent error",
        ),
    ]


@pytest.fixture
def new_results():
    """Create new test results."""
    return [
        TestResult(
            tms_number="TMS_001",
            test_name="test_stable",
            test_id="test_stable",
            status=TestStatus.PASSED,
        ),
        TestResult(
            tms_number="TMS_002",
            test_name="test_was_failing",
            test_id="test_was_failing",
            status=TestStatus.PASSED,  # Fixed!
        ),
        TestResult(
            tms_number="TMS_003",
            test_name="test_still_failing",
            test_id="test_still_failing",
            status=TestStatus.FAILED,
            failure_reason="Persistent error",
        ),
        TestResult(
            tms_number="TMS_004",
            test_name="test_new_failure",
            test_id="test_new_failure",
            status=TestStatus.FAILED,
            failure_reason="New error",
        ),
    ]


class TestCompareReports:
    """Tests for report comparison logic."""

    def test_finds_fixed_tests(self, old_results, new_results):
        result = compare_reports(old_results, new_results)
        fixed_tms = [r.tms_number for r in result.fixed]
        assert "TMS_002" in fixed_tms

    def test_finds_new_failures(self, old_results, new_results):
        result = compare_reports(old_results, new_results)
        new_failure_tms = [r.tms_number for r in result.new_failures]
        assert "TMS_004" in new_failure_tms

    def test_finds_still_failing(self, old_results, new_results):
        result = compare_reports(old_results, new_results)
        still_failing_tms = [r.tms_number for r in result.still_failing]
        assert "TMS_003" in still_failing_tms

    def test_empty_results(self):
        result = compare_reports([], [])
        assert len(result.new_failures) == 0
        assert len(result.fixed) == 0
        assert len(result.still_failing) == 0


class TestFormatCompareResult:
    """Tests for compare result formatting."""

    def test_includes_new_failures_section(self, old_results, new_results):
        result = compare_reports(old_results, new_results)
        output = format_compare_result(result)
        assert "NEW FAILURES" in output

    def test_includes_fixed_section(self, old_results, new_results):
        result = compare_reports(old_results, new_results)
        output = format_compare_result(result)
        assert "FIXED" in output

    def test_includes_still_failing_section(self, old_results, new_results):
        result = compare_reports(old_results, new_results)
        output = format_compare_result(result)
        assert "STILL FAILING" in output

    def test_includes_summary(self, old_results, new_results):
        result = compare_reports(old_results, new_results)
        output = format_compare_result(result)
        assert "SUMMARY" in output

    def test_empty_result(self):
        result = CompareResult(
            new_failures=[],
            fixed=[],
            still_failing=[],
            new_errors=[],
            fixed_errors=[],
            still_erroring=[],
            new_passes=[],
        )
        output = format_compare_result(result)
        assert "No changes" in output or "SUMMARY" in output
