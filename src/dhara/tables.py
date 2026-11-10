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
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
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


# The old to new correspondence (decisions 5 and 24), from CAPT Bhopal's three tables. Each is a ruled
# Word table of four columns; the order of the columns differs between the tables.
COLUMNS = {
    "bns_ipc_table": ("new", "subject", "old", "summary"),
    "bnss_crpc_table": ("new", "subject", "old", "summary"),
    "bsa_iea_table": ("new", "old", "subject", "summary"),
}
CHANGES = ("unchanged", "modified", "new", "heading")


@dataclass(frozen=True)
class Correspondence:
    table: str  # the source's key, as in corpus.TABLES
    new: str  # the new Act's provision as the table prints it: "2(8)", "356 (1)"
    new_section: str  # the section it is in: "2", "356"
    old: str  # the old Act's provisions as the table prints them: "29 and 29A", "New", "3, para 1"
    old_sections: tuple[str, ...]  # the old sections they are in: ("29", "29A"); none for a new provision
    subject: str
    summary: str  # CAPT's comparison, as printed
    explanation: str  # the same, with "Ditto." replaced by the comparison it repeats
    change: str  # unchanged, modified, new, or heading (a row that sums up the rows of its subsections)
    shape: str  # one to one, merged, split, or merged and split; at the level of whole sections
    page: int


def _inside(inner: tuple[float, ...], outer: tuple[float, ...]) -> bool:
    """Whether one box lies within another, to a point."""
    left, top, right, bottom = inner
    return left >= outer[0] - 1 and top >= outer[1] - 1 and right <= outer[2] + 1 and bottom <= outer[3] + 1


def _one_line(text: str) -> str:
    return join_lines([line.strip() for line in text.splitlines() if line.strip()])


def _cells(path: Path, columns: Sequence[str]) -> list[tuple[int, dict[str, str]]]:
    """Every row of a CAPT table as {column: text}, each cell placed by where it begins on the page."""
    Box = tuple[float, float, float, float]
    found: list[tuple[int, Any, list[tuple[Box, str]]]] = []
    boxes: dict[int, list[Box]] = {}  # every cell on a page, to tell a missing cell from one that spans rows
    spans: Counter[tuple[tuple[int, int], ...]] = Counter()
    rows = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            # A row carried over from the page before has no rule above it, so the table finder would
            # leave it out; a line where the column rules begin and one where they end close the table.
            verticals = [r for r in page.rects if r["width"] < 2 and r["height"] > 2]
            closing = [min(r["top"] for r in verticals), max(r["bottom"] for r in verticals)] if verticals else []
            tables = page.find_tables(table_settings={"explicit_horizontal_lines": closing})
            for table in tables:
                if any(other is not table and _inside(table.bbox, other.bbox) for other in tables):
                    continue  # a box drawn inside a cell; the cell's own text already holds its words
                for row, texts in zip(table.rows, table.extract(), strict=True):
                    cells = [(cell, text or "") for cell, text in zip(row.cells, texts, strict=True) if cell]
                    found.append((number, page, cells))
                    boxes.setdefault(number, []).extend(box for box, _ in cells)
                    if len(cells) == len(columns):
                        spans[tuple((round(box[0]), round(box[2])) for box, _ in cells)] += 1
        edges = spans.most_common(1)[0][0]  # each column's left and right edge, from the commonest full row

        def column_of(box: Box) -> int:
            return max((i for i, (left, _) in enumerate(edges) if left <= box[0] + 2), default=0)

        for number, page, cells in found:
            placed = {name: "" for name in columns}
            seen = {column_of(box) for box, _ in cells}
            for box, text in cells:
                name = columns[column_of(box)]
                placed[name] = f"{placed[name]} {_one_line(text)}".strip()
            if not cells:
                continue
            # A cell the finder could not close, its rule missing: read the words inside it, unless a
            # cell above or below spans this row in that column and so already holds them.
            top, bottom = min(box[1] for box, _ in cells), max(box[3] for box, _ in cells)
            for index, (left, right) in enumerate(edges):
                spanned = any(
                    column_of(box) == index and box[1] < bottom - 2 and box[3] > top + 2 for box in boxes[number]
                )
                if index not in seen and not spanned:
                    placed[columns[index]] = _one_line(page.crop((left, top, right, bottom)).extract_text() or "")
            rows.append((number, placed))
    return rows


def _provision(reference: str) -> str | None:
    """The section a provision is in: "2(1)(w )" is in 2, "356 (1)" in 356; a hyphen before a letter is
    dropped, as in parse.py."""
    found = re.match(r"\s*(\d+)(?:-?([A-Z]{1,3}))?(?![a-z])", reference)
    return f"{found[1]}{found[2] or ''}" if found else None


def old_sections(reference: str) -> tuple[str, ...]:
    """The old sections a reference names: "29 and 29A", "54 & 55", "230 to 232, 246 to 249, 255",
    "233 / 234", "3, para 1" (section 3), "IEA 3 Interpretation clause"; none for "New", or for a lone dash."""
    text = re.sub(r"\b(?:IPC|CrPC|IEA)\b", "", reference)
    text = re.sub(r",?\s*para\s*\d+", "", text)
    if re.match(r"\s*(?:new\b|-\s*$)", text, re.IGNORECASE) or not text.strip():
        return ()
    names: list[str] = []
    for part in re.split(r",|&|/|\band\b", text):
        ends = [_provision(end) for end in re.split(r"\bto\b", part)]
        if len(ends) == 2 and ends[0] and ends[1] and ends[0].isdigit() and ends[1].isdigit():
            names += [str(n) for n in range(int(ends[0]), int(ends[1]) + 1)]
        elif len(ends) == 2 and ends[0] and ends[1] and ends[0][:-1] == ends[1][:-1]:  # 354A to 354D
            names += [f"{ends[0][:-1]}{chr(c)}" for c in range(ord(ends[0][-1]), ord(ends[1][-1]) + 1)]
        else:
            names += [end for end in ends if end]
    return tuple(dict.fromkeys(names))


# What a comparison may say and still mean the text is unchanged: no change; the note, made once, that
# "Code" becomes "Sanhita" throughout; the old section kept whole as a subsection or proviso of the new
# one, its heading dropped. Anything else it says describes a change. The patterns match the words run
# together, because the tables sometimes break a word with a space ("sans h eading").
NOTHING_ELSE = (
    re.compile(r"codeisreplacedwithsanhita.*hereinafter"),
    re.compile(r"no(?:other)?changes?(?:weremade)?|withoutanychange|withoutchangingaword"),
    re.compile(r"except(?:that)?"),
    re.compile(
        r"(?:the)?(?:ipc|crpc|iea)?section(?:\d+[a-z]*)?(?:of)?(?:ipc|crpc|iea)?is(?:included|added|presented)"
        r"(?:in(?:the)?(?:bns|bnss|bsa))?as(?:a)?(?:subsection|proviso)(?:\d+)?(?:(?:in|of)(?:the)?(?:\d+)?(?:bns|bnss|bsa))?"
    ),
    re.compile(r"sans(?:its|separate)?headings?"),
    re.compile(r"(?:the)?headingisdropped(?:as)?"),
)


def change_of(old: tuple[str, ...], reference: str, explanation: str) -> str:
    """What changed, from the table's own words: unchanged, modified or new; or heading, for a row
    that sums up the rows of its subsections and names no old section itself."""
    if not old:
        return "new" if re.match(r"\s*(?:new\b|-)", reference, re.IGNORECASE) else "heading"
    rest = re.sub(r"[^a-z0-9]", "", explanation.lower())
    for pattern in NOTHING_ELSE:
        rest = pattern.sub("", rest)
    return "modified" if rest else "unchanged"


def _section_in(reference: str) -> str | None:
    """The section a new provision is in, wherever the reference names it: "2(8)" is in 2, "First
    proviso to section 22" in 22."""
    found = re.search(r"(\d+)(?:-?([A-Z]{1,3}))?(?![a-z0-9])", reference)
    return f"{found[1]}{found[2] or ''}" if found else None


def correspondence(path: Path, table: str) -> list[Correspondence]:
    """The rows of one CAPT table, a row broken over two pages joined again, typed by their change.
    Rows above the first that names a section are the table's header; any other row whose new column
    names no section is kept, with no section, so the check can list it."""
    columns = COLUMNS[table]
    merged: list[tuple[int, dict[str, str]]] = []
    for number, texts in _cells(path, columns):
        if texts["new"] and (merged or _section_in(texts["new"])):
            merged.append((number, dict(texts)))
        elif merged and not texts["new"]:  # the rest of the row above, carried over to this page
            for name, text in texts.items():
                if text:
                    merged[-1][1][name] = f"{merged[-1][1][name]} {text}".strip()
    rows: list[Correspondence] = []
    explanation = ""
    for number, texts in merged:
        ditto = re.sub(r"[^a-z]", "", texts["summary"].lower()) == "ditto"
        explanation = explanation if ditto and rows else texts["summary"]
        old = old_sections(texts["old"])
        new_section = _section_in(texts["new"]) or ""
        change = change_of(old, texts["old"], explanation)
        if change == "heading" and not any(
            _section_in(r[1]["new"]) == new_section and r[1]["new"] != texts["new"] for r in merged
        ):
            change = "modified"  # an empty old column with no subsections below it
        rows.append(
            Correspondence(table, texts["new"], new_section, texts["old"], old, texts["subject"],
                           texts["summary"], explanation, change, "", number)
        )
    return _shaped(rows)


def _shaped(rows: Sequence[Correspondence]) -> list[Correspondence]:
    """Each row's shape, at the level of whole sections: merged when its new section takes in several
    old sections, split when one of its old sections went to several new sections."""
    feeds: dict[str, set[str]] = {}
    goes: dict[str, set[str]] = {}
    for row in rows:
        for old in row.old_sections:
            feeds.setdefault(row.new_section, set()).add(old)
            goes.setdefault(old, set()).add(row.new_section)
    shaped = []
    for row in rows:
        merged = len(feeds.get(row.new_section, ())) > 1 and bool(row.old_sections)
        split = any(len(goes[old]) > 1 for old in row.old_sections)
        shape = {(False, False): "one to one", (True, False): "merged", (False, True): "split"}.get(
            (merged, split), "merged and split"
        )
        shaped.append(Correspondence(**{**asdict(row), "shape": shape if row.old_sections else ""}))
    return shaped


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def words_kept(path: Path, rows: Sequence[Correspondence]) -> tuple[int, Counter[str], Counter[str]]:
    """A check that reading a table lost nothing and repeated nothing: the number of words inside its
    rules, the words there that no row holds, and the words rows hold more often than the page does.
    The header's words, above the first row, are expected among the missing."""
    printed: Counter[str] = Counter()
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            verticals = [r for r in page.rects if r["width"] < 2 and r["height"] > 2]
            if verticals:
                box = (
                    min(r["x0"] for r in verticals),
                    min(r["top"] for r in verticals),
                    max(r["x1"] for r in verticals),
                    max(r["bottom"] for r in verticals),
                )
                printed.update(token for word in page.crop(box).extract_words() for token in _tokens(word["text"]))
    texts = (text for row in rows for text in (row.new, row.old, row.subject, row.summary))
    held = Counter(token for text in texts for token in _tokens(text))
    return sum(printed.values()), printed - held, held - printed
