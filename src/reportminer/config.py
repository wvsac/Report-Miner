"""Configuration via environment variables."""

import os
from pathlib import Path

# Jira configuration
JIRA_BASE_URL = os.environ.get("MINE_JIRA_URL", "")
JIRA_TOKEN = os.environ.get("MINE_JIRA_TOKEN", "")
JIRA_EMAIL = os.environ.get("MINE_JIRA_EMAIL", "")

# Custom field ID for test steps (e.g., customfield_10100)
JIRA_STEPS_FIELD = os.environ.get("MINE_JIRA_STEPS_FIELD", "")

# Spinner style: "unicode" for fancy stars, "ascii" for basic characters
SPINNER_STYLE = os.environ.get("MINE_SPINNER", "unicode")

# Cache configuration (follows XDG_CACHE_HOME convention)
CACHE_DIR = Path(os.environ.get(
    "MINE_CACHE_DIR",
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "reportminer"
))

CACHE_TTL_HOURS = int(os.environ.get("MINE_CACHE_TTL", "24"))

# Default CLI options
DEFAULT_FORMAT = os.environ.get("MINE_FORMAT", "raw")
DEFAULT_STATUS = os.environ.get("MINE_STATUS", "failed")

# Rerun command template - use {tests} placeholder for test names
DEFAULT_RERUN_CMD = os.environ.get("MINE_RERUN_CMD", 'pytest -k "{tests}"')
