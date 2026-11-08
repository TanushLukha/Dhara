import json
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from urllib.parse import urlparse

import pytest

from dhara.corpus import ACT, ACTS, SOURCES, Source, SourceError, check, download, fetch, sha256

PDF = b"%PDF-1.7\n a tiny stand in for an Act\n%%EOF\n"


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.org/a.pdf", code, "error", Message(), None)


class FakeServer:
    """Answers with the given replies in turn: bytes, or an exception to raise."""

    def __init__(self, *replies: bytes | Exception) -> None:
        self.replies = list(replies)
        self.urls: list[str] = []

    def __call__(self, request: urllib.request.Request, timeout: float) -> bytes:
        self.urls.append(request.full_url)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def no_sleep(seconds: float) -> None:
    pass


def test_every_act_and_source_is_consistent() -> None:
    assert len(ACT) == len(ACTS) == 6
    assert {act.replaced_by for act in ACTS if act.replaced_by} == {"bns", "bnss", "bsa"}
    keys = [source.key for source in SOURCES]
    assert len(keys) == len(set(keys))
    for source in SOURCES:
        assert source.act in ACT
        url = urlparse(source.url)
        assert url.scheme == "https"
        assert url.hostname in {"www.indiacode.nic.in", "indiacode.nic.in"}
        assert url.path.endswith(".pdf")


def test_server_errors_are_retried_with_a_doubling_wait() -> None:
    server = FakeServer(http_error(504), http_error(503), PDF)
    waits: list[float] = []
    assert fetch("https://example.org/a.pdf", opener=server, wait=5.0, sleep=waits.append) == PDF
    assert waits == [5.0, 10.0]
    assert server.urls == ["https://example.org/a.pdf"] * 3


def test_a_missing_file_is_not_retried() -> None:
    server = FakeServer(http_error(404), PDF)
    with pytest.raises(SourceError, match="HTTP 404"):
        fetch("https://example.org/a.pdf", opener=server, sleep=no_sleep)
    assert len(server.urls) == 1


def test_giving_up_after_the_last_retry() -> None:
    server = FakeServer(*[http_error(504)] * 3)
    with pytest.raises(SourceError, match="after 3 tries"):
        fetch("https://example.org/a.pdf", opener=server, retries=2, sleep=no_sleep)


def test_only_the_pinned_pdf_passes_the_check() -> None:
    source = Source("bns", "bns", "https://example.org/a.pdf", "test")
    assert check(source, PDF) == sha256(PDF)
    with pytest.raises(SourceError, match="not a PDF"):
        check(source, b"<html>Gateway Timeout</html>")
    pinned = Source("bns", "bns", "https://example.org/a.pdf", "test", sha256=sha256(b"%PDF-1.7 another text"))
    with pytest.raises(SourceError, match="has changed"):
        check(pinned, PDF)


def test_download_records_files_and_skips_them_the_next_time(tmp_path: Path) -> None:
    sources = [Source("bns", "bns", "https://example.org/bns.pdf", "test")]
    raw, manifest_path = tmp_path / "raw", tmp_path / "MANIFEST.json"
    manifest, failures = download(sources, raw, manifest_path, opener=FakeServer(PDF), sleep=no_sleep)
    assert failures == []
    assert (raw / "bns.pdf").read_bytes() == PDF
    assert manifest["bns"]["sha256"] == sha256(PDF)
    assert manifest["bns"]["bytes"] == len(PDF)
    assert json.loads(manifest_path.read_text())["bns"]["url"] == "https://example.org/bns.pdf"
    untouched = FakeServer()
    download(sources, raw, manifest_path, opener=untouched, sleep=no_sleep)
    assert untouched.urls == []
    again = FakeServer(PDF)
    download(sources, raw, manifest_path, opener=again, force=True, sleep=no_sleep)
    assert again.urls == ["https://example.org/bns.pdf"]


def test_one_failure_does_not_stop_the_others(tmp_path: Path) -> None:
    sources = [
        Source("bns", "bns", "https://example.org/bns.pdf", "test"),
        Source("bsa", "bsa", "https://example.org/bsa.pdf", "test"),
    ]
    server = FakeServer(http_error(404), PDF)
    manifest, failures = download(sources, tmp_path / "raw", tmp_path / "MANIFEST.json", opener=server, sleep=no_sleep)
    assert list(manifest) == ["bsa"]
    assert len(failures) == 1 and "HTTP 404" in failures[0]
