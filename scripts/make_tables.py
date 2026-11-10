"""Reads the two tables of decision 5 and writes their checks to docs/results.

    python scripts/make_tables.py

The BNSS First Schedule comes from data/raw/bnss.pdf; the old to new correspondence from CAPT Bhopal's
three tables in data/raw (scripts/get_data.py); the Acts' sections from data/parsed
(scripts/parse_corpus.py). Rows go to data/tables/first_schedule.jsonl and data/tables/correspondence.jsonl
(not committed). The results file, docs/results/m1_tables.md, counts the rows, checks every section a row
names against the Acts, checks the schedule's terms of punishment against the words of their sections,
checks that every word inside a correspondence table reached a row, and lists what stands out.

Two hand check sheets in docs/checks hold 50 rows each, drawn with a fixed seed: first_schedule.csv and
correspondence.csv. Each is written only when it does not exist, so the verdicts filled into it are never
overwritten: its verdict column takes "ok", or a note of what is wrong. A row that no longer matches the
reader's output is reported as changed since it was checked.
"""

import csv
import json
import platform
import random
import re
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pdfplumber

from dhara import DATA, REPO
from dhara.corpus import ACT, ACTS, TABLES
from dhara.tables import (
    CHANGES,
    Correspondence,
    ScheduleRow,
    base_section,
    correspondence,
    court_kind,
    first_schedule,
    kind,
    terms,
    words_kept,
)

RESULTS = REPO / "docs" / "results" / "m1_tables.md"
SEED = 5
SAMPLE = 50
SHAPES = ("one to one", "merged", "split", "merged and split")


@dataclass(frozen=True)
class Sheet:
    path: Path
    fields: tuple[str, ...]  # the columns a row is checked on, between its page and the verdict
    label: Callable[[dict[str, str]], str]  # how a row is named in the results


SCHEDULE_SHEET = Sheet(
    REPO / "docs" / "checks" / "first_schedule.csv",
    ("section", "offence", "punishment", "cognizable", "bailable", "court"),
    lambda row: f"section {row['section']}",
)
CORRESPONDENCE_SHEET = Sheet(
    REPO / "docs" / "checks" / "correspondence.csv",
    ("table", "new", "old", "old_sections", "subject", "summary", "change", "shape"),
    lambda row: f"{row['table'].removesuffix('_table')} {row['new']}",
)


def flat(row: Any) -> dict[str, str]:
    """A row as the strings a sheet holds."""
    return {
        name: " ".join(value) if isinstance(value, tuple) else "" if value is None else str(value)
        for name, value in asdict(row).items()
    }


def write_sheet(sheet: Sheet, rows: Sequence[dict[str, str]]) -> None:
    drawn = sorted(random.Random(SEED).sample(range(len(rows)), SAMPLE))
    sheet.path.parent.mkdir(parents=True, exist_ok=True)
    with sheet.path.open("w", encoding="utf8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(["n", "page", *sheet.fields, "verdict"])
        for n, index in enumerate(drawn, start=1):
            writer.writerow([n, rows[index]["page"], *(rows[index][name] for name in sheet.fields), ""])


def read_sheet(sheet: Sheet, rows: Sequence[dict[str, str]]) -> tuple[int, int, list[str], list[str]]:
    """How many rows were checked and found right, the notes on those found wrong, and the rows changed
    since they were checked."""
    current = {tuple(row[name] for name in sheet.fields) for row in rows}
    checked = right = 0
    wrong, changed = [], []
    with sheet.path.open(encoding="utf8", newline="") as found:
        for entry in csv.DictReader(found):
            verdict = (entry.get("verdict") or "").strip()
            if not verdict:
                continue
            checked += 1
            if tuple(entry[name] for name in sheet.fields) not in current:
                changed.append(f"row {entry['n']} ({sheet.label(entry)})")
            if verdict.lower() == "ok":
                right += 1
            else:
                wrong.append(f"row {entry['n']} ({sheet.label(entry)}, page {entry['page']}): {verdict}")
    return checked, right, wrong, changed


def hand_check(sheet: Sheet, rows: Sequence[dict[str, str]], against: str) -> list[str]:
    if not sheet.path.exists():
        return ["No sheet yet."]
    checked, right, wrong, changed = read_sheet(sheet, rows)
    where = f"`{sheet.path.relative_to(REPO)}`"
    if not checked:
        return [f"{SAMPLE} rows drawn with seed {SEED} into {where}; none checked yet."]
    lines = [f"{checked} of {SAMPLE} rows in {where} checked by hand against {against}: {right} right."]
    if wrong:
        lines += ["", *(f"* {note}" for note in wrong)]
    if changed:
        lines += ["", f"Changed since they were checked: {', '.join(changed)}."]
    return lines


def load_sections(act: str) -> dict[str, dict[str, Any]]:
    path = DATA / "parsed" / f"{act}.jsonl"
    return {section["number"]: section for section in map(json.loads, path.read_text(encoding="utf8").splitlines())}


def lowered(section: dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", " ".join([section["heading"], *section["paragraphs"]]).lower())


def schedule_report(rows: list[ScheduleRow], bns: dict[str, str]) -> list[str]:
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
        section = base_section(row.section or "")
        if not wanted or section not in bns:
            continue
        stated += 1
        absent = [term for term in wanted if term not in bns[section]]
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
    return [
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
        "### Punishment against the BNS",
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
        "### What stands out",
        "",
        *(unusual or ["Nothing."]),
        "",
        "### Hand check (decision 5)",
        "",
        *hand_check(SCHEDULE_SHEET, [flat(row) for row in part_one], "the schedule in the BNSS file"),
        "",
    ]


def correspondence_report(tables: dict[str, list[Correspondence]]) -> list[str]:
    counts, labels, unnamed, header = [], [], [], []
    sources = {source.key: source for source in TABLES}
    for key, rows in tables.items():
        new_act = ACT[sources[key].act]
        old_act = next(act for act in ACTS if act.replaced_by == new_act.key)
        new, old = load_sections(new_act.key), load_sections(old_act.key)
        without = [number for number in new if number not in {row.new_section for row in rows}]
        foreign = [row for row in rows if row.new_section not in new or any(s not in old for s in row.old_sections)]
        out_of_order, previous = [], 0
        for row in rows:
            digits = re.match(r"\d+", row.new_section)
            number = int(digits[0]) if digits else 0
            if number < previous:
                out_of_order.append(row)
            previous = number
        total, missing, repeated = words_kept(DATA / "raw" / f"{key}.pdf", rows)
        counts.append(
            f"| {new_act.short} to {old_act.short} | {len(rows)} | {len(without)} | {len(foreign)} "
            f"| {len(out_of_order)} | {total} | {sum(missing.values())} | {sum(repeated.values())} |"
        )
        header.append(f"{new_act.short} to {old_act.short}: " + ", ".join(sorted(missing.elements())))
        change, shape = Counter(row.change for row in rows), Counter(row.shape for row in rows)
        labels.append(
            f"| {new_act.short} to {old_act.short} | "
            + " | ".join(str(change[name]) for name in CHANGES)
            + " | "
            + " | ".join(str(shape[name]) for name in SHAPES)
            + " |"
        )
        named = {section for row in rows for section in row.old_sections}
        left = [n for n, section in old.items() if n not in named and section["status"] == "in force"]
        unnamed.append(f"* {old_act.short}: {', '.join(left) if left else 'none'}")
    everything = [row for rows in tables.values() for row in rows]
    return [
        "## The old to new correspondence",
        "",
        "| Table | Rows | New sections without a row | Rows naming a section the Acts lack | Rows out of order "
        "| Words inside its rules | Words no row holds | Words held twice |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        *counts,
        "",
        "CAPT Bhopal's three tables, one row for each provision of the new Act that CAPT compares. A row out "
        "of order names a section before the one above it. The words inside a table's rules are counted on the "
        "page and in the rows read from it: a word no row holds was lost, unless it is the table's header, "
        "which is not a row; a word held twice was read twice. The words no row holds: " + "; ".join(header) + ".",
        "",
        "| Table | Unchanged | Modified | New | Heading | One to one | Merged | Split | Merged and split |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        *labels,
        "",
        "What changed comes from CAPT's own words. Unchanged: the comparison says no more than \"No change\", "
        "that the old section is now a subsection of the new one with its heading dropped, or the note made "
        "once that \"Code\" becomes \"Sanhita\" throughout. New: the old column says New, or a dash. Heading: "
        "the old column is empty and rows for the section's subsections follow. Modified: anything else. "
        "The shape comes from the sections the rows name, taken whole: merged when a new section takes in "
        "several old ones, split when an old section went to several new ones.",
        "",
        "Old sections in force that no row names; each was dropped by the new Act, or went into a new section "
        "without CAPT naming it, and the text comparison of decision 24 tells which:",
        "",
        *unnamed,
        "",
        "### Hand check (decisions 5 and 24)",
        "",
        *hand_check(CORRESPONDENCE_SHEET, [flat(row) for row in everything], "CAPT's tables and their labels"),
        "",
    ]


def main() -> int:
    needed = [DATA / "raw" / f"{key}.pdf" for key in ("bnss", *(source.key for source in TABLES))]
    needed += [DATA / "parsed" / f"{act.key}.jsonl" for act in ACTS]
    for path in needed:
        if not path.exists():
            script = "get_data.py" if path.parent.name == "raw" else "parse_corpus.py"
            print(f"missing {path.relative_to(REPO)}; run scripts/{script} first", file=sys.stderr)
            return 1
    schedule = first_schedule(DATA / "raw" / "bnss.pdf")
    tables = {source.key: correspondence(DATA / "raw" / f"{source.key}.pdf", source.key) for source in TABLES}
    out = DATA / "tables"
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("first_schedule", schedule), ("correspondence", [r for v in tables.values() for r in v])):
        (out / f"{name}.jsonl").write_text(
            "".join(json.dumps(asdict(row), ensure_ascii=False) + "\n" for row in rows), encoding="utf8"
        )
    part_one = [flat(row) for row in schedule if row.part == "I"]
    pairs = [flat(row) for table in tables.values() for row in table]
    for sheet, drawn_from in ((SCHEDULE_SHEET, part_one), (CORRESPONDENCE_SHEET, pairs)):
        if not sheet.path.exists():
            write_sheet(sheet, drawn_from)
            print(f"wrote {sheet.path.relative_to(REPO)}, {SAMPLE} rows to check by hand")
    bns = {number: lowered(section) for number, section in load_sections("bns").items()}
    lines = [
        "# M1: the tables",
        "",
        "Made by `python scripts/make_tables.py` from `data/raw` and the parsed Acts (decisions 5 and 24).",
        f"Machine: {platform.system()} {platform.release()} {platform.machine()}; Python "
        f"{platform.python_version()}; pdfplumber {pdfplumber.__version__}.",
        "",
        *schedule_report(schedule, bns),
        *correspondence_report(tables),
    ]
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text("\n".join(lines), encoding="utf8")
    rows_read = sum(len(rows) for rows in tables.values())
    print(f"{len(schedule)} schedule rows, {rows_read} correspondence rows; wrote data/tables and "
          f"{RESULTS.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
