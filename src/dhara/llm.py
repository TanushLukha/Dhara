"""Every model call goes through one client: cached, versioned and paced (decision 15).

A call names one of Dhara's models (MODELS) and gives its messages and settings. The client answers
from its SQLite cache when the same call was made before. Otherwise it waits until the provider's
free limits leave room for one more call, sends it, retries a rate limit or a server error with a
growing wait, and stores the reply with its tokens, its seconds and what it would cost at list
prices. The calls already made are counted in the same database, so runs on different days share one
count, and a run that meets a daily limit stops with QuotaReached instead of failing call by call.
Replay mode answers from the cache only and fails on any call it has not seen, so every table can be
built again without a request.

Three wire formats cover the providers: chat completions (NVIDIA and Groq), Gemini's own
generateContent, and Ollama's /api/chat on the Mac.
"""

import email.utils
import hashlib
import http.client
import json
import math
import os
import sqlite3
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from dhara import REPO, RUNS

CACHE = RUNS / "llm.sqlite"
ENV = REPO / ".env"
MINUTE = 60.0
DAY = 86_400.0
MAX_WAIT = 120.0  # seconds; a longer wait for room means a daily limit, and the run stops
MARGIN = 0.5  # seconds added to every wait, since a provider's clock is not ours
RETRIES = 5  # after the first try
BACKOFF = 2.0  # seconds before the first retry, doubling up to MAX_BACKOFF
MAX_BACKOFF = 60.0
RETRIED = frozenset({429, 500, 502, 503, 504})
CHARS_PER_TOKEN = 3  # only to pace a call before it is sent; every count recorded is the provider's
ROLES = frozenset({"system", "user", "assistant"})

Wire = Literal["chat", "gemini", "ollama"]
Message = Mapping[str, str]
Json = dict[str, Any]


@dataclass(frozen=True)
class Limit:
    """At most `requests` calls, and `tokens` tokens of prompt and reply, in any window of `seconds`."""

    seconds: float
    requests: int | None = None
    tokens: int | None = None


@dataclass(frozen=True)
class Provider:
    name: str
    url: str  # {model} becomes the model's identifier
    wire: Wire
    key: str | None  # the variable holding the API key; None for the Mac
    limits: tuple[Limit, ...] = ()
    shared: bool = False  # True: the limits count every model of the provider together
    max_tokens: str = "max_tokens"  # the request field that caps the reply
    timeout: float = 300.0


PROVIDERS: dict[str, Provider] = {
    # free to members of the NVIDIA Developer Program for research, development and testing; about
    # 40 requests a minute for the whole account, and no daily cap published (decision 14)
    "nvidia": Provider(
        "nvidia",
        "https://integrate.api.nvidia.com/v1/chat/completions",
        "chat",
        "NVIDIA_API_KEY",
        limits=(Limit(MINUTE, requests=40),),
        shared=True,
    ),
    # Groq's free plan, counted per model
    "groq": Provider(
        "groq",
        "https://api.groq.com/openai/v1/chat/completions",
        "chat",
        "GROQ_API_KEY",
        limits=(Limit(MINUTE, requests=30, tokens=8_000), Limit(DAY, requests=1_000, tokens=200_000)),
        max_tokens="max_completion_tokens",
    ),
    # Gemini's free tier, counted per model; Google resets its day at midnight Pacific time, and a
    # rolling day stays under that too
    "gemini": Provider(
        "gemini",
        "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "gemini",
        "GEMINI_API_KEY",
        limits=(Limit(MINUTE, requests=10, tokens=250_000), Limit(DAY, requests=500)),
    ),
    # Ollama on the Mac: no limit but time, and a long prompt can take minutes
    "ollama": Provider("ollama", "http://localhost:11434/api/chat", "ollama", None, timeout=1_800.0),
}


@dataclass(frozen=True)
class Model:
    provider: str
    id: str  # the provider's identifier, pinned
    price_in: float  # US dollars a million prompt tokens, at list price
    price_out: float  # US dollars a million reply tokens, thinking included
    version: str | None = None  # Ollama: the digest, pinned once the model is pulled


MODELS: dict[str, Model] = {
    # Mistral's open weights, served free by NVIDIA; the prices are Mistral's own API's
    "mistral-small-4": Model("nvidia", "mistralai/mistral-small-4-119b-2603", 0.15, 0.60),
    "mistral-large-3": Model("nvidia", "mistralai/mistral-large-3-675b-instruct-2512", 0.50, 1.50),
    "gpt-oss-120b": Model("groq", "openai/gpt-oss-120b", 0.15, 0.60),
    "qwen3.8-27b": Model("groq", "qwen/qwen3.8-27b", 0.80, 4.00),
    "gemini-3.5-flash-lite": Model("gemini", "gemini-3.5-flash-lite", 0.30, 2.50),
    # on the Mac nothing is paid
    "qwen3.5-9b": Model("ollama", "qwen3.5:9b", 0.0, 0.0),
    "qwen3.5-4b": Model("ollama", "qwen3.5:4b", 0.0, 0.0),
}


@dataclass(frozen=True)
class Settings:
    """Everything a call asks besides its messages; every field is part of the cache key."""

    temperature: float = 0.0
    max_tokens: int = 1_024
    seed: int | None = 0
    reasoning: str | bool | None = None  # the provider's own value; None keeps the provider's default
    schema: dict[str, Any] | None = None  # a JSON Schema the reply must follow
    num_ctx: int | None = None  # Ollama's context window, which every local call sets (decision 16)


@dataclass(frozen=True)
class Reply:
    text: str
    model: str  # the version that answered, as the provider names it
    tokens_in: int
    tokens_out: int  # the reply's tokens, thinking included, as providers bill them
    tokens_thinking: int | None  # the part spent thinking, when the provider says
    seconds: float
    cost: float  # US dollars at list prices
    finish: str  # why the reply ended, in the provider's words
    key: str  # the cache key
    cached: bool
    body: Json  # the provider's whole answer, for what the fields above leave out (Ollama's timings)


class LlmError(Exception):
    """A model call that could not be answered."""


class ProviderError(LlmError):
    """The provider refused the call, answered in an unexpected shape, or kept failing."""


class QuotaReached(LlmError):
    """A free limit leaves no room until `until` (seconds since the epoch): stop, and run again then."""

    def __init__(self, message: str, until: float) -> None:
        super().__init__(message)
        self.until = until


class NotCached(LlmError):
    """Replay mode met a call the cache does not hold."""


class MissingKey(LlmError):
    """The provider's API key is neither in the environment nor in .env."""


class ContextFull(LlmError):
    """An Ollama prompt left no room for its reply in the context window, so it may have been cut."""


class TransportError(Exception):
    """No HTTP answer at all: a timeout, or a connection refused or dropped."""


class Send(Protocol):
    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
    ) -> tuple[int, dict[str, str], bytes]: ...


def _lowered(pairs: Iterable[tuple[str, Any]]) -> dict[str, str]:
    return {name.lower(): str(value) for name, value in pairs}


def send_http(
    method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float
) -> tuple[int, dict[str, str], bytes]:
    """The status, headers and body of one HTTP request; an HTTP error is an answer like any other."""
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status: int = response.status
            answer: bytes = response.read()
            return status, _lowered(response.headers.items()), answer
    except urllib.error.HTTPError as error:
        return error.code, _lowered(error.headers.items()), error.read()
    except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as error:
        raise TransportError(str(error)) from error


def read_env(path: Path) -> dict[str, str]:
    """The NAME=value lines of a .env file; blank lines and lines starting with # are skipped."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip("'\"")
    return values


def canonical(value: object) -> str:
    """JSON with sorted keys and no spaces, so equal values hash equally."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def prompt_hash(messages: Sequence[Message]) -> str:
    """A short name for a prompt, for results files."""
    return hashlib.sha256(canonical([dict(message) for message in messages]).encode()).hexdigest()[:16]


def price(model: Model, tokens_in: int, tokens_out: int) -> float:
    """What a call would cost at the model's list prices, in US dollars."""
    return (tokens_in * model.price_in + tokens_out * model.price_out) / 1e6


def _checked(messages: Sequence[Message]) -> list[dict[str, str]]:
    checked = []
    for message in messages:
        role, content = message.get("role"), message.get("content")
        if role not in ROLES or not isinstance(content, str):
            raise ValueError(f"a message needs a role among {sorted(ROLES)} and text: {dict(message)!r}")
        checked.append({"role": role, "content": content})
    if not checked:
        raise ValueError("a call needs at least one message")
    return checked


def _estimate(messages: list[dict[str, str]], settings: Settings) -> int:
    """More tokens than the call should use, to pace it before it is sent."""
    chars = sum(len(message["content"]) for message in messages)
    if settings.schema is not None:
        chars += len(canonical(settings.schema))
    return math.ceil(chars / CHARS_PER_TOKEN) + settings.max_tokens


def chat_body(provider: Provider, model: Model, messages: list[dict[str, str]], settings: Settings) -> Json:
    if isinstance(settings.reasoning, bool):
        raise ValueError(f"{provider.name} takes reasoning as a word, such as 'none' or 'low'")
    body: Json = {
        "model": model.id,
        "messages": messages,
        "temperature": settings.temperature,
        provider.max_tokens: settings.max_tokens,
        "stream": False,
    }
    if settings.seed is not None:
        body["seed"] = settings.seed
    if settings.reasoning is not None:
        body["reasoning_effort"] = settings.reasoning
    if settings.schema is not None:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "reply", "schema": settings.schema}}
    return body


def gemini_body(messages: list[dict[str, str]], settings: Settings) -> Json:
    if isinstance(settings.reasoning, bool):
        raise ValueError("Gemini takes reasoning as a thinking level, such as 'minimal' or 'low'")
    config: Json = {"temperature": settings.temperature, "maxOutputTokens": settings.max_tokens}
    if settings.seed is not None:
        config["seed"] = settings.seed
    if settings.reasoning is not None:
        config["thinkingConfig"] = {"thinkingLevel": settings.reasoning}
    if settings.schema is not None:
        config["responseMimeType"] = "application/json"
        config["responseJsonSchema"] = settings.schema
    contents = [
        {"role": "model" if message["role"] == "assistant" else "user", "parts": [{"text": message["content"]}]}
        for message in messages
        if message["role"] != "system"
    ]
    body: Json = {"contents": contents, "generationConfig": config}
    system = [message["content"] for message in messages if message["role"] == "system"]
    if system:
        body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system)}]}
    return body


def ollama_body(model: Model, messages: list[dict[str, str]], settings: Settings) -> Json:
    if settings.num_ctx is None:
        raise ValueError("an Ollama call sets num_ctx, so no prompt is cut silently (decision 16)")
    options: Json = {
        "temperature": settings.temperature,
        "num_predict": settings.max_tokens,
        "num_ctx": settings.num_ctx,
    }
    if settings.seed is not None:
        options["seed"] = settings.seed
    body: Json = {"model": model.id, "messages": messages, "stream": False, "options": options}
    if settings.reasoning is not None:
        body["think"] = settings.reasoning
    if settings.schema is not None:
        body["format"] = settings.schema
    return body


@dataclass(frozen=True)
class Parsed:
    text: str
    version: str
    tokens_in: int
    tokens_out: int
    tokens_thinking: int | None
    finish: str


def parse_chat(data: Json, model: Model) -> Parsed:
    try:
        choice = data["choices"][0]
        usage = data["usage"]
        details = usage.get("completion_tokens_details") or {}
        thinking = details.get("reasoning_tokens")
        return Parsed(
            text=choice["message"].get("content") or "",
            version=str(data.get("model") or model.id),
            tokens_in=int(usage["prompt_tokens"]),
            tokens_out=int(usage["completion_tokens"]),
            tokens_thinking=None if thinking is None else int(thinking),
            finish=str(choice.get("finish_reason") or ""),
        )
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as error:
        raise ProviderError(f"a reply in an unexpected shape: {error!r}") from error


def parse_gemini(data: Json, model: Model) -> Parsed:
    candidates = data.get("candidates") or []
    if not candidates:
        reason = (data.get("promptFeedback") or {}).get("blockReason", "no candidates")
        raise ProviderError(f"Gemini returned no reply: {reason}")
    try:
        candidate = candidates[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        usage = data.get("usageMetadata") or {}
        thinking = int(usage.get("thoughtsTokenCount", 0))
        return Parsed(
            # thought parts are the model's thinking, not its reply
            text="".join(str(part.get("text", "")) for part in parts if not part.get("thought")),
            version=str(data.get("modelVersion") or model.id),
            tokens_in=int(usage.get("promptTokenCount", 0)),
            tokens_out=int(usage.get("candidatesTokenCount", 0)) + thinking,
            tokens_thinking=thinking,
            finish=str(candidate.get("finishReason", "")),
        )
    except (TypeError, ValueError, AttributeError) as error:
        raise ProviderError(f"a reply in an unexpected shape: {error!r}") from error


def parse_ollama(data: Json, version: str, settings: Settings) -> Parsed:
    try:
        tokens_in = int(data.get("prompt_eval_count", 0))
        tokens_out = int(data.get("eval_count", 0))
        text = str((data.get("message") or {}).get("content", ""))
    except (TypeError, ValueError, AttributeError) as error:
        raise ProviderError(f"a reply in an unexpected shape: {error!r}") from error
    window = settings.num_ctx or 0
    if tokens_in + settings.max_tokens >= window:
        raise ContextFull(
            f"a prompt of {tokens_in} tokens and a reply of up to {settings.max_tokens} do not fit num_ctx {window}"
        )
    return Parsed(text, version, tokens_in, tokens_out, None, str(data.get("done_reason", "")))


SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    key TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    version TEXT NOT NULL,
    request TEXT NOT NULL,
    text TEXT NOT NULL,
    finish TEXT NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    tokens_thinking INTEGER,
    seconds REAL NOT NULL,
    cost REAL NOT NULL,
    body TEXT NOT NULL,
    limits TEXT NOT NULL,
    at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS usage (
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    at REAL NOT NULL,
    tokens INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS usage_by_time ON usage (provider, at);
"""


def _when(seconds: float) -> str:
    return time.strftime("%H:%M UTC on %d %b", time.gmtime(seconds))


def _excerpt(raw: bytes) -> str:
    return raw[:300].decode("utf-8", errors="replace")


class Client:
    """One cache, one count of the calls made, one set of keys; see the module's docstring."""

    def __init__(
        self,
        cache: Path = CACHE,
        *,
        replay: bool = False,
        env: Path = ENV,
        send: Send = send_http,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        max_wait: float = MAX_WAIT,
        retries: int = RETRIES,
        providers: Mapping[str, Provider] = PROVIDERS,
        models: Mapping[str, Model] = MODELS,
    ) -> None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(cache)
        self.db.executescript(SCHEMA)
        self.replay = replay
        self.env = env
        self.send = send
        self.clock = clock
        self.sleep = sleep
        self.max_wait = max_wait
        self.retries = retries
        self.providers = providers
        self.models = models
        self.versions: dict[str, str] = {}
        longest = max((limit.seconds for provider in providers.values() for limit in provider.limits), default=DAY)
        with self.db:
            self.db.execute("DELETE FROM usage WHERE at < ?", (clock() - 2 * longest,))

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def ask(self, name: str, messages: Sequence[Message], settings: Settings | None = None) -> Reply:
        """The reply of model `name` to `messages`, from the cache when this exact call was made before."""
        if name not in self.models:
            raise ValueError(f"unknown model {name!r}; Dhara's models are {sorted(self.models)}")
        settings = settings or Settings()
        model = self.models[name]
        provider = self.providers[model.provider]
        checked = _checked(messages)
        version = self._version(name, model, provider)
        request = canonical({"messages": checked, "settings": asdict(settings)})
        identity = canonical({"provider": provider.name, "model": model.id, "version": version})
        key = hashlib.sha256(f"{identity}\n{request}".encode()).hexdigest()
        row = self.db.execute(
            "SELECT text, version, tokens_in, tokens_out, tokens_thinking, seconds, finish, body FROM calls"
            " WHERE key = ?",
            (key,),
        ).fetchone()
        if row is not None:
            text, answered, tokens_in, tokens_out, thinking, seconds, finish, body = row
            cost = price(model, tokens_in, tokens_out)
            return Reply(
                text, answered, tokens_in, tokens_out, thinking, seconds, cost, finish, key, True, json.loads(body)
            )
        if self.replay:
            raise NotCached(f"replay mode, and the cache holds no call to {name} with these messages and settings")
        return self._call(provider, model, version, checked, settings, key, request)

    def _version(self, name: str, model: Model, provider: Provider) -> str:
        """The pinned identifier, or for a local model the digest Ollama reports for it."""
        if provider.wire != "ollama":
            return model.version or model.id
        if self.replay:
            if model.version is None:
                raise NotCached(f"pin {model.id}'s digest in MODELS to replay its calls")
            return model.version
        if name not in self.versions:
            tags = provider.url.rsplit("/api/", 1)[0] + "/api/tags"
            try:
                status, _, raw = self.send("GET", tags, {}, None, provider.timeout)
            except TransportError as error:
                raise ProviderError(f"Ollama is not answering at {tags} ({error}); is it running?") from error
            if status != 200:
                raise ProviderError(f"Ollama answered {status} to {tags}: {_excerpt(raw)}")
            listed = self._json(raw, provider).get("models") or []
            pulled = {str(entry.get("name")): str(entry.get("digest")) for entry in listed}
            if model.id not in pulled:
                raise ProviderError(f"{model.id} is not pulled; Ollama has {sorted(pulled)}")
            if model.version is not None and pulled[model.id] != model.version:
                raise ProviderError(f"{model.id} on the Mac is {pulled[model.id]}, not the pinned {model.version}")
            self.versions[name] = pulled[model.id]
        return self.versions[name]

    def _request(
        self, provider: Provider, model: Model, messages: list[dict[str, str]], settings: Settings
    ) -> tuple[str, dict[str, str], Json]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if provider.key is not None:
            key = os.environ.get(provider.key) or read_env(self.env).get(provider.key)
            if not key:
                raise MissingKey(f"{provider.key} is not set: put it in {self.env} (see .env.example)")
            if provider.wire == "gemini":
                headers["x-goog-api-key"] = key
            else:
                headers["Authorization"] = f"Bearer {key}"
        url = provider.url.replace("{model}", model.id)
        if provider.wire == "chat":
            return url, headers, chat_body(provider, model, messages, settings)
        if provider.wire == "gemini":
            return url, headers, gemini_body(messages, settings)
        return url, headers, ollama_body(model, messages, settings)

    def _call(
        self,
        provider: Provider,
        model: Model,
        version: str,
        messages: list[dict[str, str]],
        settings: Settings,
        key: str,
        request: str,
    ) -> Reply:
        url, headers, body = self._request(provider, model, messages, settings)
        payload = json.dumps(body, ensure_ascii=False).encode()
        estimate = _estimate(messages, settings)
        for attempt in range(self.retries + 1):
            self._make_room(provider, model, estimate)
            started = self.clock()
            try:
                status, answer_headers, raw = self.send("POST", url, headers, payload, provider.timeout)
            except TransportError as error:
                self._count(provider, model, started, 0)
                if attempt == self.retries:
                    raise ProviderError(f"{provider.name}: {error} (after {attempt + 1} tries)") from error
                self.sleep(min(BACKOFF * 2**attempt, MAX_BACKOFF))
                continue
            seconds = self.clock() - started
            if status == 200:
                try:
                    data = self._json(raw, provider)
                    parsed = self._parse(provider, model, version, settings, data)
                except LlmError:
                    self._count(provider, model, started, 0)
                    raise
                self._count(provider, model, started, parsed.tokens_in + parsed.tokens_out)
                return self._store(provider, model, parsed, key, request, seconds, started, data, answer_headers)
            self._count(provider, model, started, 0)
            if status in RETRIED and attempt < self.retries:
                delay = self._retry_after(answer_headers)
                delay = min(BACKOFF * 2**attempt, MAX_BACKOFF) if delay is None else delay
                if delay > self.max_wait:
                    until = self.clock() + delay
                    raise QuotaReached(f"{provider.name} asks to wait until {_when(until)}; run again then", until)
                self.sleep(delay)
                continue
            raise ProviderError(f"{provider.name} answered {status}: {_excerpt(raw)}")
        raise AssertionError("unreachable")

    def _parse(self, provider: Provider, model: Model, version: str, settings: Settings, data: Json) -> Parsed:
        if provider.wire == "chat":
            return parse_chat(data, model)
        if provider.wire == "gemini":
            return parse_gemini(data, model)
        return parse_ollama(data, version, settings)

    def _store(
        self,
        provider: Provider,
        model: Model,
        parsed: Parsed,
        key: str,
        request: str,
        seconds: float,
        started: float,
        data: Json,
        answer_headers: Mapping[str, str],
    ) -> Reply:
        cost = price(model, parsed.tokens_in, parsed.tokens_out)
        # the limits a provider reports with each answer are its own count of what this account has left
        limits = {name: value for name, value in answer_headers.items() if name.startswith(("x-ratelimit", "retry"))}
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO calls VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    provider.name,
                    model.id,
                    parsed.version,
                    request,
                    parsed.text,
                    parsed.finish,
                    parsed.tokens_in,
                    parsed.tokens_out,
                    parsed.tokens_thinking,
                    seconds,
                    cost,
                    canonical(data),
                    canonical(limits),
                    started,
                ),
            )
        return Reply(
            parsed.text,
            parsed.version,
            parsed.tokens_in,
            parsed.tokens_out,
            parsed.tokens_thinking,
            seconds,
            cost,
            parsed.finish,
            key,
            False,
            data,
        )

    def _json(self, raw: bytes, provider: Provider) -> Json:
        try:
            data = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderError(f"{provider.name} sent an answer that is not JSON: {_excerpt(raw)}") from error
        if not isinstance(data, dict):
            raise ProviderError(f"{provider.name} sent JSON that is not an object: {_excerpt(raw)}")
        return data

    def _count(self, provider: Provider, model: Model, at: float, tokens: int) -> None:
        """Every request sent is counted, refused ones too, since a provider may count them."""
        with self.db:
            self.db.execute("INSERT INTO usage VALUES (?, ?, ?, ?)", (provider.name, model.id, at, tokens))

    def _used(self, provider: Provider, model: Model, since: float) -> list[tuple[float, int]]:
        """The calls in the window that starts at `since`, oldest first, with their tokens."""
        if provider.shared:
            query = "SELECT at, tokens FROM usage WHERE provider = ? AND at > ? ORDER BY at"
            rows = self.db.execute(query, (provider.name, since)).fetchall()
        else:
            query = "SELECT at, tokens FROM usage WHERE provider = ? AND model = ? AND at > ? ORDER BY at"
            rows = self.db.execute(query, (provider.name, model.id, since)).fetchall()
        return [(float(at), int(tokens)) for at, tokens in rows]

    def _make_room(self, provider: Provider, model: Model, estimate: int) -> None:
        """Waits until every limit has room for one more call of about `estimate` tokens."""
        while True:
            now = self.clock()
            wait = max((self._wait(provider, model, limit, estimate, now) for limit in provider.limits), default=0.0)
            if wait <= 0:
                return
            if wait > self.max_wait:
                raise QuotaReached(
                    f"{provider.name}'s free limit for {model.id} leaves no room until {_when(now + wait)}; run again",
                    now + wait,
                )
            self.sleep(wait)

    def _wait(self, provider: Provider, model: Model, limit: Limit, estimate: int, now: float) -> float:
        used = self._used(provider, model, now - limit.seconds)
        wait = 0.0
        if limit.requests is not None and len(used) >= limit.requests:
            # the oldest calls leave the window until one more fits
            leaving = used[len(used) - limit.requests][0]
            wait = max(wait, leaving + limit.seconds - now + MARGIN)
        if limit.tokens is not None:
            if estimate > limit.tokens:
                raise ProviderError(
                    f"a call of about {estimate} tokens is more than {provider.name} allows in {limit.seconds:.0f} s"
                    f" ({limit.tokens})"
                )
            total = sum(tokens for _, tokens in used)
            for at, tokens in used:
                if total + estimate <= limit.tokens:
                    break
                total -= tokens
                wait = max(wait, at + limit.seconds - now + MARGIN)
        return wait

    def _retry_after(self, headers: Mapping[str, str]) -> float | None:
        """The wait a provider asks for, in seconds or as a date; None when it asks for none."""
        value = headers.get("retry-after")
        if value is None:
            return None
        try:
            return max(float(value), 0.0)
        except ValueError:
            pass
        try:
            return max(email.utils.parsedate_to_datetime(value).timestamp() - self.clock(), 0.0)
        except (TypeError, ValueError):
            return None
