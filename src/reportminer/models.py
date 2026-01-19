"""Data models for test results."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TestStatus(Enum):
    """Possible test result statuses."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    XFAILED = "xfailed"
    XPASSED = "xpassed"
    RERUN = "rerun"

    @classmethod
    def from_string(cls, value: str) -> "TestStatus":
        """Create status from string, case-insensitive."""
        normalized = value.lower().strip()
        for status in cls:
            if status.value == normalized:
                return status
        raise ValueError(f"Unknown test status: {value}")


@dataclass
class TestResult:
    """Single test result with all its data."""
    tms_number: str
    test_name: str
    test_id: str
    status: TestStatus
    failure_reason: Optional[str] = None
    duration: Optional[str] = None
    timestamp: Optional[str] = None
    # Jira integration fields
    jira_summary: Optional[str] = None
    jira_test_steps: Optional[str] = None
    # Execution log from pytest output
    execution_log: Optional[str] = None

    @property
    def tms_jira_format(self) -> str:
        """Convert TMS_123 to TMS-123 for Jira URLs."""
        return self.tms_number.replace("_", "-")

    @property
    def jira_url(self) -> str:
        """Full Jira URL for this test."""
        from .config import JIRA_BASE_URL
        return f"{JIRA_BASE_URL.rstrip('/')}/browse/{self.tms_jira_format}"

    @property
    def test_name_readable(self) -> str:
        """Make test name human readable."""
        name = self.test_name
        if name.startswith("test_"):
            name = name[5:]
        name = name.replace("_", " ")
        return name.capitalize()


@dataclass
class JiraIssueData:
    """Data fetched from Jira API."""
    key: str
    summary: str
    test_steps: Optional[str] = None


@dataclass
class ReportSummary:
    """Summary stats for parsed reports."""
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    source_files: list[str]
