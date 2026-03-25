"""
Chat CLI - Hỏi đáp với LLM thông qua proxy.
Cấu hình trong ~/.zshrc (set bởi proxy):
  ANTHROPIC_BASE_URL   = Base URL của proxy
  ANTHROPIC_AUTH_TOKEN = Auth token do proxy cấp

Hoặc trong .env (kết nối trực tiếp Anthropic):
  ANTHROPIC_API_KEY = API key Anthropic
  LLM_MODEL         = Model muốn dùng (vd: claude-haiku-4-5)
"""

import os
import sys

import openai
import anthropic
from dotenv import load_dotenv

load_dotenv()


def build_openai_client() -> openai.OpenAI:
    """Dùng khi proxy expose /v1/chat/completions (OpenAI-compatible)."""
    base_url = os.getenv("ANTHROPIC_BASE_URL", "").rstrip("/")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")

    # OpenAI SDK ghép: base_url + /chat/completions
    # nên base_url phải kết thúc bằng /v1
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    print(f"🔀 Proxy (OpenAI-compatible): {base_url}")
    return openai.OpenAI(
        api_key=auth_token,
        base_url=base_url,
    )


def build_anthropic_client() -> anthropic.Anthropic:
    """Dùng khi kết nối trực tiếp Anthropic API."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("❌ Thiếu ANTHROPIC_API_KEY trong .env")
    print("🌐 Kết nối trực tiếp Anthropic API")
    return anthropic.Anthropic(api_key=api_key)


def chat():
    base_url = os.getenv("ANTHROPIC_BASE_URL")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN")
    model = os.getenv("LLM_MODEL", "claude-haiku-4-5")
    history: list[dict] = []

    use_proxy = bool(base_url and auth_token)

    if use_proxy:
        openai_client = build_openai_client()
    else:
        anthropic_client = build_anthropic_client()

    print(f"🤖 Model: {model}")
    print("💬 Nhập câu hỏi (gõ 'exit' hoặc Ctrl+C để thoát, 'reset' để xoá lịch sử)\n")

    while True:
        try:
            user_input = input("Bạn: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Tạm biệt!")
            break

        if not user_input:
            continue
        if user_input.lower() == "exit":
            print("👋 Tạm biệt!")
            break
        if user_input.lower() == "reset":
            history.clear()
            print("🗑️  Đã xoá lịch sử hội thoại\n")
            continue

        history.append({"role": "user", "content": user_input})

        try:
            if use_proxy:
                # Gọi qua proxy: dùng OpenAI-compatible /v1/chat/completions
                response = openai_client.chat.completions.create(
                    model=model,
                    messages=history,
                    max_tokens=2048,
                )
                assistant_text = response.choices[0].message.content
            else:
                # Gọi trực tiếp Anthropic
                response = anthropic_client.messages.create(
                    model=model,
                    max_tokens=2048,
                    messages=history,
                )
                assistant_text = response.content[0].text

            history.append({"role": "assistant", "content": assistant_text})
            print(f"\nAI: {assistant_text}\n")

        except (openai.APIConnectionError, anthropic.APIConnectionError):
            print("❌ Không thể kết nối tới server. Kiểm tra ANTHROPIC_BASE_URL.\n")
            history.pop()
        except (openai.AuthenticationError, anthropic.AuthenticationError):
            print("❌ Auth token không hợp lệ. Kiểm tra ANTHROPIC_AUTH_TOKEN.\n")
            history.pop()
        except (openai.APIStatusError, anthropic.APIStatusError) as e:
            print(f"❌ Lỗi API {e.status_code}: {e.message}\n")
            history.pop()


if __name__ == "__main__":
    chat()
