import http.server
import itertools
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from dhara.llm import (
    DAY,
    MARGIN,
    MINUTE,
    Client,
    ContextFull,
    Limit,
    MissingKey,
    Model,
    NotCached,
    Provider,
    ProviderError,
    QuotaReached,
    Settings,
    TransportError,
    prompt_hash,
    read_env,
    send_http,
)

KEYS = ("NVIDIA_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY", "TEST_KEY")
QUESTION = [
    {"role": "system", "content": "Answer from the Acts only."},
    {"role": "user", "content": "What replaced IPC 420?"},
]
Answer = tuple[int, dict[str, str], bytes]


@pytest.fixture(autouse=True)
def no_keys_in_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in KEYS:
        monkeypatch.delenv(name, raising=False)


class Clock:
    """A clock that only moves when something sleeps or a request takes time."""

    def __init__(self) -> None:
        self.now = 1_000_000.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@dataclass
class Sent:
    method: str
    url: str
    headers: dict[str, str]
    body: Any


class FakeHttp:
    """Answers each request with the next scripted answer, or raises it; each takes `took` seconds."""

    def __init__(self, clock: Clock, *answers: Answer | Exception, took: float = 1.5) -> None:
        self.clock = clock
        self.answers = list(answers)
        self.took = took
        self.sent: list[Sent] = []

    def __call__(self, method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float) -> Answer:
        self.sent.append(Sent(method, url, dict(headers), json.loads(body) if body else None))
        answer = self.answers.pop(0)
        self.clock.now += self.took
        if isinstance(answer, Exception):
            raise answer
        return answer


def chat(text: str = "BNS 318", tokens_in: int = 100, tokens_out: int = 20, thinking: int | None = None) -> Answer:
    usage: dict[str, Any] = {"prompt_tokens": tokens_in, "completion_tokens": tokens_out}
    if thinking is not None:
        usage["completion_tokens_details"] = {"reasoning_tokens": thinking}
    body = {
        "model": "served-model",
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": usage,
    }
    return 200, {"x-ratelimit-remaining-requests": "999", "content-type": "application/json"}, json.dumps(body).encode()


def status(code: int, headers: dict[str, str] | None = None) -> Answer:
    return code, headers or {}, b'{"error": {"message": "slow down"}}'


def client(tmp_path: Path, http: FakeHttp, clock: Clock, **kwargs: Any) -> Client:
    tmp_path.mkdir(parents=True, exist_ok=True)
    env = tmp_path / ".env"
    env.write_text("# keys\nNVIDIA_API_KEY=nv-test\nGROQ_API_KEY='gq-test'\nGEMINI_API_KEY=gm-test\nTEST_KEY=t\n")
    return Client(tmp_path / "llm.sqlite", env=env, send=http, clock=clock, sleep=clock.sleep, **kwargs)


def test_chat_completions_request_and_reply(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, chat(thinking=5))
    schema = {"type": "object", "properties": {"section": {"type": "string"}}}
    with client(tmp_path, http, clock) as llm:
        reply = llm.ask("mistral-small-4", QUESTION, Settings(seed=7, reasoning="none", schema=schema))
    sent = http.sent[0]
    assert sent.url == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert sent.headers["Authorization"] == "Bearer nv-test"
    assert sent.body == {
        "model": "mistralai/mistral-small-4-119b-2603",
        "messages": QUESTION,
        "temperature": 0.0,
        "max_tokens": 1024,
        "stream": False,
        "seed": 7,
        "reasoning_effort": "none",
        "response_format": {"type": "json_schema", "json_schema": {"name": "reply", "schema": schema}},
    }
    assert (reply.text, reply.model, reply.finish, reply.cached) == ("BNS 318", "served-model", "stop", False)
    assert (reply.tokens_in, reply.tokens_out, reply.tokens_thinking) == (100, 20, 5)
    assert reply.seconds == 1.5
    assert reply.cost == pytest.approx((100 * 0.15 + 20 * 0.60) / 1e6)
    # the provider's own count of what is left is kept; other headers are not
    assert reply.limits == {"x-ratelimit-remaining-requests": "999"}


def test_groq_caps_the_reply_with_its_own_field(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, chat())
    with client(tmp_path, http, clock) as llm:
        llm.ask("gpt-oss-120b", QUESTION, Settings(max_tokens=300, reasoning="low"))
    body = http.sent[0].body
    assert http.sent[0].headers["Authorization"] == "Bearer gq-test"
    assert body["max_completion_tokens"] == 300 and "max_tokens" not in body
    assert body["reasoning_effort"] == "low"


def test_gemini_request_and_reply(tmp_path: Path) -> None:
    clock = Clock()
    answer = {
        "candidates": [
            {
                "content": {"role": "model", "parts": [{"text": "weighing it", "thought": True}, {"text": "BNS 318"}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 4, "thoughtsTokenCount": 30},
        "modelVersion": "gemini-3.5-flash-lite",
    }
    http = FakeHttp(clock, (200, {}, json.dumps(answer).encode()))
    conversation = [*QUESTION, {"role": "assistant", "content": "Which Act?"}, {"role": "user", "content": "BNS"}]
    with client(tmp_path, http, clock) as llm:
        reply = llm.ask("gemini-3.5-flash-lite", conversation, Settings(reasoning="minimal", schema={"type": "object"}))
    sent = http.sent[0]
    assert sent.url.endswith("/v1beta/models/gemini-3.5-flash-lite:generateContent")
    assert sent.headers["x-goog-api-key"] == "gm-test" and "Authorization" not in sent.headers
    assert sent.body["systemInstruction"] == {"parts": [{"text": "Answer from the Acts only."}]}
    assert [content["role"] for content in sent.body["contents"]] == ["user", "model", "user"]
    assert sent.body["generationConfig"] == {
        "temperature": 0.0,
        "maxOutputTokens": 1024,
        "seed": 0,
        "thinkingConfig": {"thinkingLevel": "minimal"},
        "responseMimeType": "application/json",
        "responseJsonSchema": {"type": "object"},
    }
    assert (reply.text, reply.model, reply.finish) == ("BNS 318", "gemini-3.5-flash-lite", "STOP")
    # thinking is billed as output, so it counts in the reply's tokens
    assert (reply.tokens_in, reply.tokens_out, reply.tokens_thinking) == (50, 34, 30)


def test_a_blocked_gemini_prompt_is_an_error(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, (200, {}, b'{"promptFeedback": {"blockReason": "SAFETY"}}'))
    with client(tmp_path, http, clock) as llm, pytest.raises(ProviderError, match="SAFETY"):
        llm.ask("gemini-3.5-flash-lite", QUESTION)


def ollama(tokens_in: int, tokens_out: int = 40) -> Answer:
    body = {
        "model": "qwen3.5:9b",
        "message": {"role": "assistant", "content": "BNS 318"},
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": tokens_in,
        "eval_count": tokens_out,
        "prompt_eval_duration": 2_000_000_000,
        "eval_duration": 1_000_000_000,
    }
    return 200, {}, json.dumps(body).encode()


TAGS: Answer = (200, {}, json.dumps({"models": [{"name": "qwen3.5:9b", "digest": "abc123"}]}).encode())


def test_ollama_sets_its_context_and_checks_the_prompt_fits(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, TAGS, ollama(tokens_in=500), ollama(tokens_in=3_700))
    with client(tmp_path, http, clock) as llm:
        with pytest.raises(ValueError, match="num_ctx"):
            llm.ask("qwen3.5-9b", QUESTION)
        settings = Settings(max_tokens=400, num_ctx=4_096, reasoning=False)
        reply = llm.ask("qwen3.5-9b", QUESTION, settings)
        assert http.sent[0].method == "GET" and http.sent[0].url == "http://localhost:11434/api/tags"
        body = http.sent[1].body
        assert body["options"] == {"temperature": 0.0, "num_predict": 400, "num_ctx": 4_096, "seed": 0}
        assert (body["stream"], body["think"]) == (False, False)
        assert (reply.model, reply.tokens_in, reply.cost) == ("abc123", 500, 0.0)
        assert reply.body["prompt_eval_duration"] == 2_000_000_000
        # 3,700 prompt tokens leave less than the 400 the reply may need
        with pytest.raises(ContextFull):
            llm.ask("qwen3.5-9b", [{"role": "user", "content": "a long prompt"}], settings)


def test_a_local_model_must_be_the_pinned_one_and_ollama_running(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, TAGS, TransportError("connection refused"))
    models = {"local": Model("ollama", "qwen3.5:9b", 0.0, 0.0, version="def456")}
    with client(tmp_path, http, clock, models=models) as llm, pytest.raises(ProviderError, match="pinned"):
        llm.ask("local", QUESTION, Settings(num_ctx=4_096))
    with client(tmp_path, http, clock) as llm, pytest.raises(ProviderError, match="running"):
        llm.ask("qwen3.5-4b", QUESTION, Settings(num_ctx=4_096))


def test_a_repeated_call_comes_from_the_cache(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, chat("first"), chat("second"))
    with client(tmp_path, http, clock) as llm:
        first = llm.ask("mistral-small-4", QUESTION)
    with client(tmp_path, http, clock) as llm:
        again = llm.ask("mistral-small-4", QUESTION)
        other = llm.ask("mistral-small-4", QUESTION, Settings(temperature=0.7))
    assert len(http.sent) == 2
    assert (again.text, again.cached, again.key, again.tokens_in) == ("first", True, first.key, first.tokens_in)
    assert again.cost == first.cost and again.body == first.body and again.limits == first.limits
    assert (other.text, other.cached) == ("second", False)


def test_replay_answers_only_from_the_cache(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, chat())
    with client(tmp_path, http, clock) as llm:
        llm.ask("mistral-small-4", QUESTION)
    with client(tmp_path, http, clock, replay=True) as llm:
        assert llm.ask("mistral-small-4", QUESTION).cached
        with pytest.raises(NotCached):
            llm.ask("mistral-small-4", [{"role": "user", "content": "a new question"}])
        with pytest.raises(NotCached, match="pin"):
            llm.ask("qwen3.5-9b", QUESTION, Settings(num_ctx=4_096))
    assert len(http.sent) == 1


def limited(*limits: Limit, shared: bool = False) -> dict[str, Any]:
    provider = Provider("test", "https://example.org/v1/chat/completions", "chat", "TEST_KEY", limits, shared)
    return {
        "providers": {"test": provider},
        "models": {"a": Model("test", "model-a", 1.0, 2.0), "b": Model("test", "model-b", 1.0, 2.0)},
    }


PROMPTS = itertools.count(10)


def ask_each(llm: Client, *names: str) -> None:
    """One new question to each model named, in turn."""
    for name in names:
        llm.ask(name, [{"role": "user", "content": f"question {next(PROMPTS)}"}], Settings(max_tokens=10))


def test_calls_are_paced_under_a_limit_on_requests(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, chat(), chat(), chat(), took=1.0)
    start = clock.now
    with client(tmp_path, http, clock, **limited(Limit(MINUTE, requests=2))) as llm:
        ask_each(llm, "a", "a", "a")
    # the third waits until the first, sent at the start, leaves the minute
    assert clock.slept == [pytest.approx(MINUTE - 2.0 + MARGIN)]
    assert clock.now == pytest.approx(start + MINUTE + MARGIN + 1.0)


def test_a_shared_limit_counts_every_model_together(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, chat(), chat(), chat(), chat(), chat(), took=1.0)
    with client(tmp_path / "shared", http, clock, **limited(Limit(MINUTE, requests=2), shared=True)) as llm:
        ask_each(llm, "a", "b", "b")
    assert len(clock.slept) == 1
    clock.slept.clear()
    # counted per model, the same calls never wait
    with client(tmp_path / "apart", http, clock, **limited(Limit(MINUTE, requests=1))) as llm:
        ask_each(llm, "a", "b")
    assert clock.slept == []


def test_calls_are_paced_under_a_limit_on_tokens(tmp_path: Path) -> None:
    clock = Clock()
    # each call uses 120 tokens; the next is estimated at 11 characters / 3, rounded up, + 10 = 14
    http = FakeHttp(clock, chat(), chat(), chat(), took=1.0)
    with client(tmp_path, http, clock, **limited(Limit(MINUTE, tokens=250))) as llm:
        ask_each(llm, "a", "a")
        assert clock.slept == []
        ask_each(llm, "a")
    assert clock.slept == [pytest.approx(MINUTE - 2.0 + MARGIN)]


def test_a_call_larger_than_a_window_allows_is_refused(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock)
    with client(tmp_path, http, clock, **limited(Limit(MINUTE, tokens=50))) as llm:
        with pytest.raises(ProviderError, match="more than"):
            llm.ask("a", [{"role": "user", "content": "x" * 300}], Settings(max_tokens=10))
    assert http.sent == []


def test_a_daily_limit_stops_the_run_and_the_count_outlives_it(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, chat(), took=1.0)
    start = clock.now
    with client(tmp_path, http, clock, **limited(Limit(DAY, requests=1))) as llm:
        ask_each(llm, "a")
    # a new run, as on the same day, finds the call already counted
    with client(tmp_path, http, clock, **limited(Limit(DAY, requests=1))) as llm:
        with pytest.raises(QuotaReached) as stopped:
            llm.ask("a", [{"role": "user", "content": "another"}])
    assert stopped.value.until == pytest.approx(start + DAY + MARGIN)
    assert len(http.sent) == 1 and clock.slept == []


def test_a_rate_limited_call_waits_as_asked(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, status(429, {"retry-after": "7"}), chat())
    with client(tmp_path, http, clock) as llm:
        reply = llm.ask("gpt-oss-120b", QUESTION)
    assert clock.slept == [7.0] and reply.text == "BNS 318"
    counted = llm_count(tmp_path)
    assert counted == [0, 120]


def llm_count(tmp_path: Path) -> list[int]:
    with client(tmp_path, FakeHttp(Clock()), Clock()) as llm:
        return [tokens for (tokens,) in llm.db.execute("SELECT tokens FROM usage ORDER BY at")]


def test_server_errors_back_off_then_give_up(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, status(503), status(503), status(503))
    with client(tmp_path, http, clock, retries=2) as llm, pytest.raises(ProviderError, match="503"):
        llm.ask("mistral-small-4", QUESTION)
    assert clock.slept == [2.0, 4.0] and len(http.sent) == 3


def test_a_long_wait_asked_for_stops_the_run(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, status(429, {"retry-after": "3600"}))
    with client(tmp_path, http, clock) as llm, pytest.raises(QuotaReached) as stopped:
        llm.ask("gemini-3.5-flash-lite", QUESTION)
    assert stopped.value.until == pytest.approx(clock.now + 3_600)


def test_dropped_connections_are_retried(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, TransportError("timed out"), chat())
    with client(tmp_path, http, clock) as llm:
        assert llm.ask("mistral-small-4", QUESTION).text == "BNS 318"
    assert clock.slept == [2.0]


def test_a_refused_call_is_not_retried(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, status(400), chat())
    with client(tmp_path, http, clock) as llm, pytest.raises(ProviderError, match="400"):
        llm.ask("mistral-small-4", QUESTION)
    assert len(http.sent) == 1


def test_a_reply_in_another_shape_is_an_error(tmp_path: Path) -> None:
    clock = Clock()
    http = FakeHttp(clock, (200, {}, b'{"choices": []}'), (200, {}, b"<html>busy</html>"))
    with client(tmp_path, http, clock) as llm:
        with pytest.raises(ProviderError, match="shape"):
            llm.ask("mistral-small-4", QUESTION)
        with pytest.raises(ProviderError, match="not JSON"):
            llm.ask("mistral-small-4", QUESTION)


def test_keys_come_from_the_environment_first_then_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clock = Clock()
    http = FakeHttp(clock, chat())
    llm = Client(tmp_path / "llm.sqlite", env=tmp_path / "missing.env", send=http, clock=clock, sleep=clock.sleep)
    with llm, pytest.raises(MissingKey, match="NVIDIA_API_KEY"):
        llm.ask("mistral-small-4", QUESTION)
    assert http.sent == []
    monkeypatch.setenv("GROQ_API_KEY", "from-environment")
    with client(tmp_path, http, clock) as llm:
        llm.ask("gpt-oss-120b", QUESTION)
    assert http.sent[0].headers["Authorization"] == "Bearer from-environment"
    assert read_env(tmp_path / ".env")["GROQ_API_KEY"] == "gq-test"


def test_messages_and_models_are_checked(tmp_path: Path) -> None:
    clock = Clock()
    with client(tmp_path, FakeHttp(clock), clock) as llm:
        with pytest.raises(ValueError, match="role"):
            llm.ask("mistral-small-4", [{"role": "judge", "content": "?"}])
        with pytest.raises(ValueError, match="unknown model"):
            llm.ask("mistral-medium", QUESTION)
        with pytest.raises(ValueError, match="word"):
            llm.ask("mistral-small-4", QUESTION, Settings(reasoning=True))


def test_prompt_hash_names_a_prompt() -> None:
    assert prompt_hash(QUESTION) == prompt_hash([dict(message) for message in QUESTION])
    assert prompt_hash(QUESTION) != prompt_hash(QUESTION[::-1])
    assert len(prompt_hash(QUESTION)) == 16


class Server(http.server.BaseHTTPRequestHandler):
    """Answers 429 to a body that says slow, and 200 to any other, with a Retry After header either way."""

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(429 if body == b"slow" else 200)
        self.send_header("Retry-After", "3")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *args: Any) -> None:
        pass


def test_http_errors_come_back_as_answers_and_no_answer_is_a_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Server)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
    try:
        ok = send_http("POST", url, {"Content-Type": "application/json"}, b"{}", 5.0)
        slow = send_http("POST", url, {}, b"slow", 5.0)
    finally:
        server.shutdown()
        server.server_close()
    assert (ok[0], ok[1]["retry-after"], ok[2]) == (200, "3", b'{"ok": true}')
    assert (slow[0], slow[1]["retry-after"]) == (429, "3")
    with pytest.raises(TransportError):
        send_http("POST", url, {}, b"{}", 5.0)
