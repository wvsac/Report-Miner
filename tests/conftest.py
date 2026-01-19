"""Pytest fixtures for report-parser tests."""

import json
import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile

from reportminer.models import TestResult, TestStatus


@pytest.fixture
def sample_test_result():
    """Create a sample TestResult for testing."""
    return TestResult(
        tms_number="TMS_12345",
        test_name="test_login_feature",
        test_id="tests/auth/test_login.py::test_login_feature",
        status=TestStatus.PASSED,
        failure_reason=None,
        duration="1.23s",
        timestamp="2024-01-15",
    )


@pytest.fixture
def failed_test_result():
    """Create a failed TestResult with failure reason."""
    return TestResult(
        tms_number="TMS_67890",
        test_name="test_checkout",
        test_id="tests/cart/test_checkout.py::test_checkout",
        status=TestStatus.FAILED,
        failure_reason="AssertionError: Expected [200] but got [500]",
        duration="2.45s",
        timestamp="2024-01-15",
    )


@pytest.fixture
def test_result_with_logs():
    """Create a TestResult with execution logs containing brackets."""
    return TestResult(
        tms_number="TMS_11111",
        test_name="test_api_call",
        test_id="tests/api/test_calls.py::test_api_call",
        status=TestStatus.FAILED,
        failure_reason="ConnectionError: [timeout]",
        duration="5.00s",
        timestamp="2024-01-15",
        execution_log="INFO [kafka-consumer-bin,partition=0,offset=-1,error=None}]\nDEBUG [api] Request sent [status=pending]",
    )


@pytest.fixture
def sample_html_report(tmp_path):
    """Create a sample HTML report file."""
    report_data = {
        "tests": {
            "tests/test_example.py::test_TMS_12345_login": [{
                "result": "passed",
                "duration": "1.23s",
                "time": "2024-01-15",
                "resultsTableRow": [
                    "<td>TMS_12345</td>",
                    "<td>passed</td>",
                    "<td>1.23s</td>",
                    "<td></td>"
                ]
            }],
            "tests/test_example.py::test_TMS_67890_checkout": [{
                "result": "failed",
                "duration": "2.45s",
                "time": "2024-01-15",
                "resultsTableRow": [
                    "<td>TMS_67890</td>",
                    "<td>failed</td>",
                    "<td>2.45s</td>",
                    "<td>AssertionError: Expected [200] but got [500]</td>"
                ]
            }],
            "tests/test_example.py::test_TMS_11111_search": [{
                "result": "failed",
                "duration": "0.5s",
                "time": "2024-01-15",
                "resultsTableRow": [
                    "<td>TMS_11111</td>",
                    "<td>failed</td>",
                    "<td>0.5s</td>",
                    "<td>TimeoutError: Connection timed out</td>"
                ]
            }]
        }
    }

    html_content = f'''<!DOCTYPE html>
<html>
<head><title>Test Report</title></head>
<body>
<div id="data-container" data-jsonblob='{json.dumps(report_data)}'>
</div>
</body>
</html>'''

    report_file = tmp_path / "test_report.html"
    report_file.write_text(html_content)
    return report_file


@pytest.fixture
def sample_html_report_with_logs(tmp_path):
    """Create a sample HTML report with execution logs."""
    report_data = {
        "tests": {
            "tests/test_example.py::test_TMS_99999_api[param1]": [{
                "result": "passed",
                "duration": "1.00s",
                "time": "2024-01-15",
                "log": "INFO [kafka-consumer-bin,partition=0,offset=-1,error=None}]\nDEBUG [api] Request sent",
                "resultsTableRow": [
                    "<td>TMS_99999</td>",
                    "<td>passed</td>",
                    "<td>1.00s</td>",
                    "<td></td>"
                ]
            }]
        }
    }

    html_content = f'''<!DOCTYPE html>
<html>
<head><title>Test Report</title></head>
<body>
<div id="data-container" data-jsonblob='{json.dumps(report_data)}'>
</div>
</body>
</html>'''

    report_file = tmp_path / "test_report_logs.html"
    report_file.write_text(html_content)
    return report_file


@pytest.fixture
def second_html_report(tmp_path):
    """Create a second HTML report for diff testing."""
    report_data = {
        "tests": {
            "tests/test_example.py::test_TMS_12345_login": [{
                "result": "passed",
                "duration": "1.23s",
                "time": "2024-01-16",
                "resultsTableRow": [
                    "<td>TMS_12345</td>",
                    "<td>passed</td>",
                    "<td>1.23s</td>",
                    "<td></td>"
                ]
            }],
            "tests/test_example.py::test_TMS_67890_checkout": [{
                "result": "passed",
                "duration": "2.45s",
                "time": "2024-01-16",
                "resultsTableRow": [
                    "<td>TMS_67890</td>",
                    "<td>passed</td>",
                    "<td>2.45s</td>",
                    "<td></td>"
                ]
            }],
            "tests/test_example.py::test_TMS_99999_new": [{
                "result": "failed",
                "duration": "0.1s",
                "time": "2024-01-16",
                "resultsTableRow": [
                    "<td>TMS_99999</td>",
                    "<td>failed</td>",
                    "<td>0.1s</td>",
                    "<td>NewError: Something failed</td>"
                ]
            }]
        }
    }

    html_content = f'''<!DOCTYPE html>
<html>
<head><title>Test Report 2</title></head>
<body>
<div id="data-container" data-jsonblob='{json.dumps(report_data)}'>
</div>
</body>
</html>'''

    report_file = tmp_path / "test_report2.html"
    report_file.write_text(html_content)
    return report_file
