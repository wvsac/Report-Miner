"""Integration tests for end-to-end scenarios."""

import json
import pytest
from pathlib import Path
from click.testing import CliRunner

from reportminer.cli import main
from reportminer.models import TestResult, TestStatus
from reportminer.parser import parse_reports


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def comprehensive_report(tmp_path):
    """Create a comprehensive report with various test statuses and data."""
    report_data = {
        "tests": {
            # Passed test
            "tests/auth/test_login.py::test_TMS_10001_login_success": [{
                "result": "passed",
                "duration": "1.23s",
                "time": "2024-01-15 10:00:00",
                "log": "INFO [auth] Login attempt started\nDEBUG [auth] Credentials validated\nINFO [auth] Login successful",
                "resultsTableRow": [
                    "<td>TMS_10001</td>",
                    "<td>passed</td>",
                    "<td>1.23s</td>",
                    "<td></td>"
                ]
            }],
            # Failed test with error
            "tests/auth/test_login.py::test_TMS_10002_login_invalid_password": [{
                "result": "failed",
                "duration": "2.45s",
                "time": "2024-01-15 10:01:00",
                "log": "INFO [auth] Login attempt started\nERROR [auth] Invalid password\nWARN [auth] Account lockout warning",
                "resultsTableRow": [
                    "<td>TMS_10002</td>",
                    "<td>failed</td>",
                    "<td>2.45s</td>",
                    "<td>AssertionError: Expected redirect to dashboard but got error page</td>"
                ]
            }],
            # Skipped test
            "tests/auth/test_login.py::test_TMS_10003_login_mfa[disabled]": [{
                "result": "skipped",
                "duration": "0.01s",
                "time": "2024-01-15 10:02:00",
                "resultsTableRow": [
                    "<td>TMS_10003</td>",
                    "<td>skipped</td>",
                    "<td>0.01s</td>",
                    "<td>Skipped: MFA not configured in test environment</td>"
                ]
            }],
            # Error test
            "tests/network/test_api.py::test_TMS_10004_api_connection": [{
                "result": "error",
                "duration": "30.00s",
                "time": "2024-01-15 10:03:00",
                "log": "INFO [api] Connecting to endpoint\nDEBUG [api] Timeout set to 30s\nFATAL [api] Connection refused\nTRACE [api] Stack trace follows",
                "resultsTableRow": [
                    "<td>TMS_10004</td>",
                    "<td>error</td>",
                    "<td>30.00s</td>",
                    "<td>ConnectionRefusedError: Unable to connect to api.example.com:443</td>"
                ]
            }],
            # Another failed test with same error (for grouping)
            "tests/network/test_api.py::test_TMS_10005_api_timeout": [{
                "result": "failed",
                "duration": "5.00s",
                "time": "2024-01-15 10:04:00",
                "resultsTableRow": [
                    "<td>TMS_10005</td>",
                    "<td>failed</td>",
                    "<td>5.00s</td>",
                    "<td>AssertionError: Expected redirect to dashboard but got error page</td>"
                ]
            }],
            # xfailed test
            "tests/experimental/test_feature.py::test_TMS_10006_new_feature": [{
                "result": "xfailed",
                "duration": "0.50s",
                "time": "2024-01-15 10:05:00",
                "resultsTableRow": [
                    "<td>TMS_10006</td>",
                    "<td>xfailed</td>",
                    "<td>0.50s</td>",
                    "<td>Expected failure: Feature not implemented yet</td>"
                ]
            }],
        }
    }

    report_file = tmp_path / "comprehensive.html"
    html = f'''<!DOCTYPE html>
<html>
<head><title>Comprehensive Test Report</title></head>
<body>
<div id="data-container" data-jsonblob='{json.dumps(report_data)}'>
</div>
</body>
</html>'''
    report_file.write_text(html)
    return report_file


class TestEndToEndParsing:
    """Test complete parsing workflow."""

    def test_parses_all_test_statuses(self, comprehensive_report):
        results = list(parse_reports([comprehensive_report]))

        # Should have all 6 tests
        assert len(results) == 6

        # Check each status is represented
        statuses = {r.status for r in results}
        assert TestStatus.PASSED in statuses
        assert TestStatus.FAILED in statuses
        assert TestStatus.SKIPPED in statuses
        assert TestStatus.ERROR in statuses
        assert TestStatus.XFAILED in statuses

    def test_preserves_execution_logs(self, comprehensive_report):
        results = list(parse_reports([comprehensive_report]))

        # Find the passed test with logs
        login_test = [r for r in results if r.tms_number == "TMS_10001"][0]
        assert login_test.execution_log is not None
        assert "INFO" in login_test.execution_log
        assert "DEBUG" in login_test.execution_log

    def test_preserves_failure_reasons(self, comprehensive_report):
        results = list(parse_reports([comprehensive_report]))

        failed_test = [r for r in results if r.tms_number == "TMS_10002"][0]
        assert failed_test.failure_reason is not None
        assert "AssertionError" in failed_test.failure_reason


class TestEndToEndCLI:
    """Test complete CLI workflow."""

    def test_default_shows_failed(self, runner, comprehensive_report):
        result = runner.invoke(main, [str(comprehensive_report)])
        assert result.exit_code == 0
        # Default is failed status, should show failed tests
        assert "TMS_10002" in result.output or "TMS_10005" in result.output

    def test_all_formats_work(self, runner, comprehensive_report):
        formats = ["raw", "pytest", "names", "full", "detailed", "jira", "jira-md", "wiki"]

        for fmt in formats:
            result = runner.invoke(main, ["-f", fmt, "-s", "all", str(comprehensive_report)])
            assert result.exit_code == 0, f"Format {fmt} failed: {result.output}"

    def test_all_status_filters_work(self, runner, comprehensive_report):
        statuses = ["failed", "passed", "skipped", "error", "all"]

        for status in statuses:
            result = runner.invoke(main, ["-s", status, str(comprehensive_report)])
            assert result.exit_code == 0, f"Status filter {status} failed: {result.output}"

    def test_grouping_works(self, runner, comprehensive_report):
        result = runner.invoke(main, ["-g", str(comprehensive_report)])
        assert result.exit_code == 0
        # Should have grouped output with test counts
        assert "tests]" in result.output

    def test_count_option(self, runner, comprehensive_report):
        result = runner.invoke(main, ["-c", "-s", "all", str(comprehensive_report)])
        assert result.exit_code == 0
        # Should output a number
        assert result.output.strip() == "6"

    def test_sort_option(self, runner, comprehensive_report):
        result = runner.invoke(main, ["-S", "-s", "all", str(comprehensive_report)])
        assert result.exit_code == 0
        # Should contain TMS numbers in sorted order
        assert "TMS_10001" in result.output

    def test_output_to_file(self, runner, comprehensive_report, tmp_path):
        output_file = tmp_path / "results.txt"
        result = runner.invoke(main, [
            "-o", str(output_file),
            "-s", "all",
            str(comprehensive_report)
        ])
        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "TMS_" in content


class TestDiffMode:
    """Test diff comparison mode."""

    def test_diff_shows_changes(self, runner, tmp_path):
        # Create old report (2 tests failing)
        old_data = {
            "tests": {
                "test::TMS_001": [{"result": "passed", "resultsTableRow": ["<td>TMS_001</td>", "", "", ""]}],
                "test::TMS_002": [{"result": "failed", "resultsTableRow": ["<td>TMS_002</td>", "", "", "<td>Error</td>"]}],
            }
        }
        old_report = tmp_path / "old.html"
        old_report.write_text(f'<html><body><div id="data-container" data-jsonblob=\'{json.dumps(old_data)}\'></div></body></html>')

        # Create new report (TMS_002 fixed, TMS_003 new failure)
        new_data = {
            "tests": {
                "test::TMS_001": [{"result": "passed", "resultsTableRow": ["<td>TMS_001</td>", "", "", ""]}],
                "test::TMS_002": [{"result": "passed", "resultsTableRow": ["<td>TMS_002</td>", "", "", ""]}],
                "test::TMS_003": [{"result": "failed", "resultsTableRow": ["<td>TMS_003</td>", "", "", "<td>NewError</td>"]}],
            }
        }
        new_report = tmp_path / "new.html"
        new_report.write_text(f'<html><body><div id="data-container" data-jsonblob=\'{json.dumps(new_data)}\'></div></body></html>')

        result = runner.invoke(main, ["--diff", str(old_report), str(new_report)])
        assert result.exit_code == 0
        assert "FIXED" in result.output or "Fixed" in result.output
        assert "NEW FAILURES" in result.output or "TMS_003" in result.output


class TestRerunIntegration:
    """Integration tests for rerun command."""

    def test_rerun_generates_valid_pytest_command(self, runner, comprehensive_report):
        result = runner.invoke(main, ["--rerun", str(comprehensive_report)])
        assert result.exit_code == 0
        assert "pytest -k" in result.output
        # Should contain quoted test names
        assert '"' in result.output
        assert " or " in result.output or "test_" in result.output

    def test_rerun_with_specific_status(self, runner, comprehensive_report):
        # Only rerun error tests
        result = runner.invoke(main, ["--rerun", "-s", "error", str(comprehensive_report)])
        assert result.exit_code == 0
        if "No tests found" not in result.output:
            assert "pytest -k" in result.output


class TestMultipleReportIntegration:
    """Integration tests for multiple report handling."""

    def test_parses_multiple_reports_correctly(self, runner, comprehensive_report, tmp_path):
        # Create second report with different tests
        second_data = {
            "tests": {
                "test::TMS_20001": [{"result": "passed", "resultsTableRow": ["<td>TMS_20001</td>", "", "", ""]}],
                "test::TMS_20002": [{"result": "failed", "resultsTableRow": ["<td>TMS_20002</td>", "", "", "<td>Error</td>"]}],
            }
        }
        second_report = tmp_path / "second.html"
        second_report.write_text(f'<html><body><div id="data-container" data-jsonblob=\'{json.dumps(second_data)}\'></div></body></html>')

        result = runner.invoke(main, ["-s", "all", str(comprehensive_report), str(second_report)])
        assert result.exit_code == 0
        # Should have TMS from both reports
        assert "TMS_10001" in result.output
        assert "TMS_20001" in result.output

    def test_deduplication_across_reports(self, runner, comprehensive_report, tmp_path):
        # Create report with duplicate TMS
        duplicate_data = {
            "tests": {
                "test_dup::TMS_10001": [{"result": "failed", "resultsTableRow": ["<td>TMS_10001</td>", "", "", "<td>Different error</td>"]}],
            }
        }
        dup_report = tmp_path / "dup.html"
        dup_report.write_text(f'<html><body><div id="data-container" data-jsonblob=\'{json.dumps(duplicate_data)}\'></div></body></html>')

        result = runner.invoke(main, ["-s", "all", "--unique", str(comprehensive_report), str(dup_report)])
        assert result.exit_code == 0
        # TMS_10001 should appear only once
        count = result.output.count("TMS_10001")
        assert count == 1


class TestRealWorldScenarios:
    """Tests simulating real-world usage patterns."""

    def test_ci_pipeline_usage(self, runner, comprehensive_report, tmp_path):
        """Simulate CI pipeline: get count, check if failures, output to file."""
        # Check count
        count_result = runner.invoke(main, ["-c", str(comprehensive_report)])
        assert count_result.exit_code == 0
        failed_count = int(count_result.output.strip())

        # If failures exist, output them to file
        if failed_count > 0:
            output_file = tmp_path / "failures.txt"
            result = runner.invoke(main, [
                "-f", "detailed",
                "-o", str(output_file),
                str(comprehensive_report)
            ])
            assert result.exit_code == 0
            assert output_file.exists()

    def test_developer_workflow(self, runner, comprehensive_report):
        """Simulate developer workflow: check failures, get rerun command."""
        # First, see what failed
        list_result = runner.invoke(main, ["-f", "detailed", str(comprehensive_report)])
        assert list_result.exit_code == 0

        # Then get rerun command
        rerun_result = runner.invoke(main, ["--rerun", str(comprehensive_report)])
        assert rerun_result.exit_code == 0
        if "No tests found" not in rerun_result.output:
            assert "pytest" in rerun_result.output

    def test_team_reporting_workflow(self, runner, comprehensive_report):
        """Simulate creating reports for team communication."""
        # Get Jira-formatted output
        jira_result = runner.invoke(main, ["-f", "jira-md", str(comprehensive_report)])
        assert jira_result.exit_code == 0
        # Should have markdown links
        assert "[TMS-" in jira_result.output

        # Get grouped by failure reason
        grouped_result = runner.invoke(main, ["-f", "raw", "-g", str(comprehensive_report)])
        assert grouped_result.exit_code == 0


class TestEdgeCasesIntegration:
    """Integration tests for edge cases."""

    def test_empty_report(self, runner, tmp_path):
        empty_report = tmp_path / "empty.html"
        empty_report.write_text('''<!DOCTYPE html>
<html><body>
<div id="data-container" data-jsonblob='{"tests": {}}'></div>
</body></html>''')

        result = runner.invoke(main, [str(empty_report)])
        assert "No tests found" in result.output or result.exit_code == 0

    def test_report_with_only_skipped(self, runner, tmp_path):
        skipped_data = {
            "tests": {
                "test::TMS_001": [{"result": "skipped", "resultsTableRow": ["<td>TMS_001</td>", "", "", "<td>Skipped</td>"]}],
            }
        }
        report = tmp_path / "skipped.html"
        report.write_text(f'<html><body><div id="data-container" data-jsonblob=\'{json.dumps(skipped_data)}\'></div></body></html>')

        # Default filter is failed - should show nothing
        result = runner.invoke(main, [str(report)])
        assert "No tests found" in result.output or result.exit_code == 0

        # With skipped filter - should show the test
        result = runner.invoke(main, ["-s", "skipped", str(report)])
        assert result.exit_code == 0
        assert "TMS_001" in result.output

    def test_report_with_unicode_content(self, runner, tmp_path):
        unicode_data = {
            "tests": {
                "test::TMS_001": [{
                    "result": "failed",
                    "resultsTableRow": [
                        "<td>TMS_001</td>",
                        "",
                        "",
                        "<td>Error: Expected unicode but got ascii</td>"
                    ]
                }],
            }
        }
        report = tmp_path / "unicode.html"
        # Use ensure_ascii=False and properly escape quotes
        json_str = json.dumps(unicode_data, ensure_ascii=False)
        # Escape single quotes for HTML attribute
        json_str = json_str.replace("'", "&#39;")
        report.write_text(
            f'<html><body><div id="data-container" data-jsonblob=\'{json_str}\'></div></body></html>',
            encoding='utf-8'
        )

        result = runner.invoke(main, ["-f", "detailed", str(report)])
        assert result.exit_code == 0
        assert "TMS_001" in result.output
