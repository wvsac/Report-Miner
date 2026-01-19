"""Compare two reports to find differences."""

from dataclasses import dataclass

from .models import TestResult


@dataclass
class CompareResult:
    """Result of comparing two reports."""
    new_failures: list[TestResult]      # failed in new, not in old
    fixed: list[TestResult]             # failed in old, passed in new
    still_failing: list[TestResult]     # failed in both
    new_errors: list[TestResult]        # error in new, not in old
    fixed_errors: list[TestResult]      # error in old, passed in new
    still_erroring: list[TestResult]    # error in both
    new_passes: list[TestResult]        # passed in new, not in old


def compare_reports(
    old_results: list[TestResult],
    new_results: list[TestResult],
) -> CompareResult:
    """Compare old and new test results."""

    # Build lookup dicts by TMS number
    old_by_tms = {r.tms_number: r for r in old_results}
    new_by_tms = {r.tms_number: r for r in new_results}

    old_failed = {r.tms_number for r in old_results if r.status.value == "failed"}
    new_failed = {r.tms_number for r in new_results if r.status.value == "failed"}
    old_error = {r.tms_number for r in old_results if r.status.value == "error"}
    new_error = {r.tms_number for r in new_results if r.status.value == "error"}
    old_passed = {r.tms_number for r in old_results if r.status.value == "passed"}
    new_passed = {r.tms_number for r in new_results if r.status.value == "passed"}

    # New failures - failed now but wasn't failing before
    new_failure_tms = new_failed - old_failed - old_error
    new_failures = [new_by_tms[tms] for tms in new_failure_tms]

    # Fixed - was failing, now passing
    fixed_tms = old_failed & new_passed
    fixed = [new_by_tms[tms] for tms in fixed_tms]

    # Still failing - failed in both
    still_failing_tms = old_failed & new_failed
    still_failing = [new_by_tms[tms] for tms in still_failing_tms]

    # New errors - error now but wasn't erroring before
    new_error_tms = new_error - old_error - old_failed
    new_errors = [new_by_tms[tms] for tms in new_error_tms]

    # Fixed errors - was erroring, now passing
    fixed_error_tms = old_error & new_passed
    fixed_errors = [new_by_tms[tms] for tms in fixed_error_tms]

    # Still erroring - error in both
    still_erroring_tms = old_error & new_error
    still_erroring = [new_by_tms[tms] for tms in still_erroring_tms]

    # New passes - passing now, wasn't in old report at all
    new_pass_tms = new_passed - old_passed - old_failed - old_error
    new_passes = [new_by_tms[tms] for tms in new_pass_tms]

    return CompareResult(
        new_failures=sorted(new_failures, key=lambda r: r.tms_number),
        fixed=sorted(fixed, key=lambda r: r.tms_number),
        still_failing=sorted(still_failing, key=lambda r: r.tms_number),
        new_errors=sorted(new_errors, key=lambda r: r.tms_number),
        fixed_errors=sorted(fixed_errors, key=lambda r: r.tms_number),
        still_erroring=sorted(still_erroring, key=lambda r: r.tms_number),
        new_passes=sorted(new_passes, key=lambda r: r.tms_number),
    )


def format_compare_result(result: CompareResult) -> str:
    """Format comparison result as readable text."""
    lines = []

    if result.new_failures:
        lines.append(f"NEW FAILURES ({len(result.new_failures)}):")
        for r in result.new_failures:
            lines.append(f"  - {r.tms_number}: {r.test_name}")
            if r.failure_reason:
                for reason_line in r.failure_reason.split("\n"):
                    lines.append(f"    {reason_line}")
        lines.append("")

    if result.new_errors:
        lines.append(f"NEW ERRORS ({len(result.new_errors)}):")
        for r in result.new_errors:
            lines.append(f"  ! {r.tms_number}: {r.test_name}")
            if r.failure_reason:
                for reason_line in r.failure_reason.split("\n"):
                    lines.append(f"    {reason_line}")
        lines.append("")

    if result.fixed:
        lines.append(f"FIXED ({len(result.fixed)}):")
        for r in result.fixed:
            lines.append(f"  + {r.tms_number}: {r.test_name}")
        lines.append("")

    if result.fixed_errors:
        lines.append(f"FIXED ERRORS ({len(result.fixed_errors)}):")
        for r in result.fixed_errors:
            lines.append(f"  + {r.tms_number}: {r.test_name}")
        lines.append("")

    if result.still_failing:
        lines.append(f"STILL FAILING ({len(result.still_failing)}):")
        for r in result.still_failing:
            lines.append(f"  ~ {r.tms_number}: {r.test_name}")
            if r.failure_reason:
                for reason_line in r.failure_reason.split("\n"):
                    lines.append(f"    {reason_line}")
        lines.append("")

    if result.still_erroring:
        lines.append(f"STILL ERRORING ({len(result.still_erroring)}):")
        for r in result.still_erroring:
            lines.append(f"  ~ {r.tms_number}: {r.test_name}")
            if r.failure_reason:
                for reason_line in r.failure_reason.split("\n"):
                    lines.append(f"    {reason_line}")
        lines.append("")

    # Summary
    lines.append("SUMMARY:")
    lines.append(f"  New failures: {len(result.new_failures)}")
    lines.append(f"  New errors: {len(result.new_errors)}")
    lines.append(f"  Fixed: {len(result.fixed)}")
    lines.append(f"  Fixed errors: {len(result.fixed_errors)}")
    lines.append(f"  Still failing: {len(result.still_failing)}")
    lines.append(f"  Still erroring: {len(result.still_erroring)}")

    return "\n".join(lines)
