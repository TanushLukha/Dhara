"""The BNSS First Schedule as rows: for each offence, its punishment, whether it is cognizable and
bailable, and which court tries it (decision 5).

The schedule is a ruled table in the BNSS file. Part I lists the offences under the BNS in six
columns (section, offence, punishment, cognizable or not, bailable or not, court); Part II classifies
offences under other laws in four. Each page's column edges are read from the short rules drawn
across the top of its table, and every character is placed in the column its middle falls in, so a
word can never run from one column into the next. A row starts where the offence column and at least
two of the others begin a new entry in capitals at the same height; a section's number may sit one
line below the first line of its row. A section whose offence is set out as a lead in ("in cases not
otherwise provided for:") followed by clauses (a), (b) gives one row per clause, each with the lead in.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber

from dhara.parse import join_lines

ROW_GAP = 15.0  # points: a section number this close below its row's first line belongs to that row
WORD_GAP = 0.5  # points: characters closer than this belong to one word (India Code letter spaces some cells)
SAME_LINE = 2.5  # points: words whose tops differ by less than this sit on one line


@dataclass(frozen=True)
class TableLine:
    page: int
    top: float
    cells: tuple[str, ...]  # one text per column, empty where the column has nothing on this line


@dataclass(frozen=True)
class ScheduleRow:
    part: str  # "I", offences under the BNS; "II", offences under other laws
    section: str | None  # as the schedule prints it: "49", "58(a)", "356(3)"; None in Part II
    offence: str
    punishment: str | None  # None in Part II, whose offence column states the punishment
    cognizable: str
    bailable: str
    court: str
    page: int
    lead_in: str | None = None  # the words that open the offence before its clauses, when the schedule has them


@dataclass
class _Building:
    page: int
    top: float
    number: str | None
    columns: list[list[str]] = field(default_factory=list)


HEADER_BAND = 20.0  # points: the rules that bound the header sit this close to its row of column numbers


def _header(page: Any) -> tuple[float, int] | None:
    """The height of the row that numbers the table's columns (1, 2, 3 ...), and how many there are."""
    rows: list[tuple[float, list[tuple[float, str]]]] = []
    for word in sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"])):
        if rows and abs(word["top"] - rows[-1][0]) < SAME_LINE:
            rows[-1][1].append((word["x0"], word["text"]))
        else:
            rows.append((word["top"], [(word["x0"], word["text"])]))
    for top, words in rows:
        texts = [text for _, text in sorted(words)]
        if len(texts) >= 4 and texts == [str(n) for n in range(1, len(texts) + 1)]:
            return top, len(texts)
    return None


def _column_edges(rules: Sequence[dict[str, Any]]) -> list[float]:
    """Where the columns begin and end, from the rules drawn across the header, cell by cell."""
    xs = sorted({round(r["x0"], 1) for r in rules} | {round(r["x1"], 1) for r in rules})
    edges: list[float] = []
    for x in xs:
        if not edges or x - edges[-1] >= 1.5:
            edges.append(x)
    return edges


def _table_lines(page: Any, number: int) -> list[TableLine]:
    """The lines of a schedule page's table: below its row of column numbers, above its closing rule
    when the page has one (a table that runs on to the next page has none), without the page number."""
    header = _header(page)
    if header is None:
        return []
    header_top, columns = header
    rules = [r for r in page.rects if r["height"] < 1]
    edges = _column_edges([r for r in rules if abs(r["top"] - header_top) <= HEADER_BAND])
    if len(edges) != columns + 1:
        raise ValueError(f"page {number}: {columns} numbered columns, but the rules give edges {edges}")
    closing = [r["top"] for r in rules if r["top"] > header_top + HEADER_BAND]
    bottom = max(closing) if closing else float(page.height)
    words: list[tuple[float, float, int, str]] = []
    for column in range(columns):
        left, right = edges[column], edges[column + 1]

        def inside(obj: dict[str, Any], left: float = left, right: float = right) -> bool:
            middle = (obj["x0"] + obj["x1"]) / 2
            return obj.get("object_type") == "char" and bool(obj["text"].strip()) and left <= middle < right

        for word in page.filter(inside).extract_words(x_tolerance=WORD_GAP):
            if header_top + SAME_LINE < word["top"] < bottom - 1:
                words.append((word["top"], word["x0"], column, word["text"]))
    words.sort()
    grouped: list[tuple[float, list[tuple[float, float, int, str]]]] = []
    for word in words:
        if grouped and abs(word[0] - grouped[-1][0]) < SAME_LINE:
            grouped[-1][1].append(word)
        else:
            grouped.append((word[0], [word]))
    lines = []
    for top, found in grouped:
        cells: list[list[str]] = [[] for _ in range(columns)]
        for _, _, column, text in sorted(found, key=lambda w: w[1]):
            cells[column].append(text)
        texts = tuple(" ".join(cell) for cell in cells)
        if top > 0.85 * float(page.height) and "".join(texts).isdigit():
            continue  # the page number
        lines.append(TableLine(number, top, texts))
    return lines


def _capital(text: str) -> bool:
    return text[:1].isupper()


def _opens(text: str) -> bool:
    """An offence entry opens in capitals, or with a clause such as "(a)"."""
    return _capital(text) or bool(re.match(r"\(\w{1,4}\)", text))


def assemble(lines: Iterable[TableLine], part: str) -> list[ScheduleRow]:
    """Rows from a part's table lines, which may run over several pages."""
    built: list[_Building] = []
    for line in lines:
        if part == "I":
            number, offence, values = line.cells[0], line.cells[1], line.cells[2:]
        else:
            number, offence, values = "", line.cells[0], line.cells[1:]
        starts = _opens(offence) and sum(_capital(value) for value in values) >= 2
        current = built[-1] if built else None
        if number.startswith("(") and not starts and current is not None and current.number:
            current.number += number  # "61(2)", then "(a)": the reference wraps in its narrow column
            number = ""
        late_number = (
            bool(number)
            and not starts
            and current is not None
            and current.number is None
            and current.page == line.page
            and line.top - current.top <= ROW_GAP
        )
        if current is None or ((starts or bool(number)) and not late_number):
            current = _Building(line.page, line.top, number or None, [[] for _ in line.cells])
            built.append(current)
        elif late_number:
            current.number = number
        for column, text in enumerate(line.cells):
            if text and not (column == 0 and part == "I"):
                current.columns[column].append(text)
    return _rows(built, part)


def _rows(built: Sequence[_Building], part: str) -> list[ScheduleRow]:
    rows: list[ScheduleRow] = []
    section: str | None = None
    lead_in = ""
    for building in built:
        cells = [join_lines(column) for column in building.columns]
        if part == "II":
            rows.append(ScheduleRow("II", None, cells[0], None, cells[1], cells[2], cells[3], building.page))
            continue
        if building.number:
            section, lead_in = building.number, ""
        if not any(cells[2:]):  # a lead in: its clauses follow as rows of their own
            lead_in = cells[1]
            continue
        offence = f"{lead_in} {cells[1]}".strip() if lead_in else cells[1]
        row = ScheduleRow("I", section, offence, cells[2], cells[3], cells[4], cells[5], building.page, lead_in or None)
        rows.append(row)
    return rows


def first_schedule(path: Path) -> list[ScheduleRow]:
    """The rows of the First Schedule in a BNSS file: Part I, then Part II."""
    parts: dict[str, list[TableLine]] = {"I": [], "II": []}
    with pdfplumber.open(path) as pdf:
        started, part = False, "I"
        for number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if not started:
                started = "THE FIRST SCHEDULE" in text and "CLASSIFICATION OF OFFENCES" in text
                if not started:
                    continue
            elif "THE SECOND SCHEDULE" in text:
                break
            if "OFFENCES AGAINST OTHER LAWS" in text:
                part = "II"
            parts[part].extend(_table_lines(page, number))
    return assemble(parts["I"], "I") + assemble(parts["II"], "II")


def kind(text: str, word: str) -> str:
    """Cognizable or bailable, as one word: the class, "depends" (according as the offence abetted),
    "conditional" (cognizable only on a complaint, or if a relative informs the police), or "other"."""
    words = " ".join(re.findall(r"[a-z]+", text.lower()))
    if words.startswith("according as"):
        return "depends"
    if words == f"non {word}":
        return f"non-{word}"
    if words == word:
        return word
    if re.match(rf"{word} (if|only|when|where|on)\b", words):  # "Cognizable (only on the complaint ...)"
        return "conditional"
    return "other"


def court_kind(text: str) -> str:
    """The court that tries the offence, as one of four values, or "depends" or "other"."""
    words = " ".join(re.findall(r"[a-z]+", text.lower()))
    if "by which" in words or "in which" in words:
        return "depends"
    if "session" in words:
        return "Court of Session"
    if "first" in words and "class" in words:
        return "Magistrate of the first class"
    if "any magistrate" in words:
        return "Any Magistrate"
    return "other"


def base_section(reference: str) -> str | None:
    """The section a schedule reference names: 58(a) is section 58, 356(3) is section 356."""
    found = re.match(r"(\d+[A-Z]{0,3})", reference)
    return found[1] if found else None


NUMBER_WORDS = {
    1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
    10: "ten", 11: "eleven", 12: "twelve", 14: "fourteen", 20: "twenty",
}


def terms(punishment: str) -> list[str]:
    """The terms a punishment states, as the Acts write them: "seven years", "six months", "life", "death"."""
    found = []
    for amount, unit in re.findall(r"\b(\d{1,2})\s+(year|years|month|months)\b", punishment):
        word = NUMBER_WORDS.get(int(amount))
        if word:
            found.append(f"{word} {unit}")
    lowered = punishment.lower()
    if "for life" in lowered:
        found.append("life")
    if lowered.startswith("death"):
        found.append("death")
    return found
