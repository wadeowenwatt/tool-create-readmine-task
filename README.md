# Redmine Issue Creator

> Tự động tạo Redmine issue từ file Markdown sử dụng **Claude Haiku** để phân tích nội dung.

---

## ✨ Tính năng

| Tính năng | Mô tả |
|-----------|-------|
| 📄 Upload Markdown | Kéo thả hoặc chọn file `.md` |
| 🤖 AI Phân tích | Claude Haiku 4.5 tự động trích xuất Subject & Description |
| 📋 Form thông minh | Chọn Project, Tracker, Priority, Dates |
| 🔗 Parent Task | Hỗ trợ liên kết issue cha |
| 👤 Auto-assign | Tự động assign cho chính mình |
| 🔌 MCP Server | Tích hợp Claude Desktop / Claude Code |

---

## 📁 Cấu trúc dự án

```
redmine-issue-creator/
├── server.py              # FastAPI web server + REST API
├── mcp_server.py          # MCP server cho Claude Desktop/Code
├── services/
│   ├── llm_service.py     # Tích hợp Claude Haiku (Anthropic SDK)
│   └── redmine_service.py # Redmine REST API client
├── static/
│   ├── index.html         # Giao diện web
│   ├── style.css          # Stylesheet
│   └── app.js             # Frontend logic
├── tests/
│   ├── test_llm_service.py
│   ├── test_redmine_service.py
│   └── test_server.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🚀 Cài đặt & Chạy nhanh

### 1. Yêu cầu hệ thống

- Python **3.11+**
- pip

### 2. Clone & Cài đặt dependencies

```bash
cd redmine-issue-creator
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 3. Cấu hình file `.env`

```bash
cp .env.example .env
```

Mở file `.env` và điền thông tin:

```env
# Anthropic API Key (https://console.anthropic.com/)
ANTHROPIC_API_KEY=sk-ant-...

# Claude model (mặc định: claude-haiku-4-5)
LLM_MODEL=claude-haiku-4-5

# Redmine instance URL
REDMINE_URL=https://your-redmine.com

# Redmine API Key: My account → API access key
REDMINE_API_KEY=xxxxxxxxxxxxxxxxxxxx
```

> **Lấy Redmine API Key:** Đăng nhập Redmine → `My account` (góc phải trên) → phần **API access key** → Copy

### 4. Khởi động web server

```bash
python server.py
```

Mở trình duyệt: **http://127.0.0.1:8000**

---

## 🖥️ Hướng dẫn sử dụng GUI

### Bước 1 – Upload file Markdown

- Kéo thả file `.md` vào vùng upload, hoặc click **Chọn file**
- (Tùy chọn) Nhập thêm ngữ cảnh bổ sung vào ô text
- Click **✨ Phân tích bằng AI**

### Bước 2 – Kiểm tra & điền thông tin

Sau khi AI phân tích xong, các trường sẽ được tự động điền:

| Trường | Nguồn | Có thể sửa |
|--------|-------|-----------|
| Subject | LLM phân tích | ✅ |
| Description | LLM phân tích | ✅ |
| Project | Dropdown (từ Redmine) | ✅ |
| Tracker | Dropdown (từ Redmine) | ✅ |
| Parent Task ID | Nhập thủ công | ✅ |
| Priority | Dropdown | ✅ |
| Start date | Mặc định: hôm nay | ✅ |
| Due date | Mặc định: +7 ngày | ✅ |
| Assigned to | Tự động (user hiện tại) | ❌ |

### Bước 3 – Tạo Issue

Click **🚀 Tạo Issue** → Hệ thống tạo issue và hiển thị link trực tiếp.

---

## 🔌 MCP Server (Claude Desktop / Claude Code)

### Cấu hình Claude Desktop

Thêm vào file `claude_desktop_config.json`:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "redmine-issue-creator": {
      "command": "/path/to/.venv/bin/python",
      "args": ["/path/to/redmine-issue-creator/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "REDMINE_URL": "https://your-redmine.com",
        "REDMINE_API_KEY": "xxxxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

### Cấu hình Claude Code

Thêm vào `.claude/settings.json` trong project:

```json
{
  "mcpServers": {
    "redmine-issue-creator": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/path/to/redmine-issue-creator"
    }
  }
}
```

### Tools có sẵn trong MCP

| Tool | Mô tả |
|------|-------|
| `analyze_markdown` | Phân tích nội dung markdown → subject + description |
| `create_redmine_issue` | Tạo issue mới trên Redmine |
| `get_redmine_config` | Lấy trackers, projects, user hiện tại |
| `get_redmine_issue` | Lấy chi tiết issue theo ID |

**Ví dụ sử dụng với Claude:**
```
"Hãy phân tích file requirements.md và tạo issue Redmine cho sprint này"
```

---

## 🔗 REST API

API documentation tự động tại: `http://127.0.0.1:8000/docs`

### Endpoints

#### `GET /api/health`
Health check.

```json
{"status": "ok", "version": "1.0.0"}
```

#### `GET /api/config`
Lấy trackers, projects, user hiện tại.

```json
{
  "user": {"id": 1, "name": "Alice Dev", "login": "alice"},
  "trackers": [{"id": 1, "name": "Bug"}, {"id": 3, "name": "Task"}],
  "projects": [{"id": 1, "identifier": "my-project", "name": "My Project"}]
}
```

#### `POST /api/analyze`
Upload file markdown → AI phân tích.

**Form data:**
- `file`: File `.md` (multipart)
- `extra_context`: Chuỗi text tùy chọn

**Response:**
```json
{
  "subject": "Tiêu đề task được phân tích",
  "description": "Mô tả chi tiết từ markdown..."
}
```

#### `POST /api/issues`
Tạo Redmine issue.

**Body:**
```json
{
  "project_id": "my-project",
  "tracker_id": 3,
  "subject": "Tiêu đề issue",
  "description": "Mô tả chi tiết",
  "start_date": "2025-01-01",
  "due_date": "2025-01-31",
  "parent_issue_id": 100,
  "priority_id": 2
}
```

**Response:**
```json
{
  "id": 999,
  "subject": "Tiêu đề issue",
  "url": "https://your-redmine.com/issues/999",
  "status": "New",
  "tracker": "Task",
  "assigned_to": "Alice Dev"
}
```

---

## 🧪 Chạy Tests

```bash
# Cài đặt test dependencies
pip install -r requirements.txt

# Chạy toàn bộ test suite
pytest tests/ -v

# Chạy test theo module
pytest tests/test_llm_service.py -v
pytest tests/test_redmine_service.py -v
pytest tests/test_server.py -v

# Với coverage report
pytest tests/ --cov=services --cov=server --cov-report=term-missing
```

---

## 🛠️ Cấu hình nâng cao

### Biến môi trường đầy đủ

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `ANTHROPIC_API_KEY` | *(bắt buộc)* | API key từ console.anthropic.com |
| `REDMINE_URL` | *(bắt buộc)* | URL Redmine instance |
| `REDMINE_API_KEY` | *(bắt buộc)* | API key từ Redmine profile |
| `LLM_MODEL` | `claude-haiku-4-5` | Model Claude để phân tích |
| `HOST` | `127.0.0.1` | Host web server |
| `PORT` | `8000` | Port web server |

### Chạy với host/port khác

```bash
HOST=0.0.0.0 PORT=9090 python server.py
```

---

## ❓ Troubleshooting

### Lỗi "REDMINE_URL chưa được cấu hình"
→ Đảm bảo file `.env` tồn tại và có đủ các biến môi trường.

### Lỗi "Không thể kết nối Redmine"
→ Kiểm tra `REDMINE_URL` đúng định dạng (bao gồm `https://`).
→ Kiểm tra network/VPN nếu Redmine là internal.

### Lỗi "Redmine API 401: Unauthorized"
→ `REDMINE_API_KEY` sai hoặc hết hạn.
→ Vào Redmine → My Account → Reset API key.

### LLM trả về JSON không hợp lệ
→ Thử lại (model đôi khi không nhất quán).
→ Kiểm tra nội dung markdown không quá ngắn.

### MCP Server không kết nối được
→ Kiểm tra đường dẫn Python và script trong config.
→ Đảm bảo `.env` file có thể đọc được hoặc env vars được truyền trực tiếp.

---

## 📄 License

MIT License

---

*Powered by [Claude Haiku](https://www.anthropic.com/) · Built with [FastAPI](https://fastapi.tiangolo.com/) · [MCP Protocol](https://modelcontextprotocol.io/)*
