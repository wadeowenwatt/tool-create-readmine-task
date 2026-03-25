"""
MCP Server - Redmine Issue Creator Tools

Chạy như một MCP server chuẩn (stdio transport).
Claude Desktop / Claude Code có thể kết nối và sử dụng các tools sau:

Tools:
  - analyze_markdown        : Phân tích markdown → subject + description
  - create_redmine_issue    : Tạo issue trên Redmine
  - get_redmine_config      : Lấy trackers, projects, user hiện tại
  - get_redmine_issue       : Lấy chi tiết issue theo ID

Usage (thêm vào claude_desktop_config.json):
  {
    "mcpServers": {
      "redmine-issue-creator": {
        "command": "python",
        "args": ["/path/to/redmine-issue-creator/mcp_server.py"],
        "env": {
          "ANTHROPIC_API_KEY": "...",
          "REDMINE_URL": "...",
          "REDMINE_API_KEY": "..."
        }
      }
    }
  }
"""
import json
import logging
import os
import sys
from typing import Any

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
)

from services.llm_service import analyze_markdown
from services.redmine_service import RedmineClient

# ---------------------------------------------------------------------------
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
server = Server("redmine-issue-creator")


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------
TOOLS = [
    Tool(
        name="analyze_markdown",
        description=(
            "Phân tích nội dung markdown để trích xuất subject (tiêu đề) và "
            "description (mô tả chi tiết) phù hợp cho Redmine issue. "
            "Sử dụng Claude Haiku để suy luận nội dung."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Nội dung file markdown cần phân tích",
                },
                "extra_context": {
                    "type": "string",
                    "description": "Ngữ cảnh bổ sung (tùy chọn)",
                    "default": "",
                },
            },
            "required": ["content"],
        },
    ),
    Tool(
        name="create_redmine_issue",
        description=(
            "Tạo một issue mới trên Redmine. Issue sẽ được assign cho "
            "user đang đăng nhập (theo API key trong .env)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Identifier của Redmine project (vd: 'my-project')",
                },
                "subject": {
                    "type": "string",
                    "description": "Tiêu đề issue (tối đa 255 ký tự)",
                },
                "description": {
                    "type": "string",
                    "description": "Mô tả chi tiết issue",
                },
                "tracker_id": {
                    "type": "integer",
                    "description": "ID của tracker (lấy từ get_redmine_config)",
                },
                "start_date": {
                    "type": "string",
                    "description": "Ngày bắt đầu theo định dạng YYYY-MM-DD",
                },
                "due_date": {
                    "type": "string",
                    "description": "Ngày kết thúc theo định dạng YYYY-MM-DD",
                },
                "parent_issue_id": {
                    "type": "integer",
                    "description": "ID của issue cha (tùy chọn)",
                },
                "priority_id": {
                    "type": "integer",
                    "description": "Priority ID: 1=Low, 2=Normal, 3=High (mặc định: 2)",
                    "default": 2,
                },
            },
            "required": [
                "project_id",
                "subject",
                "description",
                "tracker_id",
                "start_date",
                "due_date",
            ],
        },
    ),
    Tool(
        name="get_redmine_config",
        description=(
            "Lấy thông tin cấu hình từ Redmine: "
            "danh sách trackers, projects và thông tin user hiện tại."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="get_redmine_issue",
        description="Lấy thông tin chi tiết của một Redmine issue theo ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "issue_id": {
                    "type": "integer",
                    "description": "ID của issue cần xem",
                },
            },
            "required": ["issue_id"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
@server.list_tools()
async def list_tools() -> ListToolsResult:
    return ListToolsResult(tools=TOOLS)


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    """Dispatch tool calls."""
    try:
        if name == "analyze_markdown":
            return await _tool_analyze_markdown(arguments)
        elif name == "create_redmine_issue":
            return await _tool_create_issue(arguments)
        elif name == "get_redmine_config":
            return await _tool_get_config()
        elif name == "get_redmine_issue":
            return await _tool_get_issue(arguments)
        else:
            return _error(f"Tool không tồn tại: {name}")
    except Exception as e:
        logger.exception(f"Tool '{name}' failed")
        return _error(str(e))


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
async def _tool_analyze_markdown(args: dict) -> CallToolResult:
    content = args.get("content", "")
    if not content.strip():
        return _error("content không được để trống")

    extra_context = args.get("extra_context", "")
    result = analyze_markdown(content, extra_context)
    return _ok(result)


async def _tool_create_issue(args: dict) -> CallToolResult:
    required = ["project_id", "subject", "description", "tracker_id", "start_date", "due_date"]
    for field in required:
        if field not in args:
            return _error(f"Thiếu tham số bắt buộc: {field}")

    client = RedmineClient()
    user = client.get_current_user()

    issue = client.create_issue(
        project_id=args["project_id"],
        subject=args["subject"],
        description=args["description"],
        tracker_id=int(args["tracker_id"]),
        assigned_to_id=user["id"],
        start_date=args["start_date"],
        due_date=args["due_date"],
        parent_issue_id=args.get("parent_issue_id"),
        priority_id=int(args.get("priority_id", 2)),
    )
    return _ok(issue)


async def _tool_get_config() -> CallToolResult:
    client = RedmineClient()
    user = client.get_current_user()
    trackers = client.get_trackers()
    projects = client.get_projects()
    return _ok(
        {
            "user": {
                "id": user.get("id"),
                "name": f"{user.get('firstname','')} {user.get('lastname','')}".strip(),
                "login": user.get("login"),
            },
            "trackers": trackers,
            "projects": [
                {"id": p["id"], "identifier": p["identifier"], "name": p["name"]}
                for p in projects
            ],
        }
    )


async def _tool_get_issue(args: dict) -> CallToolResult:
    issue_id = args.get("issue_id")
    if not issue_id:
        return _error("Thiếu tham số: issue_id")
    client = RedmineClient()
    issue = client.get_issue(int(issue_id))
    return _ok(issue)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ok(data: Any) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))])


def _error(msg: str) -> CallToolResult:
    return CallToolResult(
        isError=True,
        content=[TextContent(type="text", text=f"Lỗi: {msg}")],
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    logger.info("MCP Server 'redmine-issue-creator' starting (stdio)...")
    async with stdio_server() as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
