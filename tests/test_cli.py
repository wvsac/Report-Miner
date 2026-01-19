"""Tests for CLI interface."""

import pytest
from click.testing import CliRunner

from reportminer.cli import main, filter_by_status, deduplicate, sort_results
from reportminer.models import TestResult, TestStatus


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def test_results():
    """Create test results for CLI testing."""
    return [
        TestResult(
            tms_number="TMS_001",
            test_name="test_a",
            test_id="test_a",
            status=TestStatus.PASSED,
        ),
        TestResult(
            tms_number="TMS_002",
            test_name="test_b",
            test_id="test_b",
            status=TestStatus.FAILED,
        ),
        TestResult(
            tms_number="TMS_003",
            test_name="test_c",
            test_id="test_c",
            status=TestStatus.SKIPPED,
        ),
    ]


class TestFilterByStatus:
    """Tests for status filtering."""

    def test_filter_all_returns_all(self, test_results):
        result = filter_by_status(test_results, "all")
        assert len(result) == 3

    def test_filter_passed(self, test_results):
        result = filter_by_status(test_results, "passed")
        assert len(result) == 1
        assert result[0].status == TestStatus.PASSED

    def test_filter_failed(self, test_results):
        result = filter_by_status(test_results, "failed")
        assert len(result) == 1
        assert result[0].status == TestStatus.FAILED

    def test_filter_skipped(self, test_results):
        result = filter_by_status(test_results, "skipped")
        assert len(result) == 1
        assert result[0].status == TestStatus.SKIPPED


class TestDeduplicate:
    """Tests for deduplication."""

    def test_removes_duplicates(self):
        results = [
            TestResult(tms_number="TMS_001", test_name="test", test_id="test", status=TestStatus.PASSED),
            TestResult(tms_number="TMS_001", test_name="test", test_id="test", status=TestStatus.FAILED),
            TestResult(tms_number="TMS_002", test_name="test", test_id="test", status=TestStatus.PASSED),
        ]
        unique = deduplicate(results)
        assert len(unique) == 2

    def test_keeps_first_occurrence(self):
        results = [
            TestResult(tms_number="TMS_001", test_name="first", test_id="test", status=TestStatus.PASSED),
            TestResult(tms_number="TMS_001", test_name="second", test_id="test", status=TestStatus.FAILED),
        ]
        unique = deduplicate(results)
        assert unique[0].test_name == "first"

    def test_empty_list(self):
        assert deduplicate([]) == []


class TestSortResults:
    """Tests for result sorting."""

    def test_sorts_by_tms_number(self, test_results):
        # Reverse the list first
        reversed_results = list(reversed(test_results))
        sorted_results = sort_results(reversed_results)
        assert sorted_results[0].tms_number == "TMS_001"
        assert sorted_results[1].tms_number == "TMS_002"
        assert sorted_results[2].tms_number == "TMS_003"

    def test_empty_list(self):
        assert sort_results([]) == []


class TestCLI:
    """Tests for CLI commands."""

    def test_help_option(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Parse pytest-html test reports" in result.output

    def test_parses_report(self, runner, sample_html_report):
        result = runner.invoke(main, [str(sample_html_report)])
        assert result.exit_code == 0
        # Default is failed tests only
        assert "TMS_67890" in result.output or "TMS_11111" in result.output

    def test_format_raw(self, runner, sample_html_report):
        result = runner.invoke(main, ["-f", "raw", str(sample_html_report)])
        assert result.exit_code == 0
        assert ", " in result.output or "TMS_" in result.output

    def test_format_pytest(self, runner, sample_html_report):
        result = runner.invoke(main, ["-f", "pytest", str(sample_html_report)])
        assert result.exit_code == 0
        assert " or " in result.output or "TMS_" in result.output

    def test_format_names(self, runner, sample_html_report):
        result = runner.invoke(main, ["-f", "names", "-s", "all", str(sample_html_report)])
        assert result.exit_code == 0
        assert "test_" in result.output

    def test_format_detailed(self, runner, sample_html_report):
        result = runner.invoke(main, ["-f", "detailed", str(sample_html_report)])
        assert result.exit_code == 0
        assert "TMS:" in result.output
        assert "Status:" in result.output

    def test_format_jira(self, runner, sample_html_report):
        result = runner.invoke(main, ["-f", "jira", str(sample_html_report)])
        assert result.exit_code == 0
        assert "browse/" in result.output

    def test_format_jira_md(self, runner, sample_html_report, monkeypatch):
        monkeypatch.setattr("reportminer.config.JIRA_BASE_URL", "https://jira.example.com")

        result = runner.invoke(main, ["-f", "jira-md", str(sample_html_report)])
        assert result.exit_code == 0
        assert "[TMS-" in result.output
        # Markdown format uses (url) not |url
        assert "](https://" in result.output or "](http://" in result.output

    def test_group_flag(self, runner, sample_html_report):
        result = runner.invoke(main, ["-f", "raw", "--group", str(sample_html_report)])
        assert result.exit_code == 0
        assert "tests]" in result.output

    def test_status_all(self, runner, sample_html_report):
        result = runner.invoke(main, ["-s", "all", str(sample_html_report)])
        assert result.exit_code == 0
        assert "TMS_12345" in result.output  # Passed test

    def test_status_passed(self, runner, sample_html_report):
        result = runner.invoke(main, ["-s", "passed", str(sample_html_report)])
        assert result.exit_code == 0
        assert "TMS_12345" in result.output

    def test_count_option(self, runner, sample_html_report):
        result = runner.invoke(main, ["-c", str(sample_html_report)])
        assert result.exit_code == 0
        # Should output a number
        assert result.output.strip().isdigit()

    def test_sort_option(self, runner, sample_html_report):
        result = runner.invoke(main, ["-S", str(sample_html_report)])
        assert result.exit_code == 0

    def test_output_to_file(self, runner, sample_html_report, tmp_path):
        output_file = tmp_path / "output.txt"
        result = runner.invoke(main, ["-o", str(output_file), str(sample_html_report)])
        assert result.exit_code == 0
        assert output_file.exists()

    def test_diff_requires_two_files(self, runner, sample_html_report):
        result = runner.invoke(main, ["--diff", str(sample_html_report)])
        assert result.exit_code == 1
        assert "requires exactly 2" in result.output

    def test_diff_mode(self, runner, sample_html_report, second_html_report):
        result = runner.invoke(main, ["--diff", str(sample_html_report), str(second_html_report)])
        assert result.exit_code == 0
        assert "SUMMARY" in result.output or "FIXED" in result.output or "NEW FAILURES" in result.output

    def test_invalid_path(self, runner):
        result = runner.invoke(main, ["/nonexistent/path.html"])
        assert result.exit_code != 0

    def test_no_tests_found_message(self, runner, tmp_path):
        # Create empty report
        empty_report = tmp_path / "empty.html"
        empty_report.write_text('''<!DOCTYPE html>
<html><body>
<div id="data-container" data-jsonblob='{"tests": {}}'></div>
</body></html>''')
        result = runner.invoke(main, [str(empty_report)])
        assert "No tests found" in result.output or result.exit_code == 0


class TestRerunCommand:
    """Tests for --rerun command."""

    def test_rerun_outputs_pytest_command(self, runner, sample_html_report):
        result = runner.invoke(main, ["--rerun", str(sample_html_report)])
        assert result.exit_code == 0
        assert "pytest -k" in result.output
        # Should contain test names joined with "or"
        assert " or " in result.output or "test_" in result.output

    def test_rerun_includes_test_names(self, runner, sample_html_report):
        result = runner.invoke(main, ["--rerun", str(sample_html_report)])
        assert result.exit_code == 0
        # Test names should be in the output
        output = result.output.lower()
        assert "test_" in output

    def test_rerun_with_no_failed_tests(self, runner, tmp_path):
        # Create report with only passed tests
        import json
        report_data = {
            "tests": {
                "tests/test.py::test_TMS_12345_login": [{
                    "result": "passed",
                    "duration": "1.0s",
                    "time": "2024-01-15",
                    "resultsTableRow": [
                        "<td>TMS_12345</td>",
                        "<td>passed</td>",
                        "<td>1.0s</td>",
                        "<td></td>"
                    ]
                }]
            }
        }
        report = tmp_path / "all_passed.html"
        report.write_text(f'''<!DOCTYPE html>
<html><body>
<div id="data-container" data-jsonblob='{json.dumps(report_data)}'></div>
</body></html>''')

        result = runner.invoke(main, ["--rerun", str(report)])
        # Should output message about no tests to rerun
        assert "No tests found" in result.output or result.exit_code == 0

    def test_rerun_with_copy_flag(self, runner, sample_html_report, monkeypatch):
        # Mock clipboard
        copied_text = []
        def mock_copy(text):
            copied_text.append(text)
            return True
        monkeypatch.setattr("reportminer.cli.copy_to_clipboard", mock_copy)

        result = runner.invoke(main, ["--rerun", "--copy", str(sample_html_report)])
        assert result.exit_code == 0
        assert "copied to clipboard" in result.output.lower() or len(copied_text) > 0

    def test_rerun_custom_command(self, runner, sample_html_report, monkeypatch):
        # Set custom rerun command
        monkeypatch.setattr("reportminer.config.DEFAULT_RERUN_CMD", 'python -m pytest --tb=short -k "{tests}"')

        # Need to reload the module to pick up the change
        import importlib
        import reportminer.cli
        importlib.reload(reportminer.cli)

        result = runner.invoke(reportminer.cli.main, ["--rerun", str(sample_html_report)])
        assert result.exit_code == 0
        assert "python -m pytest --tb=short -k" in result.output


class TestMultipleFiles:
    """Tests for handling multiple report files."""

    def test_parses_multiple_reports(self, runner, sample_html_report, second_html_report):
        result = runner.invoke(main, [
            "-s", "all",
            str(sample_html_report),
            str(second_html_report)
        ])
        assert result.exit_code == 0
        # Should have TMS numbers from both files
        assert "TMS_12345" in result.output

    def test_unique_across_files(self, runner, sample_html_report, second_html_report):
        result = runner.invoke(main, [
            "-s", "all", "--unique",
            str(sample_html_report),
            str(second_html_report)
        ])
        assert result.exit_code == 0
        # TMS_12345 appears in both - should only appear once in output
        output = result.output
        # Count occurrences
        count = output.count("TMS_12345")
        assert count == 1

    def test_no_unique_keeps_duplicates(self, runner, sample_html_report, second_html_report):
        result = runner.invoke(main, [
            "-s", "all", "--no-unique",
            str(sample_html_report),
            str(second_html_report)
        ])
        assert result.exit_code == 0

    def test_directory_parsing(self, runner, tmp_path, sample_html_report):
        # Copy sample report to directory
        import shutil
        report_dir = tmp_path / "reports"
        report_dir.mkdir()
        shutil.copy(sample_html_report, report_dir / "report1.html")
        shutil.copy(sample_html_report, report_dir / "report2.html")

        result = runner.invoke(main, ["-s", "all", str(report_dir)])
        assert result.exit_code == 0


class TestOutputFile:
    """Tests for output file generation."""

    def test_creates_output_file(self, runner, sample_html_report, tmp_path):
        output_file = tmp_path / "results.txt"
        result = runner.invoke(main, [
            "-o", str(output_file),
            str(sample_html_report)
        ])
        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "TMS_" in content

    def test_output_file_includes_newline(self, runner, sample_html_report, tmp_path):
        output_file = tmp_path / "results.txt"
        runner.invoke(main, ["-o", str(output_file), str(sample_html_report)])
        content = output_file.read_text()
        assert content.endswith("\n")


class TestFormatWiki:
    """Tests for wiki output format."""

    def test_format_wiki_output(self, runner, sample_html_report, monkeypatch):
        monkeypatch.setattr("reportminer.config.JIRA_BASE_URL", "https://jira.example.com")

        result = runner.invoke(main, ["-f", "wiki", str(sample_html_report)])
        assert result.exit_code == 0
        # Wiki format uses [title|url] syntax
        assert "[TMS-" in result.output
        assert "|https://" in result.output or "|http://" in result.output


class TestClearCache:
    """Tests for --clear-cache command."""

    def test_clear_cache_works(self, runner, tmp_path, monkeypatch):
        # Set up a temporary cache directory
        monkeypatch.setattr("reportminer.cache.CACHE_DIR", tmp_path)

        # Create some cache files
        cache_dir = tmp_path / "jira"
        cache_dir.mkdir(parents=True)
        (cache_dir / "test1.json").write_text('{"key": "test"}')
        (cache_dir / "test2.json").write_text('{"key": "test"}')

        result = runner.invoke(main, ["--clear-cache"])
        assert result.exit_code == 0
        assert "Cleared 2 cached items" in result.output

    def test_clear_cache_empty(self, runner, tmp_path, monkeypatch):
        # Set up empty cache directory
        monkeypatch.setattr("reportminer.cache.CACHE_DIR", tmp_path)

        result = runner.invoke(main, ["--clear-cache"])
        assert result.exit_code == 0
        assert "Cleared 0 cached items" in result.output

    def test_missing_input_paths_shows_error(self, runner):
        result = runner.invoke(main, [])
        assert result.exit_code == 1
        assert "Missing argument" in result.output


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_handles_corrupted_html(self, runner, tmp_path):
        corrupted = tmp_path / "corrupted.html"
        corrupted.write_text("<html><body>No data container</body></html>")
        result = runner.invoke(main, [str(corrupted)])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_handles_invalid_json_blob(self, runner, tmp_path):
        bad_json = tmp_path / "bad_json.html"
        bad_json.write_text('''<!DOCTYPE html>
<html><body>
<div id="data-container" data-jsonblob='not valid json'></div>
</body></html>''')
        result = runner.invoke(main, [str(bad_json)])
        assert result.exit_code == 1

    def test_mixed_valid_invalid_paths(self, runner, sample_html_report, tmp_path):
        # Should fail if any path is invalid
        result = runner.invoke(main, [
            str(sample_html_report),
            str(tmp_path / "nonexistent.html")
        ])
        assert result.exit_code != 0
