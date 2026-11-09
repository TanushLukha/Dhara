"""Parses the six Acts in data/raw into sections and writes the check of decisions 4 and 30 to docs/results.

    python scripts/parse_corpus.py

Sections go to data/parsed/<act>.jsonl, one JSON object a line (not committed). The results file,
docs/results/m1_corpus.md, lists for each Act its pages, the arrangement's entries, the sections found,
the entries never found, gaps in the numbering, the section like lines left unused, headings that
disagree with the arrangement, what was kept apart from the text (footnotes, state amendments, group
headings), and how the paragraph breaks behave, so the check can be read at a glance.
"""

import json
import platform
import sys
from dataclasses import asdict
from pathlib import Path

import pdfplumber

from dhara import DATA, REPO
from dhara.corpus import ACT, SOURCES, read_manifest
from dhara.parse import Parsed, group_starts, groups_that_differ, heading_agrees, parse

RESULTS = REPO / "docs" / "results" / "m1_corpus.md"


def write_sections(parsed: Parsed, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / f"{parsed.act}.jsonl").open("w", encoding="utf8") as out:
        for section in parsed.sections:
            out.write(json.dumps(asdict(section), ensure_ascii=False) + "\n")


def share(part: int, whole: int) -> str:
    return f"{part} of {whole} ({100 * part / whole:.1f}%)" if whole else "none"


def report(results: list[Parsed]) -> str:
    manifest = read_manifest(DATA / "MANIFEST.json")
    files, sections, apart, breaks, notes = [], [], [], [], []
    for parsed in results:
        name = ACT[parsed.act].short
        entry = manifest.get(parsed.act)
        route = "Internet Archive copy" if entry and entry["fetched_from"] != entry["url"] else "India Code"
        files.append(
            f"| {name} | {route} | `{entry['sha256'][:16] if entry else '?'}` | {parsed.pages} "
            f"| {parsed.note or 'none'} |"
        )
        listed = {e.number: e.heading for e in parsed.arrangement}
        differ = [s for s in parsed.sections if not heading_agrees(listed[s.number], s.heading)]
        status = {"repealed": 0, "omitted": 0}
        for section in parsed.sections:
            if section.status in status:
                status[section.status] += 1
        lettered = sum(1 for section in parsed.sections if not section.number.isdigit())
        paragraphs = sum(len(section.paragraphs) for section in parsed.sections)
        sections.append(
            f"| {name} | {len(parsed.arrangement)} | {len(parsed.sections)} | {len(parsed.missing)} "
            f"| {len(parsed.gaps)} | {len(parsed.unused)} | {len(differ)} "
            f"| {status['repealed']} + {status['omitted']} | {lettered} | {paragraphs} |"
        )
        blocks = sum(1 for section in parsed.sections if section.state_amendments)
        groups = groups_that_differ(parsed)
        apart.append(
            f"| {name} | {len(parsed.footnotes)} | {blocks} | {len(parsed.inserted_by_states)} "
            f"| {len(group_starts(parsed.arrangement))} | {len(parsed.group_headings)} | {len(groups)} |"
        )
        breaks.append(f"| {name} | {share(*reversed(parsed.clause_lines))} | {share(*reversed(parsed.lower_lines))} |")
        found = []
        found += [f"* never found in the body: section {number}" for number in parsed.missing]
        found += [f"* missing from the arrangement's numbering: {number}" for number in parsed.gaps]
        found += [f"* left unused, page {line.page}: {line.text[:110]}" for line in parsed.unused]
        found += [
            f"* inserted by a state, cut out with its block, page {line.page}: {line.text[:90]}"
            for line in parsed.inserted_by_states
        ]
        found += [
            f"* heading differs, section {s.number}: listed \"{listed[s.number]}\", found \"{s.heading}\""
            for s in differ
        ]
        found += [f"* group heading {note}" for note in groups]
        if found:
            notes += [f"\n**{name}**\n", *found]
    commencement = []
    for parsed in results:
        first = next((s for s in parsed.sections if s.number == "1"), None)
        if first and ACT[parsed.act].replaced_by is None:
            for note in first.footnotes:
                commencement.append(f"* {ACT[parsed.act].short} section 1, footnote {note.marker}: {note.text}")
    found_all = all(not parsed.missing for parsed in results)
    no_gaps = all(not parsed.gaps for parsed in results)
    lines = [
        "# M1: the corpus",
        "",
        "Made by `python scripts/parse_corpus.py` from the files in `data/raw` (decisions 3, 4, 29 and 30).",
        f"Machine: {platform.system()} {platform.release()} {platform.machine()}; Python "
        f"{platform.python_version()}; pdfplumber {pdfplumber.__version__}.",
        "",
        "## The files",
        "",
        "| Act | Came from | SHA256 | Pages | Note in the file |",
        "|---|---|---|---:|---|",
        *files,
        "",
        "## The sections",
        "",
        "| Act | Listed | Found | Never found | Gaps in the numbering | Unused lines | Headings that differ "
        "| Repealed + omitted | Lettered | Paragraphs |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        *sections,
        "",
        "Listed: sections in the Act's arrangement of sections. Found: sections cut from the body, in the "
        "arrangement's order. Gaps in the numbering: whole numbers up to the last, and single letters up to "
        "the last for a number (171A to 171I), that the arrangement does not list. Unused lines: lines in the "
        "central text that look like a section start but were not used as one (a cross reference that breaks "
        "over a line, so that its section number starts the line). Headings that differ: the body's heading "
        "against the arrangement's, after case and punctuation; the body's is the one used. Lettered: "
        "sections such as 54A, and 171I, which India Code prints with a hyphen before the letter.",
        "",
        ("Every listed section was found in the body" if found_all else "Some listed sections were not found")
        + (", and no number is missing from the arrangements." if no_gaps else "; some numbers are missing."),
        "",
        "## Kept apart from the text",
        "",
        "| Act | Footnotes | State amendment blocks cut | State insertions | Groups listed "
        "| Group headings cut from the body | Groups that differ |",
        "|---|---:|---:|---:|---:|---:|---:|",
        *apart,
        "",
        "Footnotes: the amendment history below the rule at the foot of a page, kept with the section whose "
        "marker they carry. State amendment blocks: the state amendments India Code prints after a section, "
        "cut out of it and kept beside it, since Dhara answers on the central Acts (decision 2); state "
        "insertions are the section like lines inside them. Groups: the headings of groups of sections within "
        "a chapter (\"Of theft\", \"ADMISSIONS\"). The arrangement names the group of each section; the body's "
        "group headings are cut from the end of the section before them, and the two are compared.",
        "",
        "## Paragraph breaks",
        "",
        "| Act | Lines opening with a clause marker that start a paragraph "
        "| Lines opening in lower case that start a paragraph |",
        "|---|---:|---:|",
        *breaks,
        "",
        "Lines after a section's first. A line that opens with a clause marker (\"(a)\", \"(1)\", "
        "\"Explanation\", \"Provided\", \"Illustration\") should start a paragraph, unless it is a cross "
        "reference broken over a line (\"clause\", then \"(b) of section 3\"); a line that opens in lower case "
        "should almost never start one.",
        "",
        "## What the check found",
        *(notes or ["\nNothing to report."]),
        "",
        "## Commencement, as India Code's footnotes record it (decision 25)",
        "",
        *(commencement or ["None found."]),
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    raw = DATA / "raw"
    missing = [source.key for source in SOURCES if not (raw / f"{source.key}.pdf").exists()]
    if missing:
        print(f"missing in data/raw: {', '.join(missing)}; run scripts/get_data.py first", file=sys.stderr)
        return 1
    results = []
    for source in SOURCES:
        parsed = parse(source.act, raw / f"{source.key}.pdf")
        write_sections(parsed, DATA / "parsed")
        results.append(parsed)
        print(
            f"{source.key:5} {len(parsed.sections):4} of {len(parsed.arrangement):4} sections, "
            f"{len(parsed.missing)} never found, {len(parsed.gaps)} gaps, {len(parsed.unused)} unused lines"
        )
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(report(results), encoding="utf8")
    print(f"wrote {RESULTS.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
