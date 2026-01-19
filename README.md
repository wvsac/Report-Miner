<p align="center">
  <img src="reportminer_logo.png" alt="Report Miner Logo" width="400">
</p>

<h1 align="center">Report Miner</h1>

<p align="center">
  <strong>Mine pytest-html reports for test results</strong><br>
  Extract, filter, analyze test data with multiple output formats and interactive TUI viewer
</p>

---

## Features

| Feature | Description |
|---------|-------------|
| **Parse Reports** | Single files, multiple files, or entire directories |
| **Filter Results** | By status: failed, passed, skipped, error, all |
| **Multiple Formats** | Raw, pytest, detailed, Jira, Confluence wiki |
| **Compare Reports** | Find new failures, fixed tests, regressions |
| **Interactive TUI** | Browse tests with keyboard, colored logs |
| **Jira Integration** | Fetch test titles and steps via API |
| **Rerun Commands** | Generate pytest commands for failed tests |

---

## Installation

```bash
# Using pipx (recommended)
pipx install /path/to/reportminer

# Using pip
pip install /path/to/reportminer
```

---

## Quick Start

```bash
# Get failed test TMS numbers
mine report.html

# Interactive TUI viewer
mine --view report.html

# Generate pytest rerun command
mine --rerun report.html

# Compare two reports
mine --diff old.html new.html
```

---

## Output Formats

```bash
mine -f <format> report.html
```

| Format | Output |
|--------|--------|
| `raw` | `TMS_123, TMS_456, TMS_789` |
| `pytest` | `TMS_123 or TMS_456 or TMS_789` |
| `names` | Test function names |
| `full` | Full test paths |
| `detailed` | Table with TMS, status, name, reason |
| `jira` | Jira URLs |
| `jira-md` | `[TMS-123: title](url)` |
| `wiki` | `[TMS-123: title\|url]` |

### Group by Failure Reason

```bash
mine -f pytest --group report.html
```

```
### [3 tests] AssertionError: Connection timeout
  TMS_123 or TMS_456 or TMS_789

### [2 tests] ValueError: Invalid response
  TMS_111 or TMS_222
```

---

## Interactive TUI

```bash
mine --view report.html
```

### Navigation

| Key | Action |
|-----|--------|
| `↑` `↓` | Navigate tests / Scroll logs |
| `j` `k` | Scroll logs (vim-style) |
| `Enter` | Focus log panel for scrolling |
| `Tab` | Switch between list and detail |
| `l` | Toggle fullscreen |
| `Esc` | Back / Clear search / Quit |
| `q` | Quit |

### Filtering

| Key | Action |
|-----|--------|
| `/` | Search |
| `a` | All tests |
| `f` | Failed |
| `p` | Passed |
| `s` | Skipped |
| `e` | Errors |
| `m` | Marked |

### Actions

| Key | Action |
|-----|--------|
| `Space` | Mark/unmark test |
| `y` | Copy marked TMS numbers |
| `c` | Copy current test |
| `o` | Open in Jira |

### Log Colors

- **ERROR/FATAL** — Red
- **WARN** — Yellow
- **INFO** — Green
- **DEBUG** — Blue
- **TRACE** — Cyan

---

## Compare Reports

```bash
mine --diff old_report.html new_report.html
```

```
NEW FAILURES (2):
  - TMS_104658: test_network_profile

FIXED (1):
  + TMS_33405: test_certificates

STILL FAILING (5):
  ~ TMS_104207: test_ech_profile

SUMMARY: 2 new, 1 fixed, 5 still failing
```

---

## All Options

```
Usage: mine [OPTIONS] [INPUT_PATHS]...

Options:
  -f, --format FORMAT   Output format (raw, pytest, names, full, detailed, jira, jira-md, wiki)
  -s, --status STATUS   Filter: failed, passed, skipped, error, all
  -g, --group           Group by failure reason
  -r, --rerun           Generate pytest rerun command
  -o, --output FILE     Export to file
  -u, --unique          Remove duplicates (default)
  -S, --sort            Sort alphabetically
  -c, --count           Show count only
  -v, --view            Interactive TUI
  --copy                Copy to clipboard
  --diff                Compare two reports
  --clear-cache         Clear Jira cache
  --help                Show help
```

---

## Configuration

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# Jira integration (required for jira-md/wiki formats)
export MINE_JIRA_URL="https://mycompany.atlassian.net"
export MINE_JIRA_EMAIL="your-email@company.com"
export MINE_JIRA_TOKEN="your-api-token"

# Optional settings
export MINE_CACHE_TTL="24"              # Cache TTL in hours
export MINE_FORMAT="raw"                # Default format
export MINE_STATUS="failed"             # Default status filter
export MINE_SPINNER="unicode"           # "unicode" or "ascii"
export MINE_RERUN_CMD='pytest -k "{tests}"'  # Rerun command template
```

### Jira Setup

1. Get API token: https://id.atlassian.com/manage-profile/security/api-tokens
2. Add email + token to your shell config

---

## Examples

```bash
# Basic usage
mine report.html
# Output: TMS_104658, TMS_104207, TMS_100839

# Rerun failed tests
mine --rerun report.html
# Output: pytest -k "test_network or test_api"

# Copy Jira links
mine -f jira --copy report.html

# View interactively
mine --view report.html

# Compare reports
mine --diff yesterday.html today.html
```

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```
