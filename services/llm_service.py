"""
LLM Service - Sử dụng Claude Haiku để phân tích nội dung markdown
và trích xuất subject + description cho Redmine issue.
"""
import os
import json
import re
import logging

import openai
import anthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Bạn là trợ lý quản lý dự án. Nhiệm vụ của bạn là phân tích tài liệu yêu cầu và trích xuất TOÀN BỘ các task/issue riêng lẻ có cấu trúc cho hệ thống theo dõi issue Redmine.

Khi phân tích nội dung markdown:
1. Xác định tất cả các task/issue riêng lẻ được đề cập trong tài liệu
2. Mỗi task cần có subject ngắn gọn (tối đa 100 ký tự) và description chi tiết
3. Giữ lại các chi tiết kỹ thuật và yêu cầu quan trọng trong description
4. Giữ nguyên ngôn ngữ gốc (Tiếng Việt hoặc Tiếng Anh)

Luôn trả lời bằng JSON array hợp lệ, không thêm text ngoài JSON."""


def _build_client():
    """
    Trả về (client, use_proxy).
    - Nếu có ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN → OpenAI-compatible client qua proxy.
    - Ngược lại → Anthropic client trực tiếp.
    """
    base_url = os.getenv("ANTHROPIC_BASE_URL", "").rstrip("/")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if base_url and auth_token:
        # Proxy: dùng OpenAI-compatible /v1/chat/completions
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        logger.debug(f"LLM via proxy: {base_url}")
        return openai.OpenAI(api_key=auth_token, base_url=base_url), True

    # Trực tiếp Anthropic
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY chưa được cấu hình trong file .env")
    logger.debug("LLM via Anthropic API trực tiếp")
    return anthropic.Anthropic(api_key=api_key), False


def analyze_markdown(content: str, extra_context: str = "") -> list[dict]:
    """
    Phân tích nội dung markdown bằng LLM để trích xuất
    danh sách các issues phù hợp cho Redmine.

    Args:
        content: Nội dung file markdown
        extra_context: Ngữ cảnh bổ sung (tùy chọn)

    Returns:
        list of dict, mỗi dict có keys 'subject' và 'description'

    Raises:
        ValueError: Nếu không parse được response từ LLM
    """
    client, use_proxy = _build_client()
    model = os.getenv("LLM_MODEL", "claude-haiku-4-5")

    context_section = f"\nNgữ cảnh bổ sung: {extra_context}" if extra_context else ""

    user_prompt = f"""Phân tích tài liệu markdown sau và trích xuất TẤT CẢ các task/issue riêng lẻ cho Redmine:{context_section}

---NỘI DUNG MARKDOWN---
{content}
---KẾT THÚC NỘI DUNG---

Trả lời theo đúng cấu trúc JSON array sau (không thêm text nào khác):
[
  {{
    "subject": "tiêu đề task ngắn gọn, rõ ràng (tối đa 100 ký tự)",
    "description": "mô tả chi tiết đầy đủ, giữ nguyên các yêu cầu quan trọng từ tài liệu"
  }},
  ...
]"""

    logger.info(f"Calling {model} to analyze markdown ({len(content)} chars)")

    if use_proxy:
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        response_text = response.choices[0].message.content.strip()
    else:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        response_text = response.content[0].text.strip()

    logger.debug(f"LLM response: {response_text[:200]}...")

    # Parse JSON array
    json_match = re.search(r"\[[\s\S]*\]", response_text)
    if not json_match:
        raise ValueError(f"Không tìm thấy JSON array trong response: {response_text[:200]}")

    results = json.loads(json_match.group())

    if not isinstance(results, list) or len(results) == 0:
        raise ValueError("LLM không trả về danh sách issue hợp lệ")

    # Validate và normalize từng issue
    issues = []
    for i, item in enumerate(results):
        if "subject" not in item or "description" not in item:
            logger.warning(f"Issue #{i+1} thiếu subject hoặc description, bỏ qua")
            continue
        if len(item["subject"]) > 100:
            item["subject"] = item["subject"][:97] + "..."
        issues.append({"subject": item["subject"], "description": item["description"]})

    if not issues:
        raise ValueError("Không trích xuất được issue nào từ tài liệu")

    logger.info(f"Extracted {len(issues)} issues from markdown")
    return issues
