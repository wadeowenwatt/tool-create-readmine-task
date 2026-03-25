"""
Tests cho LLM Service – kiểm tra phân tích markdown với Claude Haiku.
Sử dụng mock để không gọi API thật trong CI.
"""
import json
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Đảm bảo import từ thư mục gốc project
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.llm_service import analyze_markdown


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

SAMPLE_MARKDOWN = """
# Yêu cầu: Tích hợp OAuth2 cho hệ thống login

## Mô tả
Hệ thống hiện tại sử dụng form login cơ bản. Cần tích hợp thêm OAuth2 để
người dùng có thể đăng nhập bằng Google và GitHub.

## Yêu cầu kỹ thuật
- Hỗ trợ Google OAuth2
- Hỗ trợ GitHub OAuth2
- Lưu refresh token an toàn trong DB
- Redirect về trang chủ sau khi login thành công

## Acceptance Criteria
- [ ] User có thể click "Login with Google"
- [ ] User có thể click "Login with GitHub"
- [ ] Session được tạo sau khi xác thực thành công
"""

EXPECTED_RESPONSE = {
    "subject": "Tích hợp OAuth2 (Google & GitHub) cho hệ thống login",
    "description": "Tích hợp OAuth2 để người dùng đăng nhập bằng Google và GitHub.\n\n"
                   "**Yêu cầu kỹ thuật:**\n- Hỗ trợ Google OAuth2\n- Hỗ trợ GitHub OAuth2\n"
                   "- Lưu refresh token an toàn\n\n**Acceptance Criteria:**\n"
                   "- User có thể login với Google và GitHub\n- Session tạo sau xác thực",
}


def make_mock_message(content_dict: dict) -> MagicMock:
    """Tạo mock object giả lập anthropic.Message."""
    msg = MagicMock()
    msg.content = [MagicMock()]
    msg.content[0].text = json.dumps(content_dict, ensure_ascii=False)
    return msg


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestAnalyzeMarkdown:
    """Test phân tích markdown với Claude Haiku."""

    def test_returns_subject_and_description(self, monkeypatch):
        """Hàm phải trả về dict có 'subject' và 'description'."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("services.llm_service.anthropic.Anthropic") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.messages.create.return_value = make_mock_message(EXPECTED_RESPONSE)

            result = analyze_markdown(SAMPLE_MARKDOWN)

        assert "subject" in result
        assert "description" in result
        assert isinstance(result["subject"], str)
        assert isinstance(result["description"], str)

    def test_subject_max_100_chars(self, monkeypatch):
        """Subject phải được cắt xuống ≤ 100 ký tự nếu LLM trả về dài hơn."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        long_subject = "A" * 150

        with patch("services.llm_service.anthropic.Anthropic") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.messages.create.return_value = make_mock_message(
                {"subject": long_subject, "description": "test"}
            )
            result = analyze_markdown(SAMPLE_MARKDOWN)

        assert len(result["subject"]) <= 100
        assert result["subject"].endswith("...")

    def test_passes_extra_context_to_llm(self, monkeypatch):
        """extra_context phải xuất hiện trong prompt gửi tới LLM."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        captured_prompts = []

        def fake_create(**kwargs):
            captured_prompts.append(kwargs.get("messages", []))
            return make_mock_message(EXPECTED_RESPONSE)

        with patch("services.llm_service.anthropic.Anthropic") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.messages.create.side_effect = fake_create

            analyze_markdown(SAMPLE_MARKDOWN, extra_context="Sprint Q2, high priority")

        assert any(
            "Sprint Q2" in str(m) for m in captured_prompts
        ), "extra_context không được truyền vào prompt"

    def test_raises_environment_error_without_api_key(self, monkeypatch):
        """Phải raise EnvironmentError nếu thiếu ANTHROPIC_API_KEY."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
            analyze_markdown(SAMPLE_MARKDOWN)

    def test_raises_value_error_on_invalid_json(self, monkeypatch):
        """Phải raise ValueError nếu LLM trả về text không phải JSON."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("services.llm_service.anthropic.Anthropic") as mock_cls:
            mock_client = mock_cls.return_value
            bad_msg = MagicMock()
            bad_msg.content = [MagicMock()]
            bad_msg.content[0].text = "Xin lỗi, tôi không thể xử lý yêu cầu này."
            mock_client.messages.create.return_value = bad_msg

            with pytest.raises(ValueError, match="JSON"):
                analyze_markdown(SAMPLE_MARKDOWN)

    def test_handles_json_with_extra_text(self, monkeypatch):
        """Phải parse được JSON dù LLM có thêm text trước/sau."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        response_with_preamble = (
            "Đây là kết quả phân tích của tôi:\n"
            + json.dumps(EXPECTED_RESPONSE)
            + "\nHy vọng điều này hữu ích!"
        )

        with patch("services.llm_service.anthropic.Anthropic") as mock_cls:
            mock_client = mock_cls.return_value
            msg = MagicMock()
            msg.content = [MagicMock()]
            msg.content[0].text = response_with_preamble
            mock_client.messages.create.return_value = msg

            result = analyze_markdown(SAMPLE_MARKDOWN)

        assert result["subject"] == EXPECTED_RESPONSE["subject"]

    def test_uses_configured_model(self, monkeypatch):
        """Phải dùng model từ env var LLM_MODEL."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("LLM_MODEL", "claude-haiku-4-5")
        called_with = {}

        def fake_create(**kwargs):
            called_with["model"] = kwargs.get("model")
            return make_mock_message(EXPECTED_RESPONSE)

        with patch("services.llm_service.anthropic.Anthropic") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.messages.create.side_effect = fake_create
            analyze_markdown(SAMPLE_MARKDOWN)

        assert called_with["model"] == "claude-haiku-4-5"

    def test_empty_content_is_handled(self, monkeypatch):
        """Content rỗng vẫn gọi LLM được (validation là ở API layer)."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch("services.llm_service.anthropic.Anthropic") as mock_cls:
            mock_client = mock_cls.return_value
            mock_client.messages.create.return_value = make_mock_message(
                {"subject": "Empty", "description": "No content"}
            )
            result = analyze_markdown("")  # LLM layer không validate empty

        assert result["subject"] == "Empty"
