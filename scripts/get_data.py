"""Downloads the Acts and the correspondence tables into data/raw and records each file's URL, size and
SHA256 in data/MANIFEST.json.

    python scripts/get_data.py            # what is missing or has changed
    python scripts/get_data.py --force    # every file again
    python scripts/get_data.py --retries 1    # give up on a failing URL sooner

India Code is slow and often answers with a server error for a while, so each file is retried with a
growing wait, then taken from the Internet Archive's copy of the same India Code file where there is
one; the SHA256 check is the same either way, and one failure does not stop the others. Run it again
later to finish.
"""

import argparse
import sys

from dhara import DATA
from dhara.corpus import RETRIES, SOURCES, TABLES, download


def main() -> int:
    parser = argparse.ArgumentParser(description="Downloads the Acts and the correspondence tables into data/raw.")
    parser.add_argument("--force", action="store_true", help="download every file again")
    parser.add_argument("--retries", type=int, default=RETRIES, help=f"tries after the first per URL ({RETRIES})")
    args = parser.parse_args()
    sources = SOURCES + TABLES
    manifest, failures = download(sources, DATA / "raw", DATA / "MANIFEST.json", force=args.force, retries=args.retries)
    for key in sorted(manifest):
        entry = manifest[key]
        via = "" if entry.get("fetched_from", entry["url"]) == entry["url"] else "  (the Internet Archive's copy)"
        print(f"{key:15} {entry['bytes']:>11,} bytes  sha256 {entry['sha256'][:16]}  {entry['url']}{via}")
    for failure in failures:
        print(f"failed: {failure}", file=sys.stderr)
    print(f"{len(manifest)} of {len(sources)} files in data/raw; manifest in data/MANIFEST.json")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
