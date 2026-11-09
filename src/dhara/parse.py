"""India Code PDFs into sections, with their part and chapter; footnotes kept apart (decision 4).

Each PDF opens with an arrangement of sections (the Act's contents), then the Act itself. The
arrangement is read first and is the authority on which sections exist and where each sits (part,
chapter). The body is then cut where those sections begin, in order, and only at lines that look like
a section start on the page: a bold number, or a number followed by a heading and a dash, or a repeal
note. Arrangement entries never found in the body, and section like lines that were not used, are
reported, which is the check decision 4 asks for.

Footnotes (amendment history) sit below a short rule at the foot of a page (a rectangle about two
inches wide and under a point high), and their markers are raised above the line in smaller type; both
are taken out of the text and kept with the sections they belong to. The rule, not the type size,
marks where footnotes begin: the body is 10 point in the CrPC and 11 point elsewhere, the IPC's
arrangement of sections is 9 point, and the Evidence Act's footnotes are 10 point.

Headings of groups of sections ("Of theft" in the BNS, "ADMISSIONS" in the Evidence Act, the lettered
groups of the CrPC and the BNSS) are set apart: centred on the page and inset from both margins. In the
arrangement they name the group each entry falls in; in the body they are cut from the end of the
section before them, so they never read as that section's text. The two are compared, as a check.
"""

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber

RAISED = 0.82  # in the body, characters smaller than this share of the page's usual size are raised markers
PARAGRAPH_GAP = 1.35  # a gap this many times the page's line spacing starts a new paragraph
CLAUSE_GAP = 1.35  # a line that opens with a clause marker starts one after a gap this many times its type size
INDENT = 8.0  # or when it starts this many points to the right of the line before
CENTRED_WITHIN = 20.0  # points between a line's middle and the page's middle, for the line to count as centred
INSET = 24.0  # points a centred heading keeps from the margins; a full line of text is centred too

# a section number; India Code prints a hyphen before the letter I (so that 171I is not read as 1711), dropped
NUMBERED = re.compile(r"^\[?(\d+(?:-?[A-Z]{1,3})?)\.\s*(.*)$")
# India Code's IPC sets section 17 with no full stop after its bold number, before “Government”
LOOSE = re.compile(r"^\[?(\d+(?:-?[A-Z]{1,3})?)\s+(?=[“\"‘A-Z])(.*)$")
# a lettered group heading, as the CrPC and BNSS print them: a capital letter, a full stop, a dash, the name
LETTERED = re.compile(r"^[A-H]\.\s*[—–-]+\s*\S")
STATE = re.compile(r"^STATE\s+AMENDMENTS?\b")
CHAPTER = re.compile(r"^\[?CHAPTER\s+([IVXL]+[A-Z]{0,2})\b[.\s]*[—–\-]*\s*(.*)$")
PART = re.compile(r"(?:^|\s)PART\s+([IVX]+)\b[.\s]*[—–\-]*\s*(.*)$")
SCHEDULE = re.compile(r"^\[?THE\s+(?:FIRST\s+|SECOND\s+|THIRD\s+)?SCHEDULE\b")
OBJECTS = re.compile(r"^STATEMENT\s+OF\s+OBJECTS\s+AND\s+REASONS\b")  # printed after the BNS's last section
ACT_NUMBER = re.compile(r"^\(?ACT\s+NO\.?\s*\d+\s+OF\s+\d{4}", re.I)
DASH = re.compile(r"[—–]{1,2}|-{2,}")
ENDED = re.compile(r"\.[\]\)”’\"]*$")  # a heading in the arrangement ends with a full stop
GONE = re.compile(r"\bRep\.|\[Repealed|Repealed\.|\[Omitted|Omitted\.|\bomitted by\b", re.I)
CLAUSE = re.compile(r"^(\(\w{1,6}\)|Explanation|Illustration|Provided|Exception|Ex\.|ILLUSTRATIONS?)")


@dataclass(frozen=True)
class Line:
    page: int
    top: float
    x0: float
    text: str
    size: float  # the commonest character size on the line
    bold: bool  # its first characters, after an opening bracket, are bold
    markers: tuple[str, ...] = ()  # footnote markers raised on this line
    x1: float = 0.0  # where the line ends
    width: float = 0.0  # the page's width; 0 when unknown


@dataclass(frozen=True)
class Footnote:
    page: int
    marker: str
    text: str


@dataclass(frozen=True)
class Entry:
    """One section as the arrangement of sections lists it."""

    number: str
    heading: str
    part: str | None
    chapter: str | None
    chapter_title: str | None
    group: str | None = None  # the heading of the group of sections within the chapter, if any


@dataclass
class Section:
    act: str
    number: str
    heading: str
    paragraphs: list[str]
    part: str | None
    chapter: str | None
    chapter_title: str | None
    pages: tuple[int, int]
    status: str  # "in force", "omitted" or "repealed"
    group: str | None = None
    footnotes: list[Footnote] = field(default_factory=list)
    state_amendments: list[str] = field(default_factory=list)  # printed after the section; not central law

    @property
    def text(self) -> str:
        return "\n".join(self.paragraphs)


@dataclass
class Parsed:
    act: str
    pages: int
    note: str | None  # the file's own "as on" or "last updated" note
    arrangement: list[Entry]
    sections: list[Section]
    missing: list[str]  # in the arrangement, not found in the body
    unused: list[Line]  # section like lines in the central text that were not used as a section start
    footnotes: list[Footnote]
    inserted_by_states: list[Line] = field(default_factory=list)  # section like lines in state amendments
    group_headings: list[tuple[str, str]] = field(default_factory=list)  # cut from the body: (next section, text)
    gaps: list[str] = field(default_factory=list)  # numbers missing from the arrangement's sequence
    clause_lines: tuple[int, int] = (0, 0)  # lines that open with a clause marker, and how many start a paragraph
    lower_lines: tuple[int, int] = (0, 0)  # lines that open in lower case, and how many start a paragraph


# reading the PDF


def _separator(page: Any) -> float | None:
    """Where the footnote rule sits on a page, if there is one."""
    for rect in page.rects:
        if rect["height"] < 1.0 and 130 <= rect["width"] <= 160 and rect["x0"] < 120:
            return float(rect["top"])
    return None


def _is_marker(obj: dict[str, Any], raised_below: float) -> bool:
    """A footnote marker: a small raised digit or star. Raised letters ("6th") stay in the text."""
    return obj.get("object_type") == "char" and obj["size"] < raised_below and obj["text"] in "0123456789*"


def _region_lines(region: Any, number: int, raised_below: float, width: float) -> list[Line]:
    raised = [c for c in region.chars if _is_marker(c, raised_below)]
    kept = region.filter(lambda o: not _is_marker(o, raised_below))
    lines = []
    for found in kept.extract_text_lines(return_chars=True):
        chars = [c for c in found["chars"] if c["text"].strip()]
        text = found["text"].strip()
        if not chars or not text:
            continue
        size = Counter(round(c["size"], 1) for c in chars).most_common(1)[0][0]
        lead = [c for c in chars if c["text"] not in "[("][:3]
        bold = bool(lead) and all("bold" in c["fontname"].lower() for c in lead)
        near = sorted(
            (c for c in raised if found["top"] - 4 <= c["top"] and c["bottom"] <= found["bottom"] + 1),
            key=lambda c: c["x0"],
        )
        lines.append(
            Line(number, found["top"], found["x0"], text, size, bold, _markers(near), found["x1"], width)
        )
    return lines


def _markers(chars: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    """Raised characters grouped into markers: digits that touch form one number."""
    groups: list[list[dict[str, Any]]] = []
    for c in chars:
        if groups and c["x0"] - groups[-1][-1]["x1"] < 1.5:
            groups[-1].append(c)
        else:
            groups.append([c])
    texts = ("".join(c["text"] for c in group) for group in groups)
    return tuple(t for t in texts if t.isdigit() or set(t) == {"*"})


def read_page(page: Any, number: int) -> tuple[list[Line], list[Line]]:
    """A page's body lines and its footnote lines, without the page number."""
    rule = _separator(page)
    body_region = page.crop((0, 0, page.width, rule)) if rule is not None else page
    sizes = Counter(round(c["size"], 1) for c in body_region.chars if c["text"].strip())
    usual = sizes.most_common(1)[0][0] if sizes else 11.0
    width = float(page.width)
    body = _region_lines(body_region, number, RAISED * usual, width)
    foot = _region_lines(page.crop((0, rule, page.width, page.height)), number, 0.0, width) if rule is not None else []

    def numbered_page(line: Line) -> bool:
        return bool(re.fullmatch(r"\d{1,4}", line.text)) and line.top > 0.85 * float(page.height)

    return [line for line in body if not numbered_page(line)], [line for line in foot if not numbered_page(line)]


def footnotes_of(lines: Iterable[Line]) -> list[Footnote]:
    notes: list[Footnote] = []
    for line in lines:
        match = re.match(r"^(\d+|\*+)\.?\s+(.*)$", line.text)
        if match:
            notes.append(Footnote(line.page, match[1], match[2]))
        elif notes:
            last = notes[-1]
            notes[-1] = Footnote(last.page, last.marker, f"{last.text} {line.text}")
    return notes


def read(path: Path) -> tuple[list[Line], list[Footnote], int]:
    """The body lines of every page, the footnotes, and the number of pages."""
    body: list[Line] = []
    notes: list[Footnote] = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            main, foot = read_page(page, number)
            body.extend(main)
            notes.extend(footnotes_of(foot))
        pages = len(pdf.pages)
    return body, notes, pages


# the arrangement of sections


def parse_arrangement(lines: Sequence[Line]) -> list[Entry]:
    entries: list[Entry] = []
    part = chapter = chapter_title = group = None
    title_of: str | None = None  # "part" or "chapter" while their title lines are being read
    titles: list[str] = []
    group_lines: list[str] = []  # the heading of a group, while it is being read
    heading: list[str] = []
    number: str | None = None
    margins = _margins(lines)

    def close_entry() -> None:
        nonlocal number, heading
        if number is not None:
            entries.append(Entry(number, " ".join(heading).strip(), part, chapter, chapter_title, group))
        number, heading = None, []

    def close_title() -> None:
        nonlocal title_of, titles, chapter_title
        if title_of == "chapter" and titles:
            chapter_title = " ".join(titles).strip(" .—–-")
        title_of, titles = None, []

    started = not any(line.text.strip() == "ARRANGEMENT OF SECTIONS" for line in lines)
    for line in lines:
        text = line.text.strip()
        if not started:  # the cover page, before the arrangement begins
            started = text == "ARRANGEMENT OF SECTIONS"
            continue
        if text == "SECTIONS" or not text.strip("_ "):
            continue
        if SCHEDULE.match(text) or ACT_NUMBER.match(text):
            break
        capitals = text.upper() == text
        if part_match := PART.search(text):
            close_entry()
            close_title()
            part, chapter, chapter_title, group, group_lines = f"PART {part_match[1]}", None, None, None, []
            title_of = "part"
            continue
        if chapter_match := CHAPTER.match(text):
            close_entry()
            close_title()
            chapter, chapter_title, group, group_lines = f"CHAPTER {chapter_match[1]}", None, None, []
            title_of, titles = "chapter", [chapter_match[2]] if chapter_match[2] else []
            continue
        if numbered := NUMBERED.match(text):
            close_entry()
            close_title()
            if group_lines:
                group, group_lines = _bare_group(_join(group_lines)), []
            number, heading = _number(numbered[1]), [numbered[2]]
            continue
        a_title_line = title_of is not None and capitals and not LETTERED.match(text)
        # a heading still open is continued on its next line, wherever that line happens to sit
        open_heading = number is not None and not ENDED.search(" ".join(heading).strip())
        set_apart = _set_apart(line, margins, both_sides=False) and not a_title_line and not open_heading
        if LETTERED.match(text) or (group_lines and capitals) or set_apart:
            close_entry()
            close_title()
            group_lines.append(text)
        elif title_of is not None:
            titles.append(text)
        elif number is not None and not capitals:  # a capitalised line is a title, not a heading
            heading.append(text)
    close_entry()
    return entries


def numbering_gaps(numbers: Sequence[str]) -> list[str]:
    """Numbers the arrangement should list but does not: every whole number up to the last, and for each
    number with lettered sections, every single letter up to its last (171A to 171I)."""
    whole = {int(match[1]) for number in numbers if (match := re.match(r"(\d+)", number))}
    gaps = [str(n) for n in range(1, max(whole) + 1) if n not in whole] if whole else []
    letters: dict[int, set[str]] = {}
    for number in numbers:
        if lettered := re.fullmatch(r"(\d+)([A-Z])", number):
            letters.setdefault(int(lettered[1]), set()).add(lettered[2])
    for base in sorted(letters):
        last = max(letters[base])
        gaps += [f"{base}{c}" for c in map(chr, range(ord("A"), ord(last) + 1)) if c not in letters[base]]
    return gaps


# the body


def _looks_like_start(lines: Sequence[Line], i: int) -> str | None:
    """The section number if line i looks like the start of a section, else None."""
    line = lines[i]
    match = NUMBERED.match(line.text)
    if not match:
        loose = LOOSE.match(line.text)
        return _number(loose[1]) if loose and line.bold else None
    if line.bold:
        return _number(match[1])
    window = [line.text]
    for other in lines[i + 1 : i + 3]:
        if other.page != line.page or NUMBERED.match(other.text) or CHAPTER.match(other.text):
            break
        window.append(other.text)
    joined = " ".join(window)[:400]
    if DASH.search(joined) or GONE.search(line.text[:160]):
        return _number(match[1])
    return None


def _spacing(lines: Sequence[Line]) -> dict[int, float]:
    """The line spacing within paragraphs on each page: the lower quartile of the gaps between its lines,
    taken over the whole page, since a short section has too few lines to tell."""
    tops: dict[int, list[float]] = {}
    for line in lines:
        tops.setdefault(line.page, []).append(line.top)
    spacing: dict[int, float] = {}
    for page, found in tops.items():
        found.sort()
        gaps = sorted(b - a for a, b in zip(found, found[1:], strict=False) if b > a)
        spacing[page] = gaps[len(gaps) // 4] if gaps else 12.5
    return spacing


def _breaks(lines: Sequence[Line], spacing: dict[int, float]) -> list[bool]:
    """Which lines start a paragraph: a gap wider than the page's line spacing allows; or, for a line that
    opens with a clause marker, a smaller gap or an indent; or a clause marker at the top of a page."""
    breaks: list[bool] = []
    previous: Line | None = None
    for line in lines:
        clause = bool(CLAUSE.match(line.text))
        if previous is None:
            new = True
        elif line.page != previous.page:
            new = clause
        else:
            gap = line.top - previous.top
            new = gap > PARAGRAPH_GAP * spacing.get(line.page, 12.5) or (
                clause and (gap > CLAUSE_GAP * line.size or line.x0 > previous.x0 + INDENT)
            )
        breaks.append(new)
        previous = line
    return breaks


def _paragraphs(lines: Sequence[Line], spacing: dict[int, float] | None = None) -> list[str]:
    """Lines joined into paragraphs."""
    paragraphs: list[list[str]] = []
    for line, new in zip(lines, _breaks(lines, spacing or _spacing(lines)), strict=True):
        if new or not paragraphs:
            paragraphs.append([line.text])
        else:
            paragraphs[-1].append(line.text)
    return [_join(parts) for parts in paragraphs]


def _join(parts: Sequence[str]) -> str:
    text = ""
    for part in parts:
        if text.endswith("-") and part[:1].islower():
            text += part
        else:
            text = f"{text} {part}" if text else part
    return re.sub(r"\s+", " ", text).strip()


def _number(printed: str) -> str:
    """A section number as Dhara keys it, without the hyphen India Code prints before the letter I."""
    return printed.replace("-", "")


def _margins(lines: Sequence[Line]) -> dict[int, tuple[float, float]]:
    """Where the text begins and ends on each page."""
    margins: dict[int, tuple[float, float]] = {}
    for line in lines:
        left, right = margins.get(line.page, (line.x0, line.x1))
        margins[line.page] = (min(left, line.x0), max(right, line.x1))
    return margins


def _set_apart(line: Line, margins: dict[int, tuple[float, float]], both_sides: bool = True) -> bool:
    """A heading set apart from the text: centred on the page, inset from the margins, and not a clause.
    In the arrangement, where every entry is a short line, the left margin is enough."""
    if line.width <= 0 or line.page not in margins or CLAUSE.match(line.text):
        return False
    left, right = margins[line.page]
    centred = abs((line.x0 + line.x1) / 2 - line.width / 2) <= CENTRED_WITHIN
    return centred and line.x0 >= left + INSET and (not both_sides or line.x1 <= right - INSET)


def _peel(lines: Sequence[Line], margins: dict[int, tuple[float, float]]) -> tuple[list[Line], list[Line]]:
    """A section's lines, and the headings at their end that belong to what follows: a chapter, its
    title, a group of sections."""
    end = len(lines)
    while end > 1:
        text = lines[end - 1].text
        if not (CHAPTER.match(text) or PART.match(text) or LETTERED.match(text) or _set_apart(lines[end - 1], margins)):
            break
        end -= 1
    for back in range(end - 1, max(end - 4, 0), -1):  # a chapter's title can be wider than a heading set apart
        if CHAPTER.match(lines[back].text) or PART.match(lines[back].text):
            if all(line.text.upper() == line.text for line in lines[back + 1 : end]):
                end = back
            break
    return list(lines[:end]), list(lines[end:])


def _group_of(headings: Sequence[Line]) -> str | None:
    """The heading of a group among the headings cut from a section's end, without the chapter's own."""
    group: list[str] = []
    after_chapter = False
    for line in headings:
        if CHAPTER.match(line.text) or PART.match(line.text):
            after_chapter, group = True, []
        elif after_chapter and line.text.upper() == line.text and not LETTERED.match(line.text):
            continue  # the chapter's title
        else:
            after_chapter = False
            group.append(line.text)
    return _bare_group(_join(group)) or None


def _bare_group(text: str) -> str:
    """A group's heading without the brackets that mark it as inserted by an amendment."""
    return text.strip().removeprefix("[").removesuffix("]").strip()


def split_heading(first: str) -> tuple[str, str, str]:
    """A section's first paragraph as its number, heading and the rest of the text."""
    match = NUMBERED.match(first) or LOOSE.match(first)
    if not match:
        raise ValueError(first[:80])
    after = match[2].lstrip("—–- ")  # India Code sets BNS 255 with a long dash between its number and its heading
    dash = DASH.search(after[:400])
    if dash:
        heading, rest = after[: dash.start()], after[dash.end() :]
    else:
        stop = after.find(". ")
        heading, rest = (after, "") if stop < 0 else (after[: stop + 1], after[stop + 2 :])
    return _number(match[1]), heading.strip(" .]").lstrip("[").strip(), rest.strip()


def status_of(listed: str, first: str) -> str:
    """Repealed or omitted, as the arrangement lists the section or its own first lines say."""
    probe = f"{listed} {first[:160]}"
    if re.search(r"\bOmitted\b", probe, re.I):
        return "omitted"
    if re.search(r"\bRep\.|Repealed", probe):
        return "repealed"
    return "in force"


def parse_lines(act: str, lines: Sequence[Line], notes: Sequence[Footnote], pages: int) -> Parsed:
    starts = [(i, _looks_like_start(lines, i)) for i in range(len(lines))]
    first = next((i for i, number in starts if number == "1"), None)
    if first is None:
        raise ValueError(f"{act}: no line starts section 1")
    arrangement = parse_arrangement(lines[:first])
    where = {entry.number: entry for entry in arrangement}
    body = list(lines[first:])
    for i, line in enumerate(body):
        if SCHEDULE.match(line.text) or OBJECTS.match(line.text):
            body = body[:i]
            break
    margins, spacing = _margins(body), _spacing(body)
    found: list[tuple[int, Entry]] = []
    unused: list[Line] = []
    position = 0  # where the next section may be found in the arrangement
    for i in range(len(body)):
        number = _looks_like_start(body, i)
        if number is None:
            continue
        later = [n for n, entry in enumerate(arrangement[position:], start=position) if entry.number == number]
        if later and later[0] - position <= 3:
            found.append((i, where[number]))
            position = later[0] + 1
        else:
            unused.append(body[i])
    sections = []
    group_headings: list[tuple[str, str]] = []
    state_lines: set[tuple[int, float]] = set()
    clause_lines = [0, 0]
    lower_lines = [0, 0]
    for k, (i, entry) in enumerate(found):
        end = found[k + 1][0] if k + 1 < len(found) else len(body)
        own = list(body[i:end])
        if k + 1 < len(found):
            own, headings = _peel(own, margins)
            group = _group_of(headings)
            if group:
                group_headings.append((found[k + 1][1].number, group))
        own = _without_headings(own)
        state = next((n for n, line in enumerate(own) if STATE.match(line.text)), len(own))
        own, amendments = own[:state], own[state + 1 :]
        state_lines.update((line.page, line.top) for line in amendments)
        for line, new in list(zip(own, _breaks(own, spacing), strict=True))[1:]:
            if CLAUSE.match(line.text):
                clause_lines[0] += 1
                clause_lines[1] += new
            elif line.text[:1].islower():
                lower_lines[0] += 1
                lower_lines[1] += new
        paragraphs = _paragraphs(own, spacing)
        first_paragraph = paragraphs[0]
        number, heading, rest = split_heading(first_paragraph)
        paragraphs[0] = rest
        pages_spanned = {line.page for line in own}
        markers = {(line.page, m) for line in own for m in line.markers}
        mine = [note for note in notes if (note.page, note.marker) in markers]
        sections.append(
            Section(
                act=act,
                number=entry.number,
                heading=heading,
                paragraphs=[p for p in paragraphs if p],
                part=entry.part,
                chapter=entry.chapter,
                chapter_title=entry.chapter_title,
                pages=(min(pages_spanned), max(pages_spanned)),
                status=status_of(entry.heading, first_paragraph),
                group=entry.group,
                footnotes=mine,
                state_amendments=_paragraphs(amendments, spacing) if amendments else [],
            )
        )
    seen = {section.number for section in sections}
    missing = [entry.number for entry in arrangement if entry.number not in seen]
    by_states = [line for line in unused if (line.page, line.top) in state_lines]
    unused = [line for line in unused if (line.page, line.top) not in state_lines]
    return Parsed(
        act,
        pages,
        note_of(lines[:first]),
        arrangement,
        sections,
        missing,
        unused,
        list(notes),
        by_states,
        group_headings,
        numbering_gaps([entry.number for entry in arrangement]),
        (clause_lines[0], clause_lines[1]),
        (lower_lines[0], lower_lines[1]),
    )


def group_starts(arrangement: Sequence[Entry]) -> dict[str, str]:
    """The groups the arrangement lists, keyed by the section each begins with."""
    starts: dict[str, str] = {}
    previous: str | None = None
    for entry in arrangement:
        if entry.group and entry.group != previous:
            starts[entry.number] = entry.group
        previous = entry.group
    return starts


def groups_that_differ(parsed: Parsed) -> list[str]:
    """Where the arrangement's groups and the group headings cut from the body disagree."""

    def bare(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", text.lower())

    listed = group_starts(parsed.arrangement)
    found = dict(parsed.group_headings)
    notes = []
    for number in sorted(set(listed) | set(found), key=lambda n: [e.number for e in parsed.arrangement].index(n)):
        if number not in found:
            notes.append(f"listed before section {number}, not found in the body: \"{listed[number]}\"")
        elif number not in listed:
            notes.append(f"found in the body before section {number}, not listed: \"{found[number]}\"")
        elif bare(listed[number]) != bare(found[number]):
            notes.append(f"before section {number}: listed \"{listed[number]}\", found \"{found[number]}\"")
    return notes


def note_of(lines: Sequence[Line]) -> str | None:
    """The note that dates the text, from the pages before the Act begins."""
    for line in lines[:60]:
        found = re.search(r"\[?As on the [^\]]+\]?|Last updated:?[-\s]*[\d.-]+", line.text)
        if found:
            return found[0].strip("[]").rstrip(".")
    return None


def heading_agrees(listed: str, found: str) -> bool:
    """Whether a section's heading in the body matches the arrangement: the shorter is a prefix of the
    longer once case, brackets and punctuation are set aside (the Evidence Act lists marginal notes
    such as "Extent." after the heading)."""

    def bare(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", text.lower())

    if re.fullmatch(r"\[?(Repealed|Omitted)\.?\]?\.?", listed.strip()):
        return True  # the arrangement lists only the status; the body keeps the old heading
    a, b = bare(listed), bare(found)
    return bool(a) and bool(b) and (a.startswith(b) or b.startswith(a))


def _without_headings(lines: Sequence[Line]) -> list[Line]:
    """The lines without part and chapter headings and their titles, which sit between sections."""
    kept: list[Line] = []
    skipping = False
    for line in lines:
        if CHAPTER.match(line.text) or PART.match(line.text):
            skipping = True
            continue
        if skipping and line.text.upper() == line.text:
            continue
        skipping = False
        kept.append(line)
    return kept


def parse(act: str, path: Path) -> Parsed:
    lines, notes, pages = read(path)
    return parse_lines(act, lines, notes, pages)
