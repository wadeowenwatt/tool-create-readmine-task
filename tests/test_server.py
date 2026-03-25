"""
Tests cho FastAPI server endpoints.
Sử dụng TestClient của FastAPI.
"""
import json
import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("REDMINE_URL", "https://redmine.example.com")
    monkeypatch.setenv("REDMINE_API_KEY", "test-redmine-key")


@pytest.fixture
def app_client():
    from server import app
    return TestClient(app)


FAKE_USER    = {"id": 1, "firstname": "Alice", "lastname": "Dev", "login": "alice"}
FAKE_TRACKERS = [{"id": 1, "name": "Bug"}, {"id": 3, "name": "Task"}]
FAKE_PROJECTS = [{"id": 1, "identifier": "proj-a", "name": "Project A"}]


class TestHealthEndpoint:
    def test_health_ok(self, app_client):
        r = app_client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestConfigEndpoint:
    def test_returns_config(self, app_client):
        with patch("server.RedmineClient") as mock_cls:
            inst = mock_cls.return_value
            inst.get_current_user.return_value = FAKE_USER
            inst.get_trackers.return_value = FAKE_TRACKERS
            inst.get_projects.return_value = FAKE_PROJECTS

            r = app_client.get("/api/config")

        assert r.status_code == 200
        data = r.json()
        assert data["user"]["login"] == "alice"
        assert len(data["trackers"]) == 2
        assert len(data["projects"]) == 1

    def test_503_on_connection_error(self, app_client):
        with patch("server.RedmineClient") as mock_cls:
            inst = mock_cls.return_value
            inst.get_current_user.side_effect = ConnectionError("Cannot connect")
            r = app_client.get("/api/config")
        assert r.status_code == 503


class TestAnalyzeEndpoint:
    def test_analyze_success(self, app_client):
        expected = {"subject": "Test Subject", "description": "Test Description"}
        with patch("server.analyze_markdown", return_value=expected):
            r = app_client.post(
                "/api/analyze",
                files={"file": ("test.md", b"# Hello\nTest content", "text/markdown")},
                data={"extra_context": ""},
            )
        assert r.status_code == 200
        assert r.json()["subject"] == "Test Subject"

    def test_rejects_non_markdown_file(self, app_client):
        r = app_client.post(
            "/api/analyze",
            files={"file": ("test.pdf", b"PDF content", "application/pdf")},
            data={"extra_context": ""},
        )
        assert r.status_code == 400

    def test_rejects_empty_file(self, app_client):
        r = app_client.post(
            "/api/analyze",
            files={"file": ("test.md", b"   \n  ", "text/markdown")},
            data={"extra_context": ""},
        )
        assert r.status_code == 400

    def test_503_on_missing_api_key(self, app_client):
        with patch("server.analyze_markdown", side_effect=EnvironmentError("ANTHROPIC_API_KEY")):
            r = app_client.post(
                "/api/analyze",
                files={"file": ("test.md", b"# Content", "text/markdown")},
                data={"extra_context": ""},
            )
        assert r.status_code == 503


class TestCreateIssueEndpoint:
    VALID_PAYLOAD = {
        "project_id": "proj-a",
        "tracker_id": 3,
        "subject": "Fix login bug",
        "description": "Users cannot login with OAuth",
        "start_date": "2025-01-01",
        "due_date": "2025-01-31",
    }

    def test_creates_issue(self, app_client):
        fake_issue = {"id": 123, "subject": "Fix login bug", "url": "https://redmine.example.com/issues/123",
                      "status": "New", "tracker": "Task", "assigned_to": "Alice Dev"}
        with patch("server.RedmineClient") as mock_cls:
            inst = mock_cls.return_value
            inst.get_current_user.return_value = FAKE_USER
            inst.create_issue.return_value = fake_issue

            r = app_client.post("/api/issues", json=self.VALID_PAYLOAD)

        assert r.status_code == 200
        assert r.json()["id"] == 123

    def test_assigns_to_current_user(self, app_client):
        """Issue phải được assign cho user hiện tại."""
        with patch("server.RedmineClient") as mock_cls:
            inst = mock_cls.return_value
            inst.get_current_user.return_value = FAKE_USER
            inst.create_issue.return_value = {"id": 1, "subject": "S", "url": "u",
                                               "status": "New", "tracker": "T", "assigned_to": "A"}
            app_client.post("/api/issues", json=self.VALID_PAYLOAD)

            call_kwargs = inst.create_issue.call_args[1]
            assert call_kwargs["assigned_to_id"] == FAKE_USER["id"]

    def test_rejects_missing_required_field(self, app_client):
        payload = dict(self.VALID_PAYLOAD)
        del payload["subject"]
        r = app_client.post("/api/issues", json=payload)
        assert r.status_code == 422

    def test_rejects_invalid_date_format(self, app_client):
        payload = dict(self.VALID_PAYLOAD)
        payload["start_date"] = "01/01/2025"  # wrong format
        r = app_client.post("/api/issues", json=payload)
        assert r.status_code == 422
