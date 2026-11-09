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
    url: str  # India Code's file
    origin: str  # where the file sits, in words
    mirror: str | None = None  # the Internet Archive's copy of the same file, used when url fails
    sha256: str | None = None  # pinned once the downloaded file has been checked


INDIA_CODE = "https://www.indiacode.nic.in/bitstream/123456789"
ARCHIVE = "https://web.archive.org/web"  # a capture's timestamp, then "id_/" and the URL: the original bytes


def archived(timestamp: str, url: str) -> str:
    return f"{ARCHIVE}/{timestamp}id_/{url}"


# Each India Code file was opened and its first pages read before it was listed, except the IPC's:
# India Code's current pages for the IPC list no file, and the Internet Archive holds the file India Code
# served before the repeal. Every capture below was listed by the Archive with status 200. A hash is
# pinned once its downloaded file was read: title, as on note, and the last section present in both the
# arrangement and the body. The commencement notifications join once their sources are settled
# (decision 3).
SOURCES: tuple[Source, ...] = (
    Source(
        "bns",
        "bns",
        f"{INDIA_CODE}/20062/1/a202345.pdf",
        "India Code, the central Act",
        archived("20260212071046", f"{INDIA_CODE}/20062/1/a202345.pdf"),
        sha256="ff92dcc72778944011807644b6033b1140ddbe6d7e9f82ac32fd419dae03aa86",
    ),
    Source(
        "bnss",
        "bnss",
        "https://indiacode.nic.in/bitstream/123456789/20099/3/a2023-46.pdf",
        "India Code, the central Act",
        # the Archive holds the same India Code file (item 20099, file 3) under another name in its URL
        archived("20250318103613", f"{INDIA_CODE}/20099/3/aa2023-46.pdf"),
        sha256="8047fe1de6092e23240d059b45cab8d4d93a1b77fa5de7f91ec12ac662c56512",
    ),
    Source(
        "bsa",
        "bsa",
        f"{INDIA_CODE}/20063/1/aa202347.pdf",
        "India Code, the central Act",
        archived("20260604191823", f"{INDIA_CODE}/20063/1/aa202347.pdf"),
        sha256="993882ad0ae7ded6ae8087351edd61caeb6faa1a2d6c8fff8c269a9cf149b9ac",
    ),
    Source(
        "ipc",
        "ipc",
        f"{INDIA_CODE}/2263/1/A1860-45.pdf",
        "India Code, the central Act as served before the repeal",
        archived("20230501052500", f"{INDIA_CODE}/2263/1/A1860-45.pdf"),
        sha256="2bbc5b1a7b9567a1811fc376b0cec037f8fe7b90a680d8177abc6b06364fc76a",
    ),
    Source(
        "crpc",
        "crpc",
        f"{INDIA_CODE}/13624/1/the_code_of_criminal_procedure%2c_1973.pdf",
        "India Code, Delhi collection, which carries the central text as last amended",
        archived("20251206113418", f"{INDIA_CODE}/13624/1/the_code_of_criminal_procedure%2C_1973.pdf"),
        sha256="2f28d487c18d33f65195d7ab99cb5dc8fd4dcf232c7deb18dee7f8fa289891b9",
    ),
    Source(
        "iea",
        "iea",
        f"{INDIA_CODE}/15351/1/iea_1872.pdf",
        "India Code, Chandigarh collection, which carries the central text as last amended",
        archived("20250928231439", f"{INDIA_CODE}/15351/1/iea_1872.pdf"),
        sha256="62b33659545e001223a99364447e9314d5372f1791db5cccadd87a08c267eb91",
    ),
)

USER_AGENT = "dhara/0.1 (downloads the Acts once, for research)"
TIMEOUT = 120.0  # seconds; India Code is slow
RETRIES = 4  # after the first try, waiting 5, 10, 20 and 40 seconds
WAIT = 5.0


class SourceError(Exception):
    """A download that failed, or a file that is not the one pinned."""


class ChangedError(SourceError):
    """The source now serves a different file from the one pinned: its new text must be checked first."""


class Entry(TypedDict):
    url: str  # India Code's file
    fetched_from: str  # url, or the Internet Archive's copy of it
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
    """The file at url. Server errors, redirect failures, rate limits and timeouts are retried with a
    doubling wait; other client errors (404, 403) are not, since waiting does not change them."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries + 1):
        try:
            return opener(request, TIMEOUT)
        except (urllib.error.URLError, TimeoutError) as error:
            reason = describe(error)
            if isinstance(error, urllib.error.HTTPError) and 400 <= error.code < 500 and error.code != 429:
                raise SourceError(f"{url}: {reason}") from error
            if attempt == retries:
                raise SourceError(f"{url}: {reason} (after {retries + 1} tries)") from error
            sleep(wait * 2**attempt)
    raise AssertionError("unreachable")


def describe(error: Exception) -> str:
    """An error in one line; for an HTTP error its code, its reason and where it redirected, if it did."""
    if isinstance(error, urllib.error.HTTPError):
        location = error.headers.get("Location") if error.headers is not None else None
        where = f", redirected to {location}" if location else ""
        return f"HTTP {error.code} {error.reason}{where}"
    return str(error)


def sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def check(source: Source, body: bytes) -> str:
    """The file's SHA256, once it is shown to be a PDF and, when pinned, the pinned file."""
    if not body.startswith(b"%PDF-"):
        raise SourceError(f"{source.key}: not a PDF (it starts {body[:40]!r})")
    digest = sha256(body)
    if source.sha256 is not None and digest != source.sha256:
        raise ChangedError(
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


def fetch_source(
    source: Source, opener: Opener = _open, retries: int = RETRIES, sleep: Callable[[float], None] = time.sleep
) -> tuple[bytes, str, str]:
    """The source's file, its SHA256 and the URL it came from: India Code first, then its mirror."""
    reasons = []
    for url in (source.url, source.mirror):
        if url is None:
            continue
        try:
            body = fetch(url, opener=opener, retries=retries, sleep=sleep)
            return body, check(source, body), url
        except ChangedError:
            raise  # a changed file is news to check, not a reason to use the mirror
        except SourceError as error:
            reasons.append(str(error))
    raise SourceError("; then ".join(reasons))


def download(
    sources: Sequence[Source],
    raw: Path,
    manifest_path: Path,
    opener: Opener = _open,
    force: bool = False,
    retries: int = RETRIES,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[dict[str, Entry], list[str]]:
    """Downloads what is missing or changed into raw and records it; returns the manifest and the
    failures, one line per source. The manifest says whether a file came from India Code or from its
    mirror; either way it passed the same check. A failure does not stop the others: India Code often
    fails for a while."""
    raw.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(manifest_path)
    failures = []
    for source in sources:
        path = raw / f"{source.key}.pdf"
        try:
            if path.exists() and not force and source.key in manifest:
                if check(source, path.read_bytes()) == manifest[source.key]["sha256"]:
                    continue
            body, digest, url = fetch_source(source, opener=opener, retries=retries, sleep=sleep)
        except SourceError as error:
            failures.append(str(error))
            continue
        path.write_bytes(body)
        manifest[source.key] = Entry(
            url=source.url,
            fetched_from=url,
            origin=source.origin,
            sha256=digest,
            bytes=len(body),
            downloaded=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        write_manifest(manifest_path, manifest)
    return manifest, failures
