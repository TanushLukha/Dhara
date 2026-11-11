import json
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from check_models import Check, check, is_right, report  # noqa: E402

from dhara.llm import Client  # noqa: E402


def test_an_answer_is_right_only_when_it_names_section_303() -> None:
    assert is_right("text", "Section 303.")
    assert not is_right("text", "Section 302")
    assert is_right("json", '{"act": "BNS", "section": "303"}')
    assert not is_right("json", '{"section": "303"}')
    assert not is_right("json", "303")
    assert not is_right("json", "Section 303, as JSON")


def test_each_model_is_asked_for_text_and_for_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    (tmp_path / ".env").write_text("NVIDIA_API_KEY=nv-test\n")
    answers = ["303", json.dumps({"act": "BNS", "section": "303"})]
    sent: list[dict[str, object]] = []

    def send(
        method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
    ) -> tuple[int, dict[str, str], bytes]:
        sent.append(json.loads(body or b"{}"))
        usage = {"prompt_tokens": 30, "completion_tokens": 5}
        choice = {"message": {"content": answers[len(sent) - 1]}, "finish_reason": "stop"}
        answer = {"model": "mistralai/mistral-small-4-119b-2603", "choices": [choice], "usage": usage}
        return 200, {}, json.dumps(answer).encode()

    with Client(tmp_path / "llm.sqlite", env=tmp_path / ".env", send=send, sleep=lambda seconds: None) as llm:
        checks = check(llm, "mistral-small-4")
    assert [(c.asked, c.right, c.error) for c in checks] == [("text", True, ""), ("json", True, "")]
    assert [body["reasoning_effort"] for body in sent] == ["none", "none"]
    assert "response_format" not in sent[0] and "response_format" in sent[1]


def test_the_report_shows_calls_failures_and_limits() -> None:
    checks = [
        Check(
            "gpt-oss-120b",
            "text",
            right=True,
            reply="303 | BNS",
            version="openai/gpt-oss-120b",
            tokens_in=40,
            tokens_out=12,
            thinking=8,
            seconds=0.5,
            finish="stop",
            limits={"x-ratelimit-limit-requests": "1000"},
        ),
        Check("gemini-3.5-flash-lite", "json", error="GEMINI_API_KEY is not set"),
    ]
    text = report(checks)
    row = "| `gpt-oss-120b` | text | yes | yes | 303 \\| BNS | `openai/gpt-oss-120b` | 40 | 12 | 8 | 0.50 | stop |"
    assert row in text
    assert "* `gemini-3.5-flash-lite`, json: GEMINI_API_KEY is not set" in text
    assert "| `gpt-oss-120b` | `x-ratelimit-limit-requests` 1000 |" in text
