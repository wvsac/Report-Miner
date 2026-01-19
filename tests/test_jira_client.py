"""Tests for Jira API client."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from reportminer.jira_client import JiraClient, get_jira_client, JiraClientError
from reportminer.models import TestResult, TestStatus


@pytest.fixture
def mock_config(monkeypatch):
    """Mock Jira configuration."""
    monkeypatch.setattr("reportminer.config.JIRA_BASE_URL", "https://test.atlassian.net")
    monkeypatch.setattr("reportminer.config.JIRA_EMAIL", "test@example.com")
    monkeypatch.setattr("reportminer.config.JIRA_TOKEN", "test-token")
    monkeypatch.setattr("reportminer.config.JIRA_STEPS_FIELD", "customfield_10100")


@pytest.fixture
def unconfigured_client(monkeypatch):
    """Create a client without credentials."""
    monkeypatch.setattr("reportminer.config.JIRA_BASE_URL", "https://test.atlassian.net")
    monkeypatch.setattr("reportminer.config.JIRA_EMAIL", "")
    monkeypatch.setattr("reportminer.config.JIRA_TOKEN", "")
    monkeypatch.setattr("reportminer.jira_client._client", None)
    return JiraClient()


@pytest.fixture
def configured_client(mock_config, monkeypatch, tmp_path):
    """Create a configured client with mocked cache."""
    monkeypatch.setattr("reportminer.cache.CACHE_DIR", tmp_path)
    monkeypatch.setattr("reportminer.jira_client._client", None)
    return JiraClient()


class TestJiraClientConfiguration:
    """Tests for Jira client configuration."""

    def test_is_configured_when_credentials_set(self, configured_client):
        assert configured_client.is_configured is True

    def test_is_not_configured_when_missing_email(self, unconfigured_client):
        assert unconfigured_client.is_configured is False

    def test_base_url_set(self, configured_client):
        assert configured_client.base_url == "https://test.atlassian.net"


class TestJiraClientAuth:
    """Tests for Jira authentication."""

    def test_generates_auth_header(self, configured_client):
        header = configured_client._get_auth_header()
        assert header.startswith("Basic ")

    def test_auth_header_contains_encoded_credentials(self, configured_client):
        import base64
        header = configured_client._get_auth_header()
        encoded_part = header.replace("Basic ", "")
        decoded = base64.b64decode(encoded_part).decode()
        assert "test@example.com" in decoded
        assert "test-token" in decoded


class TestJiraClientFetch:
    """Tests for Jira issue fetching."""

    def test_returns_none_when_not_configured(self, unconfigured_client):
        result = unconfigured_client.fetch_issue("TMS-123")
        assert result is None

    def test_uses_cache(self, configured_client):
        # Pre-populate cache
        configured_client.cache.set("TMS-123", {
            "key": "TMS-123",
            "summary": "Cached summary",
            "test_steps": None,
        })

        result = configured_client.fetch_issue("TMS-123")
        assert result.summary == "Cached summary"


class TestJiraClientEnrich:
    """Tests for result enrichment."""

    def test_enriches_results_when_configured(self, configured_client):
        # Pre-populate cache
        configured_client.cache.set("TMS-123", {
            "key": "TMS-123",
            "summary": "Test Summary",
            "test_steps": "Step 1\nStep 2",
        })

        results = [
            TestResult(
                tms_number="TMS_123",
                test_name="test",
                test_id="test",
                status=TestStatus.PASSED,
            )
        ]

        configured_client.enrich_results(results)
        assert results[0].jira_summary == "Test Summary"
        assert results[0].jira_test_steps == "Step 1\nStep 2"

    def test_skips_enrichment_when_not_configured(self, unconfigured_client):
        results = [
            TestResult(
                tms_number="TMS_123",
                test_name="test",
                test_id="test",
                status=TestStatus.PASSED,
            )
        ]

        unconfigured_client.enrich_results(results)
        assert results[0].jira_summary is None

    def test_calls_progress_callback(self, configured_client):
        configured_client.cache.set("TMS-123", {
            "key": "TMS-123",
            "summary": "Test",
            "test_steps": None,
        })

        results = [
            TestResult(
                tms_number="TMS_123",
                test_name="test",
                test_id="test",
                status=TestStatus.PASSED,
            )
        ]

        callback_calls = []
        def callback(current, total, name):
            callback_calls.append((current, total, name))

        configured_client.enrich_results(results, progress_callback=callback)
        assert len(callback_calls) >= 1


class TestADFConversion:
    """Tests for Atlassian Document Format conversion."""

    def test_converts_plain_text(self, configured_client):
        result = configured_client._extract_text_from_field("plain text")
        assert result == "plain text"

    def test_converts_simple_adf(self, configured_client):
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Hello world"}
                    ]
                }
            ]
        }
        result = configured_client._adf_to_text(adf)
        assert "Hello world" in result


class TestGetJiraClient:
    """Tests for singleton client getter."""

    def test_returns_same_instance(self, mock_config, monkeypatch):
        monkeypatch.setattr("reportminer.jira_client._client", None)
        client1 = get_jira_client()
        client2 = get_jira_client()
        assert client1 is client2
