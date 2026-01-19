"""Tests for HTML report parsing."""

import pytest
from pathlib import Path

from reportminer.parser import (
    parse_reports,
    parse_report,
    collect_html_files,
    extract_json_data,
    parse_tms_from_row,
    parse_test_name_from_id,
    parse_failure_reason,
    extract_execution_log,
)
from reportminer.models import TestStatus


class TestParseTmsFromRow:
    """Tests for TMS number extraction."""

    def test_finds_tms_number(self):
        assert parse_tms_from_row("<td>TMS_12345</td>") == "TMS_12345"

    def test_finds_tms_in_longer_string(self):
        assert parse_tms_from_row("test_TMS_99999_something") == "TMS_99999"

    def test_returns_none_when_not_found(self):
        assert parse_tms_from_row("<td>no tms here</td>") is None

    def test_returns_first_match(self):
        assert parse_tms_from_row("TMS_111 and TMS_222") == "TMS_111"


class TestParseTestNameFromId:
    """Tests for test name extraction."""

    def test_extracts_from_full_path(self):
        test_id = "tests/auth/test_login.py::test_login_feature"
        assert parse_test_name_from_id(test_id) == "test_login_feature"

    def test_strips_parametrize_brackets(self):
        test_id = "tests/test.py::test_something[param1-param2]"
        assert parse_test_name_from_id(test_id) == "test_something"

    def test_handles_simple_name(self):
        assert parse_test_name_from_id("test_simple") == "test_simple"


class TestParseFailureReason:
    """Tests for failure reason extraction."""

    def test_extracts_from_fourth_cell(self):
        cells = ["<td>1</td>", "<td>2</td>", "<td>3</td>", "<td>Error message</td>"]
        assert parse_failure_reason(cells) == "Error message"

    def test_returns_none_for_empty_cell(self):
        cells = ["<td>1</td>", "<td>2</td>", "<td>3</td>", "<td></td>"]
        assert parse_failure_reason(cells) is None

    def test_returns_none_for_missing_cells(self):
        cells = ["<td>1</td>", "<td>2</td>"]
        assert parse_failure_reason(cells) is None

    def test_strips_html_tags(self):
        cells = ["", "", "", "<td><b>Bold</b> error</td>"]
        # BeautifulSoup's get_text(strip=True) may combine text without spaces
        result = parse_failure_reason(cells)
        assert "Bold" in result and "error" in result


class TestExtractExecutionLog:
    """Tests for execution log extraction."""

    def test_extracts_from_log_field(self):
        test_data = {"log": "Some log content"}
        result = extract_execution_log(test_data, [])
        assert "LOG" in result
        assert "Some log content" in result

    def test_extracts_from_extras(self):
        test_data = {
            "extras": [
                {"name": "stdout", "content": "stdout output"},
                {"name": "stderr", "content": "stderr output"},
            ]
        }
        result = extract_execution_log(test_data, [])
        assert "STDOUT" in result
        assert "stdout output" in result

    def test_returns_none_when_no_logs(self):
        result = extract_execution_log({}, [])
        assert result is None


class TestExtractJsonData:
    """Tests for JSON data extraction from HTML."""

    def test_extracts_from_data_container(self, sample_html_report):
        html_content = sample_html_report.read_text()
        data = extract_json_data(html_content)
        assert "tests" in data

    def test_raises_on_missing_container(self):
        html = "<html><body></body></html>"
        with pytest.raises(ValueError, match="Could not find data container"):
            extract_json_data(html)


class TestParseReport:
    """Tests for single report parsing."""

    def test_parses_all_tests(self, sample_html_report):
        results = list(parse_report(sample_html_report))
        assert len(results) == 3

    def test_extracts_tms_numbers(self, sample_html_report):
        results = list(parse_report(sample_html_report))
        tms_numbers = {r.tms_number for r in results}
        assert "TMS_12345" in tms_numbers
        assert "TMS_67890" in tms_numbers
        assert "TMS_11111" in tms_numbers

    def test_extracts_status(self, sample_html_report):
        results = list(parse_report(sample_html_report))
        statuses = {r.tms_number: r.status for r in results}
        assert statuses["TMS_12345"] == TestStatus.PASSED
        assert statuses["TMS_67890"] == TestStatus.FAILED

    def test_extracts_failure_reason(self, sample_html_report):
        results = list(parse_report(sample_html_report))
        failed = [r for r in results if r.tms_number == "TMS_67890"][0]
        assert "AssertionError" in failed.failure_reason

    def test_extracts_execution_logs(self, sample_html_report_with_logs):
        results = list(parse_report(sample_html_report_with_logs))
        assert len(results) == 1
        assert results[0].execution_log is not None
        assert "kafka-consumer" in results[0].execution_log


class TestParseReports:
    """Tests for multiple report parsing."""

    def test_parses_multiple_files(self, sample_html_report, second_html_report):
        results = parse_reports([sample_html_report, second_html_report])
        assert len(results) == 6  # 3 from first + 3 from second

    def test_calls_progress_callback(self, sample_html_report):
        callback_calls = []

        def callback(current, total, name):
            callback_calls.append((current, total, name))

        parse_reports([sample_html_report], progress_callback=callback)
        assert len(callback_calls) >= 1


class TestCollectHtmlFiles:
    """Tests for HTML file collection."""

    def test_collects_single_file(self, sample_html_report):
        files = collect_html_files([str(sample_html_report)])
        assert len(files) == 1
        assert files[0] == sample_html_report

    def test_collects_from_directory(self, tmp_path, sample_html_report):
        # Create additional HTML file
        (tmp_path / "another.html").write_text("<html></html>")
        files = collect_html_files([str(tmp_path)])
        assert len(files) >= 1

    def test_raises_for_non_html_file(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not html")
        with pytest.raises(ValueError, match="Not an HTML file"):
            collect_html_files([str(txt_file)])

    def test_raises_for_missing_path(self):
        with pytest.raises(FileNotFoundError):
            collect_html_files(["/nonexistent/path"])

    def test_raises_when_no_html_found(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(ValueError, match="No HTML files found"):
            collect_html_files([str(empty_dir)])
