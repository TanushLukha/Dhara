"""Downloads the Acts into data/raw and records each file's URL, size and SHA256 in data/MANIFEST.json.

    python scripts/get_data.py            # what is missing or has changed
    python scripts/get_data.py --force    # every file again

India Code is slow and often answers with a server error for a while, so each file is retried with a
growing wait, and one failure does not stop the others. Run it again later to finish.
"""

import argparse
import sys

from dhara import DATA
from dhara.corpus import SOURCES, download


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--force", action="store_true", help="download every file again")
    args = parser.parse_args()
    manifest, failures = download(SOURCES, DATA / "raw", DATA / "MANIFEST.json", force=args.force)
    for key in sorted(manifest):
        entry = manifest[key]
        print(f"{key:6} {entry['bytes']:>11,} bytes  sha256 {entry['sha256'][:16]}  {entry['url']}")
    for failure in failures:
        print(f"failed: {failure}", file=sys.stderr)
    print(f"{len(manifest)} of {len(SOURCES)} files in data/raw; manifest in data/MANIFEST.json")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
