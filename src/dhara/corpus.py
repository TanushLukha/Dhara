"""The six Acts, and where each text is downloaded from.

Every source is pinned (decision 3): once a downloaded file has been checked, its SHA256 is written
here, and a later download with a different hash is refused, so every number names the exact text it
was measured on. Downloads go to data/raw and are recorded in data/MANIFEST.json; neither is committed.
"""

import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict, cast


@dataclass(frozen=True)
class Act:
    key: str
    short: str
    title: str
    citation: str
    last_section: int  # the highest numbered section in the arrangement of sections
    replaced_by: str | None = None


ACTS: tuple[Act, ...] = (
    Act("bns", "BNS", "The Bharatiya Nyaya Sanhita, 2023", "Act 45 of 2023", 358),
    Act("bnss", "BNSS", "The Bharatiya Nagarik Suraksha Sanhita, 2023", "Act 46 of 2023", 531),
    Act("bsa", "BSA", "The Bharatiya Sakshya Adhiniyam, 2023", "Act 47 of 2023", 170),
    Act("ipc", "IPC", "The Indian Penal Code, 1860", "Act 45 of 1860", 511, replaced_by="bns"),
    Act("crpc", "CrPC", "The Code of Criminal Procedure, 1973", "Act 2 of 1974", 484, replaced_by="bnss"),
    Act("iea", "IEA", "The Indian Evidence Act, 1872", "Act 1 of 1872", 167, replaced_by="bsa"),
)
ACT = {act.key: act for act in ACTS}


@dataclass(frozen=True)
class Source:
    key: str  # the file's name in data/raw, without .pdf
    act: str  # the Act whose text this is
    url: str
    origin: str  # where the file sits, in words
    sha256: str | None = None  # pinned once the downloaded file has been checked


INDIA_CODE = "https://www.indiacode.nic.in/bitstream/123456789"

# Each URL was opened and its first pages read before it was listed here. The IPC, the Evidence Act and
# the commencement notifications join once their sources are settled (decision 3).
SOURCES: tuple[Source, ...] = (
    Source("bns", "bns", f"{INDIA_CODE}/20062/1/a202345.pdf", "India Code, the central Act"),
    Source(
        "bnss",
        "bnss",
        "https://indiacode.nic.in/bitstream/123456789/20099/3/a2023-46.pdf",
        "India Code, the central Act",
    ),
    Source("bsa", "bsa", f"{INDIA_CODE}/20063/1/aa202347.pdf", "India Code, the central Act"),
    Source(
        "crpc",
        "crpc",
        f"{INDIA_CODE}/13624/1/the_code_of_criminal_procedure%2c_1973.pdf",
        "India Code, Delhi collection, which carries the central text as last amended",
    ),
)

USER_AGENT = "dhara/0.1 (downloads the Acts once, for research)"
TIMEOUT = 120.0  # seconds; India Code is slow
RETRIES = 4  # after the first try, waiting 5, 10, 20 and 40 seconds
WAIT = 5.0


class SourceError(Exception):
    """A download that failed, or a file that is not the one pinned."""


class Entry(TypedDict):
    url: str
    origin: str
    sha256: str
    bytes: int
    downloaded: str  # UTC, ISO 8601


Opener = Callable[[urllib.request.Request, float], bytes]


def _open(request: urllib.request.Request, timeout: float) -> bytes:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body: bytes = response.read()
    return body


def fetch(
    url: str,
    opener: Opener = _open,
    retries: int = RETRIES,
    wait: float = WAIT,
    sleep: Callable[[float], None] = time.sleep,
) -> bytes:
    """The file at url. Server errors, rate limits and timeouts are retried with a doubling wait;
    other client errors (404, 403) are not, since waiting does not change them."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries + 1):
        try:
            return opener(request, TIMEOUT)
        except (urllib.error.URLError, TimeoutError) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code < 500 and error.code != 429:
                raise SourceError(f"{url}: HTTP {error.code}") from error
            if attempt == retries:
                raise SourceError(f"{url}: {error} (after {retries + 1} tries)") from error
            sleep(wait * 2**attempt)
    raise AssertionError("unreachable")


def sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def check(source: Source, body: bytes) -> str:
    """The file's SHA256, once it is shown to be a PDF and, when pinned, the pinned file."""
    if not body.startswith(b"%PDF-"):
        raise SourceError(f"{source.key}: not a PDF (it starts {body[:40]!r})")
    digest = sha256(body)
    if source.sha256 is not None and digest != source.sha256:
        raise SourceError(
            f"{source.key}: SHA256 {digest} differs from the pinned {source.sha256}, so the file at the source "
            "has changed; check the new text before pinning it"
        )
    return digest


def read_manifest(path: Path) -> dict[str, Entry]:
    if not path.exists():
        return {}
    return cast(dict[str, Entry], json.loads(path.read_text(encoding="utf8")))


def write_manifest(path: Path, manifest: dict[str, Entry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n", encoding="utf8")


def download(
    sources: Sequence[Source],
    raw: Path,
    manifest_path: Path,
    opener: Opener = _open,
    force: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[dict[str, Entry], list[str]]:
    """Downloads what is missing or changed into raw and records it; returns the manifest and the
    failures, one line each. A failure does not stop the others: India Code often fails for a while."""
    raw.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(manifest_path)
    failures = []
    for source in sources:
        path = raw / f"{source.key}.pdf"
        try:
            if path.exists() and not force and source.key in manifest:
                body = path.read_bytes()
                if check(source, body) == manifest[source.key]["sha256"]:
                    continue
            body = fetch(source.url, opener=opener, sleep=sleep)
            digest = check(source, body)
        except SourceError as error:
            failures.append(str(error))
            continue
        path.write_bytes(body)
        manifest[source.key] = Entry(
            url=source.url,
            origin=source.origin,
            sha256=digest,
            bytes=len(body),
            downloaded=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        write_manifest(manifest_path, manifest)
    return manifest, failures
