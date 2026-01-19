"""Output formatters for different output modes."""

from . import config
from .models import TestResult


class Formatter:
    """Base class for formatters."""

    def format(self, results: list[TestResult]) -> str:
        raise NotImplementedError


class RawFormatter(Formatter):
    """Comma-separated TMS numbers."""

    def format(self, results: list[TestResult]) -> str:
        tms_numbers = [r.tms_number for r in results]
        return ", ".join(tms_numbers)


class PytestFormatter(Formatter):
    """TMS numbers joined with 'or' for pytest -m flag."""

    def format(self, results: list[TestResult]) -> str:
        tms_numbers = [r.tms_number for r in results]
        return " or ".join(tms_numbers)


class NamesFormatter(Formatter):
    """Comma-separated test function names."""

    def format(self, results: list[TestResult]) -> str:
        names = [r.test_name for r in results]
        return ", ".join(names)


class FullFormatter(Formatter):
    """Full test paths, one per line."""

    def format(self, results: list[TestResult]) -> str:
        paths = [r.test_id for r in results]
        return "\n".join(paths)


class DetailedFormatter(Formatter):
    """Structured blocks with TMS, status, name and full failure reason."""

    def format(self, results: list[TestResult]) -> str:
        lines = []
        separator = "-" * 80

        for i, r in enumerate(results):
            if i > 0:
                lines.append("")
            lines.append(separator)
            lines.append(f"TMS:      {r.tms_number}")
            lines.append(f"Status:   {r.status.value}")
            lines.append(f"Test:     {r.test_name}")

            reason = r.failure_reason or ""
            if reason:
                lines.append("Reason:")
                # Indent each line of the reason
                for reason_line in reason.split("\n"):
                    lines.append(f"  {reason_line}")

        if lines:
            lines.append(separator)

        return "\n".join(lines)


class JiraFormatter(Formatter):
    """Jira links, one per line."""

    def format(self, results: list[TestResult]) -> str:
        base_url = config.JIRA_BASE_URL.rstrip("/")
        lines = []
        for r in results:
            url = f"{base_url}/browse/{r.tms_jira_format}"
            lines.append(url)
        return "\n".join(lines)


class GroupedFormatter(Formatter):
    """Group tests by failure reason."""

    def format(self, results: list[TestResult]) -> str:
        # Group by failure reason
        groups: dict[str, list[TestResult]] = {}
        for r in results:
            reason = r.failure_reason or "No failure reason"
            # Normalize reason - take first line, truncate if too long
            reason = reason.split("\n")[0].strip()
            if len(reason) > 80:
                reason = reason[:77] + "..."
            if not reason:
                reason = "No failure reason"

            if reason not in groups:
                groups[reason] = []
            groups[reason].append(r)

        # Sort groups by count (most common first)
        sorted_groups = sorted(groups.items(), key=lambda x: -len(x[1]))

        lines = []
        for reason, tests in sorted_groups:
            lines.append(f"[{len(tests)} tests] {reason}")
            for t in tests:
                lines.append(f"  - {t.tms_number}: {t.test_name}")
            lines.append("")

        return "\n".join(lines).rstrip()


class JiraMarkdownFormatter(Formatter):
    """GitHub-flavored markdown links: [title](url)"""

    def format(self, results: list[TestResult]) -> str:
        base_url = config.JIRA_BASE_URL.rstrip("/")
        lines = []

        for r in results:
            jira_key = r.tms_jira_format
            url = f"{base_url}/browse/{jira_key}"

            # Use Jira summary if available, otherwise just the key
            if r.jira_summary:
                title = f"{jira_key}: {r.jira_summary}"
            else:
                title = jira_key

            # Markdown link format: [title](url)
            lines.append(f"- [{title}]({url})")

        return "\n".join(lines)


class JiraWikiFormatter(Formatter):
    """Confluence wiki markup with titles: [title|url]"""

    def format(self, results: list[TestResult]) -> str:
        base_url = config.JIRA_BASE_URL.rstrip("/")
        lines = []

        for r in results:
            jira_key = r.tms_jira_format
            url = f"{base_url}/browse/{jira_key}"

            # Use Jira summary if available, otherwise just the key
            if r.jira_summary:
                title = f"{jira_key}: {r.jira_summary}"
            else:
                title = jira_key

            # Confluence wiki link format: [title|url]
            lines.append(f"[{title}|{url}]")

        return "\n".join(lines)


class GroupedByReasonFormatter(Formatter):
    """Group tests by failure reason with configurable inner format."""

    def __init__(self, inner_format: str = "raw"):
        self.inner_format = inner_format

    def format(self, results: list[TestResult]) -> str:
        # Group by failure reason
        groups: dict[str, list[TestResult]] = {}
        for r in results:
            reason = r.failure_reason or "No failure reason"
            # Normalize reason - take first line, truncate if too long
            reason = reason.split("\n")[0].strip()
            if len(reason) > 80:
                reason = reason[:77] + "..."
            if not reason:
                reason = "No failure reason"

            if reason not in groups:
                groups[reason] = []
            groups[reason].append(r)

        # Sort groups by count (most common first)
        sorted_groups = sorted(groups.items(), key=lambda x: -len(x[1]))

        # Get inner formatter
        inner_formatter = FORMATTERS.get(self.inner_format)

        lines = []
        for reason, tests in sorted_groups:
            lines.append(f"### [{len(tests)} tests] {reason}")
            lines.append("")

            if inner_formatter and self.inner_format != "grouped":
                # Use the inner formatter for each group
                formatted_inner = inner_formatter.format(tests)
                # Indent each line
                for line in formatted_inner.split("\n"):
                    if line:
                        lines.append(f"  {line}")
            else:
                # Default: just list TMS and test names
                for t in tests:
                    lines.append(f"  - {t.tms_number}: {t.test_name}")

            lines.append("")

        return "\n".join(lines).rstrip()


FORMATTERS = {
    "raw": RawFormatter(),
    "pytest": PytestFormatter(),
    "names": NamesFormatter(),
    "full": FullFormatter(),
    "detailed": DetailedFormatter(),
    "jira": JiraFormatter(),
    "jira-md": JiraMarkdownFormatter(),
    "wiki": JiraWikiFormatter(),
}


def get_formatter(format_name: str, group: bool = False) -> Formatter:
    """Get formatter by name.

    Args:
        format_name: The format to use (e.g., "raw", "pytest")
        group: If True, wrap the formatter with grouping by failure reason
    """
    format_key = format_name.lower()

    formatter = FORMATTERS.get(format_key)
    if not formatter:
        valid = ", ".join(FORMATTERS.keys())
        raise ValueError(f"Unknown format: {format_name}. Valid: {valid}")

    # Wrap with grouping if requested
    if group:
        return GroupedByReasonFormatter(inner_format=format_key)

    return formatter
