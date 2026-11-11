"""Sends one short question to every API model Dhara uses, once asking for plain text and once for JSON
that must follow a small schema, and writes what came back to docs/results/m1_accounts.md: whether each
call worked, whether the answer was right, the model version that answered, tokens, seconds, and the
rate limit counts the provider sent with its answer. It checks the keys, the model names and the shape
of every request before any long run (decisions 14 and 15).

    python scripts/check_models.py

Every call goes through the model client, so a second run answers from its cache and sends only the
calls that failed before. The local models are left to the benchmark (decision 17).
"""

import argparse
import json
import platform
from dataclasses import dataclass

from dhara import REPO
from dhara.llm import MODELS, PROVIDERS, Client, LlmError, Settings

RESULTS = REPO / "docs" / "results" / "m1_accounts.md"
QUESTION = "Which section of the Bharatiya Nyaya Sanhita, 2023 defines theft?"
ASKS = {
    "text": f"{QUESTION} Reply with the section number only.",
    "json": f"{QUESTION} Reply in JSON with the Act's short name and the section number.",
}
SCHEMA = {
    "type": "object",
    "properties": {"act": {"type": "string"}, "section": {"type": "string"}},
    "required": ["act", "section"],
    "additionalProperties": False,
}
RIGHT = "303"  # BNS section 303, Theft
# each model's own way of asking for little or no thinking; NVIDIA's default for Mistral Small 4 is high
REASONING: dict[str, str | None] = {
    "mistral-small-4": "none",
    "mistral-large-3": None,
    "gpt-oss-120b": "low",
    "qwen3.8-27b": "none",
    "gemini-3.5-flash-lite": "minimal",
}
API = [name for name, model in MODELS.items() if PROVIDERS[model.provider].wire != "ollama"]


@dataclass
class Check:
    name: str
    asked: str
    error: str = ""
    right: bool = False
    reply: str = ""
    version: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    thinking: int | None = None
    seconds: float = 0.0
    finish: str = ""
    limits: dict[str, str] | None = None


def is_right(asked: str, text: str) -> bool:
    if asked == "text":
        return RIGHT in text
    try:
        answer = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(answer, dict) and isinstance(answer.get("act"), str) and RIGHT in str(answer.get("section"))


def check(llm: Client, name: str) -> list[Check]:
    checks = []
    for asked, content in ASKS.items():
        schema = SCHEMA if asked == "json" else None
        settings = Settings(max_tokens=1_024, reasoning=REASONING.get(name), schema=schema)
        try:
            reply = llm.ask(name, [{"role": "user", "content": content}], settings)
        except LlmError as error:
            # paths inside the repository are written from its root, so no home folder is committed
            checks.append(Check(name, asked, error=str(error).replace(f"{REPO}/", "")))
            continue
        checks.append(
            Check(
                name,
                asked,
                right=is_right(asked, reply.text),
                reply=reply.text,
                version=reply.model,
                tokens_in=reply.tokens_in,
                tokens_out=reply.tokens_out,
                thinking=reply.tokens_thinking,
                seconds=reply.seconds,
                finish=reply.finish,
                limits=reply.limits,
            )
        )
    return checks


def cell(text: str, width: int = 60) -> str:
    one_line = " ".join(text.split())
    short = one_line if len(one_line) <= width else one_line[: width - 3] + "..."
    return short.replace("|", "\\|")


def report(checks: list[Check]) -> str:
    lines = [
        "# M1: the free accounts and the model client",
        "",
        "Made by `python scripts/check_models.py` (decisions 14 and 15): one question to every API model, "
        "asking once for plain text and once for JSON that follows a small schema. The right answer is BNS "
        f"section {RIGHT} (Theft).",
        f"Machine: {platform.system()} {platform.release()} {platform.machine()}; Python "
        f"{platform.python_version()}.",
        "",
        "## Calls",
        "",
        "| Model | Asked for | Worked | Right | Reply | Version that answered | Tokens in | Tokens out | Thinking "
        "| Seconds | Finish |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for c in checks:
        if c.error:
            lines.append(f"| `{c.name}` | {c.asked} | no | | | | | | | | |")
            continue
        thinking = "" if c.thinking is None else str(c.thinking)
        lines.append(
            f"| `{c.name}` | {c.asked} | yes | {'yes' if c.right else 'no'} | {cell(c.reply)} | `{c.version}` "
            f"| {c.tokens_in} | {c.tokens_out} | {thinking} | {c.seconds:.2f} | {c.finish} |"
        )
    failed = [c for c in checks if c.error]
    if failed:
        lines += ["", "## Calls that failed", ""]
        lines += [f"* `{c.name}`, {c.asked}: {cell(c.error, 300)}" for c in failed]
    lines += [
        "",
        "## Limits the providers reported",
        "",
        "The counts each provider sent with its last answer here; a provider that sends none shows its limits "
        "only in its console.",
        "",
        "| Model | Counts |",
        "|---|---|",
    ]
    last: dict[str, dict[str, str]] = {}
    for c in checks:
        if c.limits is not None:
            last[c.name] = c.limits
    for name, limits in last.items():
        counts = ", ".join(f"`{header}` {value}" for header, value in sorted(limits.items())) or "none sent"
        lines.append(f"| `{name}` | {counts} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    argparse.ArgumentParser(description="Sends one short question to every API model Dhara uses.").parse_args()
    with Client() as llm:
        checks = [found for name in API for found in check(llm, name)]
    for c in checks:
        outcome = f"failed: {c.error}" if c.error else f"{'right' if c.right else 'wrong'}: {cell(c.reply, 50)}"
        print(f"{c.name:22} {c.asked:4} {outcome}")
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(report(checks), encoding="utf-8")
    print(f"wrote {RESULTS.relative_to(REPO)}")
    return 1 if any(c.error for c in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
