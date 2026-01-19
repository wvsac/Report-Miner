"""Tests for data models."""

import pytest
from reportminer.models import TestResult, TestStatus, JiraIssueData


class TestTestStatus:
    """Tests for TestStatus enum."""

    def test_from_string_passed(self):
        assert TestStatus.from_string("passed") == TestStatus.PASSED

    def test_from_string_failed(self):
        assert TestStatus.from_string("failed") == TestStatus.FAILED

    def test_from_string_skipped(self):
        assert TestStatus.from_string("skipped") == TestStatus.SKIPPED

    def test_from_string_error(self):
        assert TestStatus.from_string("error") == TestStatus.ERROR

    def test_from_string_case_insensitive(self):
        assert TestStatus.from_string("PASSED") == TestStatus.PASSED
        assert TestStatus.from_string("Failed") == TestStatus.FAILED

    def test_from_string_with_whitespace(self):
        assert TestStatus.from_string("  passed  ") == TestStatus.PASSED

    def test_from_string_invalid(self):
        with pytest.raises(ValueError, match="Unknown test status"):
            TestStatus.from_string("invalid")


class TestTestResult:
    """Tests for TestResult dataclass."""

    def test_tms_jira_format(self, sample_test_result):
        assert sample_test_result.tms_jira_format == "TMS-12345"

    def test_tms_jira_format_conversion(self):
        result = TestResult(
            tms_number="TMS_99999",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
        )
        assert result.tms_jira_format == "TMS-99999"

    def test_jira_url(self, sample_test_result, monkeypatch):
        monkeypatch.setattr("reportminer.config.JIRA_BASE_URL", "https://jira.example.com")

        url = sample_test_result.jira_url
        assert "TMS-12345" in url
        assert url.startswith("https://")

    def test_test_name_readable(self, sample_test_result):
        readable = sample_test_result.test_name_readable
        assert readable == "Login feature"

    def test_test_name_readable_strips_test_prefix(self):
        result = TestResult(
            tms_number="TMS_1",
            test_name="test_some_feature",
            test_id="test",
            status=TestStatus.PASSED,
        )
        assert result.test_name_readable == "Some feature"

    def test_optional_fields_default_none(self):
        result = TestResult(
            tms_number="TMS_1",
            test_name="test",
            test_id="test",
            status=TestStatus.PASSED,
        )
        assert result.failure_reason is None
        assert result.duration is None
        assert result.timestamp is None
        assert result.jira_summary is None
        assert result.jira_test_steps is None
        assert result.execution_log is None


class TestJiraIssueData:
    """Tests for JiraIssueData dataclass."""

    def test_creation(self):
        data = JiraIssueData(
            key="TMS-12345",
            summary="Test login feature",
            test_steps="1. Open login page\n2. Enter credentials",
        )
        assert data.key == "TMS-12345"
        assert data.summary == "Test login feature"
        assert data.test_steps == "1. Open login page\n2. Enter credentials"

    def test_optional_test_steps(self):
        data = JiraIssueData(key="TMS-1", summary="Test")
        assert data.test_steps is None
