"""Command line interface."""

import sys
from pathlib import Path
from typing import Optional

import click

from .clipboard import copy_to_clipboard
from .compare import compare_reports, format_compare_result
from .formatters import get_formatter
from .jira_client import get_jira_client, JiraClientError
from .models import TestResult, TestStatus
from .parser import collect_html_files, parse_reports
from .progress import Spinner, create_progress_callback, get_random_phrase


FORMATS = ["raw", "pytest", "names", "full", "detailed", "jira", "jira-md", "wiki"]
STATUSES = ["failed", "passed", "skipped", "error", "all"]


def filter_by_status(results: list[TestResult], status: str) -> list[TestResult]:
    """Keep only results matching the given status."""
    if status == "all":
        return results

    target_status = TestStatus.from_string(status)
    return [r for r in results if r.status == target_status]


def deduplicate(results: list[TestResult]) -> list[TestResult]:
    """Remove duplicates by TMS number, keep first occurrence."""
    seen = set()
    unique = []
    for r in results:
        if r.tms_number not in seen:
            seen.add(r.tms_number)
            unique.append(r)
    return unique


def sort_results(results: list[TestResult]) -> list[TestResult]:
    """Sort by TMS number."""
    return sorted(results, key=lambda r: r.tms_number)


@click.command()
@click.argument("input_paths", nargs=-1, required=False, type=click.Path(exists=True))
@click.option(
    "-f", "--format",
    "output_format",
    type=click.Choice(FORMATS, case_sensitive=False),
    default="raw",
    help="Output format (default: raw)",
)
@click.option(
    "-s", "--status",
    type=click.Choice(STATUSES, case_sensitive=False),
    default="failed",
    help="Filter by test status (default: failed)",
)
@click.option(
    "-o", "--output",
    type=click.Path(),
    default=None,
    help="Export results to file",
)
@click.option(
    "-u/-U", "--unique/--no-unique",
    default=True,
    help="Remove duplicates (default: unique)",
)
@click.option(
    "-S", "--sort",
    is_flag=True,
    default=False,
    help="Sort output alphabetically",
)
@click.option(
    "-c", "--count",
    is_flag=True,
    default=False,
    help="Show count only",
)
@click.option(
    "--copy",
    is_flag=True,
    default=False,
    help="Copy output to clipboard",
)
@click.option(
    "--diff",
    is_flag=True,
    default=False,
    help="Compare two reports (requires exactly 2 input files)",
)
@click.option(
    "-v", "--view",
    is_flag=True,
    default=False,
    help="Open interactive TUI viewer",
)
@click.option(
    "-g", "--group",
    is_flag=True,
    default=False,
    help="Group output by failure reason (combine with -f for format)",
)
@click.option(
    "-r", "--rerun",
    is_flag=True,
    default=False,
    help="Output pytest rerun command for failed tests",
)
@click.option(
    "--clear-cache",
    is_flag=True,
    default=False,
    help="Clear Jira API cache and exit",
)
def main(
    input_paths: tuple[str, ...],
    output_format: str,
    status: str,
    output: Optional[str],
    unique: bool,
    sort: bool,
    count: bool,
    copy: bool,
    diff: bool,
    view: bool,
    group: bool,
    rerun: bool,
    clear_cache: bool,
):
    """Parse pytest-html test reports and extract test information.

    INPUT_PATHS: One or more HTML report files or directories.
    """
    # Handle clear cache command
    if clear_cache:
        from .cache import FileCache
        cache = FileCache("jira")
        cleared = cache.clear()
        click.echo(f"Cleared {cleared} cached items.")
        return

    # Require input paths for normal operation
    if not input_paths:
        click.echo("Error: Missing argument 'INPUT_PATHS...'.", err=True)
        sys.exit(1)

    spinner = Spinner()

    try:
        # Handle diff mode
        if diff:
            if len(input_paths) != 2:
                click.echo("Error: --diff requires exactly 2 report files", err=True)
                sys.exit(1)

            spinner.start(get_random_phrase("loading"))

            old_file = Path(input_paths[0])
            new_file = Path(input_paths[1])

            spinner.update(message="Parsing old report...")
            old_results = list(parse_reports([old_file]))

            spinner.update(message="Parsing new report...")
            new_results = list(parse_reports([new_file]))

            spinner.stop()

            result = compare_reports(old_results, new_results)
            formatted = format_compare_result(result)

            if copy:
                if copy_to_clipboard(formatted):
                    click.echo("(copied to clipboard)", err=True)
                else:
                    click.echo("(clipboard copy failed)", err=True)

            if output:
                Path(output).write_text(formatted + "\n", encoding="utf-8")
                click.echo(f"Results written to {output}", err=True)
            else:
                click.echo(formatted)

            return

        # Normal mode
        spinner.start(get_random_phrase("loading"))
        html_files = collect_html_files(list(input_paths))
        spinner.update(progress=f"({len(html_files)} files)")

        spinner.update(message=get_random_phrase("loading"))
        progress_cb = create_progress_callback(spinner)
        results = parse_reports(html_files, progress_callback=progress_cb)

        # Always deduplicate first if requested
        if unique:
            results = deduplicate(results)

        # For view mode, keep all results (TUI handles its own filtering)
        all_results = results.copy() if view else None

        results = filter_by_status(results, status)

        if sort:
            results = sort_results(results)

        # Enrich with Jira data if needed for format/view
        results_to_enrich = all_results if view else results
        needs_jira = view or output_format in ("jira-md", "wiki")
        if needs_jira:
            jira_client = get_jira_client()
            if jira_client.is_configured:
                spinner.update(message="Fetching Jira data...")
                try:
                    jira_client.enrich_results(results_to_enrich, progress_callback=progress_cb)
                except JiraClientError as e:
                    click.echo(f"Warning: Jira enrichment failed: {e}", err=True)

        spinner.stop()

        # Handle TUI view mode - always show ALL tests
        if view:
            if not all_results:
                click.echo("No tests found.", err=True)
                sys.exit(0)
            from .tui import ReportViewerApp
            app = ReportViewerApp(all_results)
            app.run()
            return

        if count:
            click.echo(len(results))
            return

        if not results:
            click.echo("No tests found matching criteria.", err=True)
            sys.exit(0)

        # Handle rerun command output
        if rerun:
            from .config import DEFAULT_RERUN_CMD
            test_ids = [r.test_id for r in results]
            if test_ids:
                # Use -k with test names for flexible matching
                test_names = " or ".join(r.test_name for r in results)
                formatted = DEFAULT_RERUN_CMD.format(tests=test_names)
            else:
                formatted = "# No tests to rerun"
        else:
            formatter = get_formatter(output_format, group=group)
            formatted = formatter.format(results)

        if copy:
            if copy_to_clipboard(formatted):
                click.echo("(copied to clipboard)", err=True)
            else:
                click.echo("(clipboard copy failed)", err=True)

        if output:
            output_path = Path(output)
            spinner.start(get_random_phrase("writing"))
            output_path.write_text(formatted + "\n", encoding="utf-8")
            spinner.stop(f"Results written to {output_path}")
        else:
            click.echo(formatted)

    except Exception as e:
        spinner.stop()
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
