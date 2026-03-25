"""
Redmine Service - Quản lý tương tác với Redmine REST API.
Hỗ trợ lấy danh sách trackers, projects, users và tạo issue.
"""
import os
import logging
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class RedmineClient:
    """Client giao tiếp với Redmine REST API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = (base_url or os.getenv("REDMINE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("REDMINE_API_KEY", "")

        if not self.base_url:
            raise EnvironmentError("REDMINE_URL chưa được cấu hình trong file .env")
        if not self.api_key:
            raise EnvironmentError("REDMINE_API_KEY chưa được cấu hình trong file .env")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Redmine-API-Key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Thực hiện GET request, raise exception nếu lỗi."""
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Không thể kết nối Redmine tại: {self.base_url}")
        except requests.exceptions.Timeout:
            raise TimeoutError("Redmine API timeout sau 15 giây")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Redmine API lỗi {resp.status_code}: {resp.text[:200]}")

    def _post(self, endpoint: str, data: dict) -> dict:
        """Thực hiện POST request, raise exception nếu lỗi."""
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.post(url, json=data, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Không thể kết nối Redmine tại: {self.base_url}")
        except requests.exceptions.Timeout:
            raise TimeoutError("Redmine API timeout sau 15 giây")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Redmine API lỗi {resp.status_code}: {resp.text[:200]}")

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_trackers(self) -> list[dict]:
        """Lấy danh sách trackers (Bug, Feature, Task...)."""
        data = self._get("/trackers.json")
        return data.get("trackers", [])

    def get_projects(self) -> list[dict]:
        """Lấy danh sách projects mà user có quyền truy cập."""
        all_projects = []
        offset = 0
        limit = 100
        while True:
            data = self._get("/projects.json", params={"offset": offset, "limit": limit})
            projects = data.get("projects", [])
            all_projects.extend(projects)
            total_count = data.get("total_count", 0)
            offset += limit
            if offset >= total_count:
                break
        return all_projects

    def get_current_user(self) -> dict:
        """Lấy thông tin user đang đăng nhập."""
        data = self._get("/users/current.json")
        return data.get("user", {})

    def get_project_members(self, project_id: str) -> list[dict]:
        """Lấy danh sách thành viên của project."""
        data = self._get(f"/projects/{project_id}/memberships.json")
        memberships = data.get("memberships", [])
        members = []
        for m in memberships:
            user = m.get("user")
            if user:
                members.append({"id": user["id"], "name": user["name"]})
        return members

    # ------------------------------------------------------------------
    # Issue
    # ------------------------------------------------------------------

    def create_issue(
        self,
        project_id: str,
        subject: str,
        description: str,
        tracker_id: int,
        assigned_to_id: int,
        start_date: str,
        due_date: str,
        parent_issue_id: Optional[int] = None,
        priority_id: int = 2,
    ) -> dict:
        """
        Tạo Redmine issue mới.

        Args:
            project_id:       Identifier của project (vd: "my-project")
            subject:          Tiêu đề issue
            description:      Mô tả chi tiết
            tracker_id:       ID của tracker (Bug=1, Feature=2, Task=3...)
            assigned_to_id:   ID user được assign
            start_date:       Ngày bắt đầu (YYYY-MM-DD)
            due_date:         Ngày kết thúc (YYYY-MM-DD)
            parent_issue_id:  ID issue cha (tùy chọn)
            priority_id:      ID priority (1=Low, 2=Normal, 3=High)

        Returns:
            dict chứa thông tin issue vừa tạo (id, subject, url...)
        """
        issue_data: dict = {
            "project_id": project_id,
            "subject": subject,
            "description": description,
            "tracker_id": tracker_id,
            "assigned_to_id": assigned_to_id,
            "start_date": start_date,
            "due_date": due_date,
            "priority_id": priority_id,
        }

        if parent_issue_id:
            issue_data["parent_issue_id"] = parent_issue_id

        payload = {"issue": issue_data}
        logger.info(f"Creating Redmine issue: {subject[:60]}...")

        result = self._post("/issues.json", payload)
        issue = result.get("issue", {})

        issue_url = f"{self.base_url}/issues/{issue.get('id')}"
        logger.info(f"Issue created: #{issue.get('id')} - {issue_url}")

        return {
            "id": issue.get("id"),
            "subject": issue.get("subject"),
            "url": issue_url,
            "status": issue.get("status", {}).get("name", "New"),
            "tracker": issue.get("tracker", {}).get("name", ""),
            "assigned_to": issue.get("assigned_to", {}).get("name", ""),
        }

    def get_issue(self, issue_id: int) -> dict:
        """Lấy thông tin chi tiết một issue."""
        data = self._get(f"/issues/{issue_id}.json")
        return data.get("issue", {})
