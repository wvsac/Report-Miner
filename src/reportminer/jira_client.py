"""Jira API client for fetching issue data."""

import base64
from typing import Optional, Callable

import httpx

from .config import JIRA_BASE_URL, JIRA_TOKEN, JIRA_EMAIL, JIRA_STEPS_FIELD
from .cache import FileCache
from .models import JiraIssueData, TestResult


class JiraClientError(Exception):
    """Error communicating with Jira API."""
    pass


class JiraClient:
    """Client for Jira REST API v3 (Cloud)."""

    def __init__(self):
        self.base_url = JIRA_BASE_URL.rstrip("/")
        self.email = JIRA_EMAIL
        self.token = JIRA_TOKEN
        self.steps_field = JIRA_STEPS_FIELD
        self.cache = FileCache("jira")
        self._client: Optional[httpx.Client] = None

    @property
    def is_configured(self) -> bool:
        """Check if Jira credentials are configured."""
        return bool(self.base_url and self.email and self.token)

    def _get_auth_header(self) -> str:
        """Generate Basic auth header for Jira Cloud."""
        credentials = f"{self.email}:{self.token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _get_client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=f"{self.base_url}/rest/api/3",
                headers={
                    "Authorization": self._get_auth_header(),
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    def close(self):
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def fetch_issue(self, issue_key: str) -> Optional[JiraIssueData]:
        """Fetch issue data from Jira, using cache if available."""
        # Check cache first
        cached = self.cache.get(issue_key)
        if cached:
            return JiraIssueData(**cached)

        if not self.is_configured:
            return None

        try:
            # Build fields list
            fields = ["summary"]
            if self.steps_field:
                fields.append(self.steps_field)

            client = self._get_client()
            response = client.get(
                f"/issue/{issue_key}",
                params={"fields": ",".join(fields)},
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            # Extract fields
            fields_data = data.get("fields", {})
            summary = fields_data.get("summary", "")

            # Extract test steps from custom field
            test_steps = None
            if self.steps_field:
                steps_data = fields_data.get(self.steps_field)
                if steps_data:
                    test_steps = self._extract_text_from_field(steps_data)

            issue_data = JiraIssueData(
                key=issue_key,
                summary=summary,
                test_steps=test_steps,
            )

            # Cache the result
            self.cache.set(issue_key, {
                "key": issue_key,
                "summary": summary,
                "test_steps": test_steps,
            })

            return issue_data

        except httpx.HTTPError as e:
            raise JiraClientError(f"Failed to fetch {issue_key}: {e}") from e

    def _extract_text_from_field(self, field_value) -> str:
        """Extract plain text from Jira field (handles ADF and plain text)."""
        if isinstance(field_value, str):
            return field_value

        if isinstance(field_value, dict):
            return self._adf_to_text(field_value)

        return str(field_value)

    def _adf_to_text(self, adf: dict, depth: int = 0) -> str:
        """Convert Atlassian Document Format to plain text."""
        if not isinstance(adf, dict):
            return ""

        content = adf.get("content", [])
        node_type = adf.get("type", "")

        if node_type == "text":
            return adf.get("text", "")

        parts = []
        for node in content:
            parts.append(self._adf_to_text(node, depth + 1))

        text = "".join(parts)

        # Add formatting based on node type
        if node_type == "paragraph":
            text = text.strip() + "\n"
        elif node_type in ("orderedList", "bulletList"):
            text = text + "\n"
        elif node_type == "listItem":
            text = "- " + text.strip() + "\n"
        elif node_type == "heading":
            text = text.strip() + "\n"

        return text

    def enrich_results(
        self,
        results: list[TestResult],
        progress_callback: Optional[Callable] = None,
    ) -> list[TestResult]:
        """Enrich test results with Jira data."""
        if not self.is_configured:
            return results

        total = len(results)
        for i, result in enumerate(results):
            if progress_callback:
                progress_callback(i, total, result.tms_number)

            issue_key = result.tms_jira_format
            try:
                issue_data = self.fetch_issue(issue_key)
                if issue_data:
                    result.jira_summary = issue_data.summary
                    result.jira_test_steps = issue_data.test_steps
            except JiraClientError:
                # Skip failed fetches, continue with others
                pass

        if progress_callback:
            progress_callback(total, total, "complete")

        return results


# Singleton instance
_client: Optional[JiraClient] = None


def get_jira_client() -> JiraClient:
    """Get the singleton Jira client instance."""
    global _client
    if _client is None:
        _client = JiraClient()
    return _client
