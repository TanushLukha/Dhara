"""Reads the BNSS First Schedule into rows and writes the check of decision 5 to docs/results.

    python scripts/make_tables.py

Needs data/raw/bnss.pdf (scripts/get_data.py) and data/parsed/bns.jsonl (scripts/parse_corpus.py).
Rows go to data/tables/first_schedule.jsonl (not committed). The results file, docs/results/m1_tables.md,
counts the rows, checks every row's section against the BNS and the order of the sections, checks each
stated term of punishment against the words of its section, and lists what stands out.

The hand check sheet, docs/checks/first_schedule.csv, holds 50 rows of Part I drawn with a fixed seed.
It is written only when it does not exist, so the verdicts filled into it are never overwritten: its
verdict column takes "ok", or a note of what is wrong. A row that no longer matches the parser's output
is reported as changed since it was checked.
"""

import csv
import json
import platform
import random
import re
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import pdfplumber

from dhara import DATA, REPO
from dhara.tables import ScheduleRow, base_section, court_kind, first_schedule, kind, terms

RESULTS = REPO / "docs" / "results" / "m1_tables.md"
SHEET = REPO / "docs" / "checks" / "first_schedule.csv"
SEED = 5
SAMPLE = 50
FIELDS = ["section", "offence", "punishment", "cognizable", "bailable", "court"]


def load_bns(path: Path) -> dict[str, str]:
    """Each BNS section's heading and text, in lower case, keyed by its number."""
    sections = {}
    for line in path.read_text(encoding="utf8").splitlines():
        section = json.loads(line)
        text = " ".join([section["heading"], *section["paragraphs"]]).lower()
        sections[section["number"]] = re.sub(r"\s+", " ", text)
    return sections


def write_sheet(rows: list[ScheduleRow]) -> None:
    part_one = [row for row in rows if row.part == "I"]
    drawn = sorted(random.Random(SEED).sample(range(len(part_one)), SAMPLE))
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    with SHEET.open("w", encoding="utf8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["n", "page", *FIELDS, "verdict"])
        for n, index in enumerate(drawn, start=1):
            row = part_one[index]
            writer.writerow([n, row.page, *(getattr(row, name) or "" for name in FIELDS), ""])


def read_sheet(rows: list[ScheduleRow]) -> tuple[int, int, list[str], list[str]]:
    """How many rows were checked and found right, the notes on those found wrong, and the rows changed
    since they were checked."""
    current = {tuple(getattr(row, name) or "" for name in FIELDS) for row in rows}
    checked = right = 0
    wrong, changed = [], []
    with SHEET.open(encoding="utf8", newline="") as sheet:
        for entry in csv.DictReader(sheet):
            verdict = (entry.get("verdict") or "").strip()
            if not verdict:
                continue
            checked += 1
            if tuple(entry[name] for name in FIELDS) not in current:
                changed.append(f"row {entry['n']} (section {entry['section']})")
            if verdict.lower() == "ok":
                right += 1
            else:
                wrong.append(f"row {entry['n']} (section {entry['section']}, page {entry['page']}): {verdict}")
    return checked, right, wrong, changed


def report(rows: list[ScheduleRow], bns: dict[str, str]) -> str:
    part_one = [row for row in rows if row.part == "I"]
    part_two = [row for row in rows if row.part == "II"]
    sections = {base_section(row.section or "") for row in part_one}
    unknown = [row for row in part_one if base_section(row.section or "") not in bns]
    out_of_order, previous = [], 0
    for row in part_one:
        digits = re.match(r"\d+", row.section or "")
        number = int(digits[0]) if digits else 0
        if number < previous:
            out_of_order.append(row)
        previous = number
    lead_ins = [row for row in part_one if row.lead_in]
    stated = found = 0
    missed = []
    for row in part_one:
        wanted = terms(row.punishment or "")
        if not wanted or base_section(row.section or "") not in bns:
            continue
        stated += 1
        text = bns[base_section(row.section or "") or ""]
        absent = [term for term in wanted if term not in text]
        if absent:
            missed.append(f"* section {row.section}: \"{row.punishment}\"; not in the section: {', '.join(absent)}")
        else:
            found += 1
    punishing = [n for n, text in bns.items() if re.search(r"shall be punished|be punishable", text)]
    unlisted = [n for n in punishing if n not in sections]
    classes = {
        "Cognizable": Counter(kind(row.cognizable, "cognizable") for row in rows),
        "Bailable": Counter(kind(row.bailable, "bailable") for row in rows),
        "Court": Counter(court_kind(row.court) for row in rows),
    }
    unusual = [
        f"* section {row.section or 'none'}, page {row.page}: {name.lower()} \"{value}\""
        for row in rows
        for name, value, label in (
            ("Cognizable", row.cognizable, kind(row.cognizable, "cognizable")),
            ("Bailable", row.bailable, kind(row.bailable, "bailable")),
            ("Court", row.court, court_kind(row.court)),
        )
        if label in ("other", "conditional")
    ]
    lines = [
        "# M1: the tables",
        "",
        "Made by `python scripts/make_tables.py` from `data/raw/bnss.pdf` and the parsed BNS (decision 5).",
        f"Machine: {platform.system()} {platform.release()} {platform.machine()}; Python "
        f"{platform.python_version()}; pdfplumber {pdfplumber.__version__}.",
        "",
        "## The BNSS First Schedule",
        "",
        "| Part | Rows | BNS sections | Rows opened by a lead in | Rows naming no BNS section | Rows out of order |",
        "|---|---:|---:|---:|---:|---:|",
        f"| I, offences under the BNS | {len(part_one)} | {len(sections)} | {len(lead_ins)} | {len(unknown)} "
        f"| {len(out_of_order)} |",
        f"| II, offences under other laws | {len(part_two)} | | | | |",
        "",
        "Rows naming no BNS section: a row whose section number is not a section of the parsed BNS. Rows out "
        "of order: a row whose section comes before the row above it; the schedule follows the BNS, so either "
        "would show a number read wrongly or put on the wrong row. A lead in opens an offence that the "
        "schedule then splits into clauses, (a) and (b); each clause is a row of its own, with the lead in.",
        "",
        "| Column | Its values, as classes |",
        "|---|---|",
        *(
            f"| {column} | " + ", ".join(f"{name} {count}" for name, count in counter.most_common()) + " |"
            for column, counter in classes.items()
        ),
        "",
        "Each value as one class. Depends: the value turns on another offence, or on where the offence is "
        "committed (\"According as offence abetted is cognizable or non-cognizable\", \"Court by which offence "
        "abetted is triable\"). Conditional: the value states a condition (\"only on the complaint of the "
        "victim\"). Other: the value could not be classed.",
        "",
        "## Punishment against the BNS",
        "",
        f"{stated} rows of Part I state a term of punishment (years, months, life or death); for {found}, every "
        "term appears in the words of the row's BNS section (7 years as \"seven years\"). The rest state none "
        "(\"Same as for offence abetted\", \"Fine\").",
        "",
        *(missed or ["No stated term is missing from its section."]),
        "",
        "BNS sections whose words punish (\"shall be punished\", \"be punishable\") but which no row of Part I "
        f"names: {', '.join(unlisted) if unlisted else 'none'}.",
        "",
        "## What stands out",
        "",
        *(unusual or ["Nothing."]),
        "",
        "## Hand check (decision 5)",
        "",
    ]
    if SHEET.exists():
        checked, right, wrong, changed = read_sheet(rows)
        if checked:
            lines.append(f"{checked} of {SAMPLE} rows checked by hand against the schedule and the BNS: {right} right.")
            if wrong:
                lines += ["", *(f"* {note}" for note in wrong)]
            if changed:
                lines += ["", f"Changed since they were checked: {', '.join(changed)}."]
        else:
            lines.append(f"{SAMPLE} rows drawn with seed {SEED} into `{SHEET.relative_to(REPO)}`; none checked yet.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    pdf, parsed = DATA / "raw" / "bnss.pdf", DATA / "parsed" / "bns.jsonl"
    for needed, script in ((pdf, "get_data.py"), (parsed, "parse_corpus.py")):
        if not needed.exists():
            print(f"missing {needed.relative_to(REPO)}; run scripts/{script} first", file=sys.stderr)
            return 1
    rows = first_schedule(pdf)
    out = DATA / "tables" / "first_schedule.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(asdict(row), ensure_ascii=False) + "\n" for row in rows), encoding="utf8")
    if not SHEET.exists():
        write_sheet(rows)
        print(f"wrote {SHEET.relative_to(REPO)}, {SAMPLE} rows to check by hand")
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(report(rows, load_bns(parsed)), encoding="utf8")
    print(f"{len(rows)} rows; wrote {out.relative_to(REPO)} and {RESULTS.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
