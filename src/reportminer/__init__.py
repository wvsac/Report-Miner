"""Report Parser - CLI tool to parse pytest-html test reports."""

__version__ = "1.0.0"

from .models import TestResult, TestStatus
from .parser import parse_report, parse_reports

__all__ = [
    "__version__",
    "TestResult",
    "TestStatus",
    "parse_report",
    "parse_reports",
]
