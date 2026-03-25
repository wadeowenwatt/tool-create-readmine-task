"""
FastAPI Web Server - Cung cấp REST API và phục vụ GUI cho Redmine Issue Creator.

Endpoints:
  GET  /                    - Phục vụ giao diện chính
  GET  /api/health          - Health check
  GET  /api/config          - Lấy trackers, projects, user hiện tại
  POST /api/analyze         - Upload markdown → LLM phân tích → subject + description
  POST /api/issues          - Tạo Redmine issue
  GET  /api/issues/{id}     - Lấy thông tin issue theo ID
"""
import logging
import os
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from services.llm_service import analyze_markdown
from services.redmine_service import RedmineClient

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Redmine Issue Creator",
    description="Tự động tạo Redmine issue từ file markdown với Claude Haiku",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_redmine() -> RedmineClient:
    """Tạo RedmineClient, raise HTTPException nếu chưa cấu hình."""
    try:
        return RedmineClient()
    except EnvironmentError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class CreateIssueRequest(BaseModel):
    project_id: str = Field(..., description="Identifier của Redmine project")
    tracker_id: int = Field(..., description="ID của tracker")
    subject: str = Field(..., min_length=1, max_length=255, description="Tiêu đề issue")
    description: str = Field(..., description="Mô tả issue")
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Ngày bắt đầu (YYYY-MM-DD)")
    due_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Ngày kết thúc (YYYY-MM-DD)")
    parent_issue_id: Optional[int] = Field(None, description="ID issue cha")
    priority_id: int = Field(2, description="Priority ID (1=Low, 2=Normal, 3=High)")


class AnalyzeResponse(BaseModel):
    issues: list[dict]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_ui():
    """Phục vụ giao diện web chính."""
    index_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))


@app.get("/api/health", tags=["System"])
async def health():
    """Kiểm tra server đang chạy."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/config", tags=["Config"])
async def get_config():
    """
    Trả về dữ liệu cần thiết để render form:
    - user: thông tin user hiện tại
    - trackers: danh sách trackers
    - projects: danh sách projects
    """
    redmine = get_redmine()
    try:
        user = redmine.get_current_user()
        trackers = redmine.get_trackers()
        projects = redmine.get_projects()
        return {
            "user": {
                "id": user.get("id"),
                "name": f"{user.get('firstname', '')} {user.get('lastname', '')}".strip(),
                "login": user.get("login"),
            },
            "trackers": trackers,
            "projects": [
                {"id": p["id"], "identifier": p["identifier"], "name": p["name"]}
                for p in projects
            ],
        }
    except (ConnectionError, TimeoutError, RuntimeError) as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/api/analyze", response_model=AnalyzeResponse, tags=["Analysis"])
async def analyze_file(
    file: UploadFile = File(...),
    extra_context: str = Form(""),
):
    """
    Upload file markdown → Claude Haiku phân tích → trả về subject + description.

    - **file**: File .md (UTF-8)
    - **extra_context**: Ngữ cảnh bổ sung (tùy chọn)
    """
    if not file.filename.endswith((".md", ".markdown", ".txt")):
        raise HTTPException(
            status_code=400,
            detail="Chỉ hỗ trợ file .md, .markdown, .txt",
        )

    max_size = 100 * 1024  # 100 KB
    raw = await file.read()
    if len(raw) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File quá lớn (tối đa {max_size // 1024} KB)",
        )

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File không phải UTF-8")

    if not content.strip():
        raise HTTPException(status_code=400, detail="File rỗng")

    try:
        issues = analyze_markdown(content, extra_context)
        return AnalyzeResponse(issues=issues)
    except EnvironmentError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("LLM analysis failed")
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích: {e}")


@app.post("/api/issues", tags=["Issues"])
async def create_issue(req: CreateIssueRequest):
    """
    Tạo Redmine issue mới.
    Issue sẽ được assign cho chính user đang đăng nhập.
    """
    redmine = get_redmine()
    try:
        user = redmine.get_current_user()
        issue = redmine.create_issue(
            project_id=req.project_id,
            subject=req.subject,
            description=req.description,
            tracker_id=req.tracker_id,
            assigned_to_id=user["id"],
            start_date=req.start_date,
            due_date=req.due_date,
            parent_issue_id=req.parent_issue_id,
            priority_id=req.priority_id,
        )
        return issue
    except (ConnectionError, TimeoutError, RuntimeError) as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Failed to create issue")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/issues/{issue_id}", tags=["Issues"])
async def get_issue(issue_id: int):
    """Lấy thông tin chi tiết issue theo ID."""
    redmine = get_redmine()
    try:
        return redmine.get_issue(issue_id)
    except (ConnectionError, TimeoutError, RuntimeError) as e:
        raise HTTPException(status_code=503, detail=str(e))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting Redmine Issue Creator at http://{host}:{port}")
    uvicorn.run("server:app", host=host, port=port, reload=True)
