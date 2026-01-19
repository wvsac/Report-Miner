"""HTML report parsing logic."""

import json
import re
from pathlib import Path
from typing import Iterator, Optional

from bs4 import BeautifulSoup

from .models import TestResult, TestStatus


# Pattern to find TMS numbers like TMS_12345
TMS_PATTERN = re.compile(r"TMS_\d+")


def extract_json_data(html_content: str) -> dict:
    """Pull JSON data blob from pytest-html report."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Try finding by id first, then by attribute
    data_container = soup.find(id="data-container")
    if not data_container:
        data_container = soup.find(attrs={"data-jsonblob": True})

    if not data_container:
        raise ValueError("Could not find data container in HTML report")

    json_blob = data_container.get("data-jsonblob")
    if not json_blob:
        raise ValueError("Could not find JSON data blob in report")

    # BeautifulSoup already decodes HTML entities
    return json.loads(json_blob)


def parse_tms_from_row(row_html: str) -> Optional[str]:
    """Find TMS number in a table row HTML string."""
    match = TMS_PATTERN.search(row_html)
    if match:
        return match.group()
    return None


def parse_test_name_from_id(test_id: str) -> str:
    """Get just the test function name from full path like path/file.py::test_name."""
    if "::" in test_id:
        name_part = test_id.split("::")[-1]
        # Strip parametrize brackets if present
        if "[" in name_part:
            name_part = name_part.split("[")[0]
        return name_part
    return test_id


def parse_failure_reason(row_cells: list[str]) -> Optional[str]:
    """Get failure reason text from table row cells."""
    if len(row_cells) > 3:
        reason_cell = row_cells[3]
        soup = BeautifulSoup(reason_cell, "html.parser")
        text = soup.get_text(strip=True)
        return text if text else None
    return None


def extract_execution_log(test_data: dict, row_cells: list[str]) -> Optional[str]:
    """Extract stdout/stderr/log output from test data."""
    log_parts = []

    # Check extras array (common in pytest-html)
    extras = test_data.get("extras", [])
    for extra in extras:
        if isinstance(extra, dict):
            name = extra.get("name", "")
            content = extra.get("content", "")
            if name.lower() in ("stdout", "stderr", "log") and content:
                log_parts.append(f"=== {name.upper()} ===")
                # Clean up the content - decode HTML entities and clean whitespace
                cleaned = _clean_log_content(content)
                log_parts.append(cleaned)

    # Check direct log field
    log_content = test_data.get("log", "")
    if log_content:
        log_parts.append("=== LOG ===")
        cleaned = _clean_log_content(log_content)
        log_parts.append(cleaned)

    # Extract logs from the results table row (often stored in expandable sections)
    for cell in row_cells:
        if "log" in cell.lower() or "pre" in cell.lower():
            soup = BeautifulSoup(cell, "html.parser")
            # Find all <pre> tags which usually contain log output
            for pre in soup.find_all("pre"):
                text = pre.get_text()  # Don't strip - preserve formatting
                if text and len(text.strip()) > 10:  # Skip tiny snippets
                    cleaned = _clean_log_content(text)
                    log_parts.append(cleaned)

    return "\n\n".join(log_parts) if log_parts else None


def _clean_log_content(content: str) -> str:
    """Clean up log content by removing unnecessary characters."""
    import html

    # Decode HTML entities (e.g., &lt; -> <, &amp; -> &)
    content = html.unescape(content)

    # Remove ANSI escape sequences (color codes, etc.)
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    content = ansi_escape.sub('', content)

    # Remove carriage returns (but keep newlines)
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    # Remove null bytes and other control characters (except newline and tab)
    content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)

    # Normalize multiple blank lines to single blank line
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content.strip()


def parse_test_result(test_id: str, test_data: dict) -> Optional[TestResult]:
    """Parse one test result from the JSON data."""
    result_str = test_data.get("result", "")
    try:
        status = TestStatus.from_string(result_str)
    except ValueError:
        return None

    results_row = test_data.get("resultsTableRow", [])

    # Find TMS number in any cell
    tms_number = None
    for cell in results_row:
        tms_number = parse_tms_from_row(cell)
        if tms_number:
            break

    if not tms_number:
        return None

    test_name = parse_test_name_from_id(test_id)
    failure_reason = parse_failure_reason(results_row)
    execution_log = extract_execution_log(test_data, results_row)

    return TestResult(
        tms_number=tms_number,
        test_name=test_name,
        test_id=test_id,
        status=status,
        failure_reason=failure_reason,
        duration=test_data.get("duration"),
        timestamp=test_data.get("time"),
        execution_log=execution_log,
    )


def parse_report(file_path: Path) -> Iterator[TestResult]:
    """Parse a single pytest-html report file."""
    html_content = file_path.read_text(encoding="utf-8")
    data = extract_json_data(html_content)

    tests = data.get("tests", {})

    for test_id, test_runs in tests.items():
        # Handle both single result and list of results
        if not isinstance(test_runs, list):
            test_runs = [test_runs]

        for test_data in test_runs:
            result = parse_test_result(test_id, test_data)
            if result:
                yield result


def parse_reports(file_paths: list[Path], progress_callback=None) -> list[TestResult]:
    """Parse multiple report files."""
    results = []
    total = len(file_paths)

    for i, file_path in enumerate(file_paths):
        if progress_callback:
            progress_callback(i, total, file_path.name)

        try:
            for result in parse_report(file_path):
                results.append(result)
        except Exception as e:
            raise RuntimeError(f"Failed to parse {file_path}: {e}") from e

    if progress_callback:
        progress_callback(total, total, "complete")

    return results


def collect_html_files(paths: list[str]) -> list[Path]:
    """Gather all HTML files from given paths (files or directories)."""
    html_files = []

    for path_str in paths:
        path = Path(path_str)

        if path.is_file() and path.suffix.lower() == ".html":
            html_files.append(path)
        elif path.is_dir():
            html_files.extend(path.glob("**/*.html"))
        elif path.is_file():
            raise ValueError(f"Not an HTML file: {path}")
        else:
            raise FileNotFoundError(f"Path not found: {path}")

    if not html_files:
        raise ValueError("No HTML files found in provided paths")

    return sorted(html_files)
