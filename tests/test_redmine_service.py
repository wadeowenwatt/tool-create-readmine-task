"""
Tests cho Redmine Service – kiểm tra tương tác với Redmine REST API.
Sử dụng responses library để mock HTTP calls.
"""
import os
import sys
import pytest
import responses as resp_lib
import requests

# Đảm bảo import từ thư mục gốc project
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.redmine_service import RedmineClient

REDMINE_URL  = "https://redmine.example.com"
REDMINE_KEY  = "test-api-key-12345"


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("REDMINE_URL", REDMINE_URL)
    monkeypatch.setenv("REDMINE_API_KEY", REDMINE_KEY)


@pytest.fixture
def client():
    return RedmineClient()


FAKE_USER = {
    "user": {
        "id": 42,
        "login": "testuser",
        "firstname": "Test",
        "lastname": "User",
        "mail": "test@example.com",
    }
}

FAKE_TRACKERS = {
    "trackers": [
        {"id": 1, "name": "Bug"},
        {"id": 2, "name": "Feature"},
        {"id": 3, "name": "Task"},
    ]
}

FAKE_PROJECTS = {
    "total_count": 2,
    "projects": [
        {"id": 1, "identifier": "project-a", "name": "Project A"},
        {"id": 2, "identifier": "project-b", "name": "Project B"},
    ],
}

FAKE_ISSUE_CREATED = {
    "issue": {
        "id": 999,
        "subject": "Test Issue Subject",
        "status": {"id": 1, "name": "New"},
        "tracker": {"id": 3, "name": "Task"},
        "assigned_to": {"id": 42, "name": "Test User"},
    }
}

FAKE_ISSUE_GET = {
    "issue": {
        "id": 999,
        "subject": "Test Issue Subject",
        "description": "Detailed description",
        "status": {"id": 1, "name": "New"},
    }
}


# ──────────────────────────────────────────────────────────────────────────────
# Initialisation tests
# ──────────────────────────────────────────────────────────────────────────────

class TestRedmineClientInit:

    def test_raises_if_no_url(self, monkeypatch):
        monkeypatch.delenv("REDMINE_URL")
        with pytest.raises(EnvironmentError, match="REDMINE_URL"):
            RedmineClient()

    def test_raises_if_no_api_key(self, monkeypatch):
        monkeypatch.delenv("REDMINE_API_KEY")
        with pytest.raises(EnvironmentError, match="REDMINE_API_KEY"):
            RedmineClient()

    def test_strips_trailing_slash(self):
        c = RedmineClient(base_url="https://example.com/", api_key="key")
        assert not c.base_url.endswith("/")

    def test_custom_url_and_key(self):
        c = RedmineClient(base_url="https://custom.com", api_key="mykey")
        assert c.base_url == "https://custom.com"
        assert c.api_key == "mykey"


# ──────────────────────────────────────────────────────────────────────────────
# get_current_user
# ──────────────────────────────────────────────────────────────────────────────

class TestGetCurrentUser:

    @resp_lib.activate
    def test_returns_user_dict(self, client):
        resp_lib.add(resp_lib.GET, f"{REDMINE_URL}/users/current.json", json=FAKE_USER)
        user = client.get_current_user()
        assert user["id"] == 42
        assert user["login"] == "testuser"

    @resp_lib.activate
    def test_sends_api_key_header(self, client):
        resp_lib.add(resp_lib.GET, f"{REDMINE_URL}/users/current.json", json=FAKE_USER)
        client.get_current_user()
        assert resp_lib.calls[0].request.headers["X-Redmine-API-Key"] == REDMINE_KEY

    @resp_lib.activate
    def test_raises_on_401(self, client):
        resp_lib.add(resp_lib.GET, f"{REDMINE_URL}/users/current.json", status=401, body="Unauthorized")
        with pytest.raises(RuntimeError, match="401"):
            client.get_current_user()


# ──────────────────────────────────────────────────────────────────────────────
# get_trackers
# ──────────────────────────────────────────────────────────────────────────────

class TestGetTrackers:

    @resp_lib.activate
    def test_returns_list_of_trackers(self, client):
        resp_lib.add(resp_lib.GET, f"{REDMINE_URL}/trackers.json", json=FAKE_TRACKERS)
        trackers = client.get_trackers()
        assert len(trackers) == 3
        assert trackers[0]["name"] == "Bug"

    @resp_lib.activate
    def test_returns_empty_list_on_empty_response(self, client):
        resp_lib.add(resp_lib.GET, f"{REDMINE_URL}/trackers.json", json={"trackers": []})
        assert client.get_trackers() == []


# ──────────────────────────────────────────────────────────────────────────────
# get_projects
# ──────────────────────────────────────────────────────────────────────────────

class TestGetProjects:

    @resp_lib.activate
    def test_returns_all_projects(self, client):
        resp_lib.add(
            resp_lib.GET, f"{REDMINE_URL}/projects.json",
            json=FAKE_PROJECTS
        )
        projects = client.get_projects()
        assert len(projects) == 2
        assert projects[0]["identifier"] == "project-a"

    @resp_lib.activate
    def test_paginates_correctly(self, client):
        """Phải gọi nhiều trang nếu total_count > limit."""
        page1 = {
            "total_count": 150,
            "projects": [{"id": i, "identifier": f"p{i}", "name": f"Project {i}"} for i in range(100)],
        }
        page2 = {
            "total_count": 150,
            "projects": [{"id": i, "identifier": f"p{i}", "name": f"Project {i}"} for i in range(100, 150)],
        }
        resp_lib.add(resp_lib.GET, f"{REDMINE_URL}/projects.json", json=page1)
        resp_lib.add(resp_lib.GET, f"{REDMINE_URL}/projects.json", json=page2)

        projects = client.get_projects()
        assert len(projects) == 150


# ──────────────────────────────────────────────────────────────────────────────
# create_issue
# ──────────────────────────────────────────────────────────────────────────────

class TestCreateIssue:

    @resp_lib.activate
    def test_creates_issue_successfully(self, client):
        resp_lib.add(resp_lib.POST, f"{REDMINE_URL}/issues.json", json=FAKE_ISSUE_CREATED, status=201)
        issue = client.create_issue(
            project_id="project-a",
            subject="Test Issue Subject",
            description="Test description",
            tracker_id=3,
            assigned_to_id=42,
            start_date="2025-01-01",
            due_date="2025-01-31",
        )
        assert issue["id"] == 999
        assert "url" in issue
        assert "999" in issue["url"]

    @resp_lib.activate
    def test_includes_parent_issue_id_when_provided(self, client):
        resp_lib.add(resp_lib.POST, f"{REDMINE_URL}/issues.json", json=FAKE_ISSUE_CREATED, status=201)
        client.create_issue(
            project_id="project-a",
            subject="Child Issue",
            description="desc",
            tracker_id=3,
            assigned_to_id=42,
            start_date="2025-01-01",
            due_date="2025-01-31",
            parent_issue_id=500,
        )
        import json
        body = json.loads(resp_lib.calls[0].request.body)
        assert body["issue"]["parent_issue_id"] == 500

    @resp_lib.activate
    def test_omits_parent_issue_id_when_none(self, client):
        resp_lib.add(resp_lib.POST, f"{REDMINE_URL}/issues.json", json=FAKE_ISSUE_CREATED, status=201)
        client.create_issue(
            project_id="project-a",
            subject="Root Issue",
            description="desc",
            tracker_id=3,
            assigned_to_id=42,
            start_date="2025-01-01",
            due_date="2025-01-31",
        )
        import json
        body = json.loads(resp_lib.calls[0].request.body)
        assert "parent_issue_id" not in body["issue"]

    @resp_lib.activate
    def test_returns_url_with_issue_id(self, client):
        resp_lib.add(resp_lib.POST, f"{REDMINE_URL}/issues.json", json=FAKE_ISSUE_CREATED, status=201)
        issue = client.create_issue(
            project_id="p", subject="S", description="D",
            tracker_id=1, assigned_to_id=1,
            start_date="2025-01-01", due_date="2025-01-31"
        )
        assert issue["url"] == f"{REDMINE_URL}/issues/999"

    @resp_lib.activate
    def test_raises_on_422_error(self, client):
        resp_lib.add(
            resp_lib.POST, f"{REDMINE_URL}/issues.json",
            json={"errors": ["Subject cannot be blank"]}, status=422
        )
        with pytest.raises(RuntimeError, match="422"):
            client.create_issue(
                project_id="p", subject="", description="",
                tracker_id=1, assigned_to_id=1,
                start_date="2025-01-01", due_date="2025-01-31"
            )

    @resp_lib.activate
    def test_raises_on_connection_error(self, client):
        resp_lib.add(
            resp_lib.POST, f"{REDMINE_URL}/issues.json",
            body=requests.exceptions.ConnectionError("Connection refused")
        )
        with pytest.raises(ConnectionError):
            client.create_issue(
                project_id="p", subject="S", description="D",
                tracker_id=1, assigned_to_id=1,
                start_date="2025-01-01", due_date="2025-01-31"
            )


# ──────────────────────────────────────────────────────────────────────────────
# get_issue
# ──────────────────────────────────────────────────────────────────────────────

class TestGetIssue:

    @resp_lib.activate
    def test_returns_issue_details(self, client):
        resp_lib.add(resp_lib.GET, f"{REDMINE_URL}/issues/999.json", json=FAKE_ISSUE_GET)
        issue = client.get_issue(999)
        assert issue["id"] == 999
        assert issue["subject"] == "Test Issue Subject"

    @resp_lib.activate
    def test_raises_on_404(self, client):
        resp_lib.add(resp_lib.GET, f"{REDMINE_URL}/issues/9999.json", status=404, body="Not Found")
        with pytest.raises(RuntimeError, match="404"):
            client.get_issue(9999)
