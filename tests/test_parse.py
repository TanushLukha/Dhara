import pytest

from dhara.parse import (
    Entry,
    Footnote,
    Line,
    _breaks,
    _join,
    footnotes_of,
    groups_that_differ,
    heading_agrees,
    note_of,
    numbering_gaps,
    parse_arrangement,
    parse_lines,
    split_heading,
    status_of,
)

WIDTH = 595.0  # an A4 page, in points


def line(
    text: str, page: int = 1, top: float = 0.0, x0: float = 75.0, bold: bool = False, markers: tuple[str, ...] = ()
) -> Line:
    return Line(page, top, x0, text, 11.0, bold, markers)


def placed(text: str, x0: float, x1: float, top: float = 0.0, page: int = 1, bold: bool = False) -> Line:
    """A line with its full position on an A4 page, so that whether it is centred can be told."""
    return Line(page, top, x0, text, 11.0, bold, (), x1, WIDTH)


def centred(text: str, top: float = 0.0, page: int = 1, half: float = 60.0) -> Line:
    return placed(text, WIDTH / 2 - half, WIDTH / 2 + half, top, page)


def test_the_arrangement_gives_parts_chapters_and_headings() -> None:
    lines = [
        line("The Example Act, 2099"),  # the cover, before the arrangement begins
        line("(ACT NO. 1 OF 2099)"),
        line("ARRANGEMENT OF SECTIONS"),
        line("PART I"),
        line("RELEVANCY OF FACTS"),
        line("CHAPTER I.––PRELIMINARY"),
        line("SECTIONS"),
        line("1. Short title."),
        line("Extent."),
        line("2. [Repealed.]"),
        line("CHAPTER II"),
        line("OF THE RELEVANCY OF FACTS"),
        line("3. Facts relevant when right or custom is in"),
        line("question."),
        line("THE EXAMPLE ACT, 2099"),
        line("ACT NO. 1 OF 2099"),
        line("4. not an entry"),
    ]
    entries = parse_arrangement(lines)
    assert [entry.number for entry in entries] == ["1", "2", "3"]
    assert entries[0] == Entry("1", "Short title. Extent.", "PART I", "CHAPTER I", "PRELIMINARY")
    assert entries[1].heading == "[Repealed.]"
    assert entries[2] == Entry(
        "3", "Facts relevant when right or custom is in question.", "PART I", "CHAPTER II", "OF THE RELEVANCY OF FACTS"
    )


@pytest.mark.parametrize(
    ("first", "expected"),
    [
        (
            "42. When such right extends to causing any harm other than death.—If the offence, the",
            ("42", "When such right extends to causing any harm other than death", "If the offence, the"),
        ),
        (
            "65B. Admissibility of electronic records. –– (1) Notwithstanding anything",
            ("65B", "Admissibility of electronic records", "(1) Notwithstanding anything"),
        ),
        (
            "[17 “Government”.—The word “Government” denotes",
            ("17", "“Government”", "The word “Government” denotes"),
        ),
        (
            "2. [Repeal of enactments.].––Rep. by the Repealing Act, 1938",
            ("2", "Repeal of enactments", "Rep. by the Repealing Act, 1938"),
        ),
        (
            "255.—Public servant disobeying direction of law.—Whoever, being a public servant",
            ("255", "Public servant disobeying direction of law", "Whoever, being a public servant"),
        ),
    ],
)
def test_headings_are_split_from_the_text(first: str, expected: tuple[str, str, str]) -> None:
    assert split_heading(first) == expected


def test_a_section_is_repealed_or_omitted_as_listed_or_as_it_says() -> None:
    assert status_of("[Repealed.].", "15. [Definition of “British India”.] Rep. by the A. O. 1937.") == "repealed"
    assert status_of("Definition of “Queen”.", "13. [Definition of “Queen”.] Omitted by the A. O. 1950.") == "omitted"
    assert status_of("Punishments.", "53. Punishments.—The punishments to which offenders are liable") == "in force"


def test_headings_agree_when_one_starts_the_other() -> None:
    assert heading_agrees("Short title. Extent. Commencement of Act.", "Short title")
    assert heading_agrees("“Government”.", "“Government”")
    assert heading_agrees("[Repealed.].", "Definition of “British India”.] Rep")
    assert not heading_agrees("“Moveable property”.", "“Movable property”")


def test_footnotes_are_joined_across_lines() -> None:
    lines = [
        line("1. Subs. by Act 3 of 1951, s. 3,", page=5, top=700),
        line("for “Part B States”.", page=5, top=710),
        line("2. Ins. by Act 4 of 2003.", page=5, top=720),
    ]
    assert footnotes_of(lines) == [
        Footnote(5, "1", "Subs. by Act 3 of 1951, s. 3, for “Part B States”."),
        Footnote(5, "2", "Ins. by Act 4 of 2003."),
    ]


def test_the_note_that_dates_the_text_is_found() -> None:
    assert note_of([line("The Bharatiya Nyaya Sanhita, 2023"), line("[As on the 6th October, 2025]")]) == (
        "As on the 6th October, 2025"
    )
    evidence_act = [line("THE INDIAN EVIDENCE ACT, 1872"), line("Last updated:-13-3-2020")]
    assert note_of(evidence_act) == "Last updated:-13-3-2020"
    assert note_of([line("THE INDIAN PENAL CODE")]) is None


def test_lines_broken_at_a_hyphen_are_joined_without_a_space() -> None:
    assert _join(["house-", "trespass is an offence"]) == "house-trespass is an offence"
    assert _join(["one", "two"]) == "one two"


def test_a_small_act_is_cut_into_sections_checked_against_its_arrangement() -> None:
    def body(
        text: str, top: float, page: int = 2, x0: float = 75.0, bold: bool = False, markers: tuple[str, ...] = ()
    ) -> Line:
        return line(text, page, top, x0, bold, markers)

    arrangement = [
        line("ARRANGEMENT OF SECTIONS", top=50),
        line("CHAPTER I", top=70),
        line("PRELIMINARY", top=82),
        line("1. Short title.", top=100),
        line("2. Definitions.", top=112),
        line("CHAPTER II", top=130),
        line("OF PUNISHMENTS", top=142),
        line("3. Punishments.", top=160),
        line("THE EXAMPLE ACT", top=180),
        line("ACT NO. 1 OF 2099", top=192),
    ]
    lines = arrangement + [
        body("CHAPTER I", 100, x0=250),
        body("PRELIMINARY", 112, x0=250),
        body("1. Short title.—This Act may be called the Example Act.", 130, bold=True, markers=("1",)),
        body("2. Definitions.—In this Act,—", 148, bold=True),
        body("(a) “court” means a court established under", 166, x0=93),
        body("section 3; and", 178, x0=75),
        body("3. A numbered item inside a definition", 196, x0=93),
        body("STATE AMENDMENT", 214, x0=250),
        body("Example State", 226),
        body("2A. Something.—Inserted by a state", 238, bold=True),
        body("CHAPTER II", 262, x0=250),
        body("OF PUNISHMENTS", 274, x0=250),
        body("3. Punishments.—The punishments are death and", 292, bold=True),
        body("fine.", 304, x0=57),
        body("Explanation.—Fine is money.", 70, page=3),
        body("THE SCHEDULE", 88, page=3, x0=250),
        body("1. A row of the schedule", 106, page=3),
    ]
    notes = [Footnote(2, "1", "Comes into force on a date the Government notifies.")]
    parsed = parse_lines("example", lines, notes, pages=3)

    assert [s.number for s in parsed.sections] == ["1", "2", "3"]
    assert parsed.missing == [] and parsed.unused == []
    assert [found.text for found in parsed.inserted_by_states] == ["2A. Something.—Inserted by a state"]
    first, second, third = parsed.sections
    assert (first.heading, first.paragraphs) == ("Short title", ["This Act may be called the Example Act."])
    assert (first.chapter, first.chapter_title) == ("CHAPTER I", "PRELIMINARY")
    assert first.footnotes == notes
    assert second.paragraphs == [
        "In this Act,—",
        "(a) “court” means a court established under section 3; and",
        "3. A numbered item inside a definition",
    ]
    assert second.state_amendments and second.state_amendments[0].startswith("Example State")
    assert (third.heading, third.chapter, third.chapter_title) == ("Punishments", "CHAPTER II", "OF PUNISHMENTS")
    assert third.paragraphs == ["The punishments are death and fine.", "Explanation.—Fine is money."]
    assert third.pages == (2, 3)


def test_a_number_printed_with_a_hyphen_is_kept_without_it() -> None:
    assert split_heading("171-I. Failure to keep election accounts.—Whoever being required") == (
        "171I",
        "Failure to keep election accounts",
        "Whoever being required",
    )
    listed = parse_arrangement(
        [
            line("ARRANGEMENT OF SECTIONS"),
            line("171H. Illegal payments in connection with an election."),
            line("171-I. Failure to keep election accounts."),
        ]
    )
    assert [entry.number for entry in listed] == ["171H", "171I"]


def test_gaps_in_the_numbering_are_found() -> None:
    assert numbering_gaps(["1", "2", "4", "4A", "4C", "5"]) == ["3", "4B"]
    assert numbering_gaps(["1", "2", "2A", "2AA", "2B", "3"]) == []


def test_the_arrangement_names_the_group_of_each_section() -> None:
    lines = [
        centred("ARRANGEMENT OF SECTIONS"),
        centred("CHAPTER XVII"),
        centred("OF OFFENCES AGAINST PROPERTY", half=90),
        centred("Of theft"),
        placed("303. Theft.", 90, 150),
        placed("304. Snatching, and the punishment for it when the snatching is", 90, 520),
        centred("committed by night.", half=50),  # centred by chance, but the heading above is still open
        centred("Of extortion"),
        placed("308. Extortion.", 90, 160),
        placed("A.—Summons", 270, 330),
        placed("309. Robbery.", 90, 160),
    ]
    entries = parse_arrangement(lines)
    assert [(entry.number, entry.group) for entry in entries] == [
        ("303", "Of theft"),
        ("304", "Of theft"),
        ("308", "Of extortion"),
        ("309", "A.—Summons"),
    ]
    assert entries[0].chapter_title == "OF OFFENCES AGAINST PROPERTY"
    assert entries[1].heading.endswith("when the snatching is committed by night.")


def test_group_headings_are_cut_from_the_body_and_checked_against_the_arrangement() -> None:
    arrangement = [
        centred("ARRANGEMENT OF SECTIONS", top=40),
        centred("CHAPTER I", top=60),
        centred("PRELIMINARY", top=72),
        placed("1. Short title.", 90, 160, top=90),
        centred("Of theft", top=102),
        placed("2. Theft.", 90, 140, top=114),
        centred("CHAPTER II", top=126),
        centred("OF PUNISHMENTS", top=138),
        centred("Of extortion", top=150),
        placed("3. Extortion.", 90, 160, top=162),
        placed("4. Robbery.", 90, 160, top=174),
        centred("ACT NO. 1 OF 2099", top=200),
    ]
    body = [
        placed("1. Short title.—This Act may be called the Example Act.", 75, 400, top=100, page=2, bold=True),
        centred("Of theft", top=120, page=2),
        placed("2. Theft.—Whoever takes what is not his commits theft as set out in", 75, 520, 140, 2, True),
        placed("(a) the first clause, set by chance in the middle of the line;", 120, 475, top=153, page=2),
        centred("CHAPTER II", top=175, page=2),
        centred("OF PUNISHMENTS", top=190, page=2),
        centred("Of extortion", top=205, page=2),
        placed("3. Extortion.—Whoever puts a person in fear commits extortion.", 75, 520, top=225, page=2, bold=True),
        placed("4. Robbery.—Theft or extortion with violence is robbery.", 75, 520, top=245, page=2, bold=True),
        centred("STATEMENT OF OBJECTS AND REASONS", top=275, page=2, half=110),
        placed("The Bill seeks to achieve the above objectives.", 75, 400, top=295, page=2),
    ]
    parsed = parse_lines("example", arrangement + body, [], pages=2)

    assert [section.number for section in parsed.sections] == ["1", "2", "3", "4"]
    one, two, three, four = parsed.sections
    assert one.paragraphs == ["This Act may be called the Example Act."]
    assert two.paragraphs[-1] == "(a) the first clause, set by chance in the middle of the line;"
    assert (two.group, three.group, four.group) == ("Of theft", "Of extortion", "Of extortion")
    assert (three.chapter, three.chapter_title) == ("CHAPTER II", "OF PUNISHMENTS")
    assert four.paragraphs == ["Theft or extortion with violence is robbery."]
    assert parsed.group_headings == [("2", "Of theft"), ("3", "Of extortion")]
    assert parsed.gaps == [] and groups_that_differ(parsed) == []

    body[1] = centred("Of thefts", top=120, page=2)
    reparsed = parse_lines("example", arrangement + body, [], pages=2)
    assert groups_that_differ(reparsed) == ['before section 2: listed "Of theft", found "Of thefts"']


def test_a_clause_starts_a_paragraph_after_an_indent_and_a_cross_reference_does_not() -> None:
    lines = [
        line("1. The court may,—", top=100, x0=75),
        line("(a) hear the case; and", top=113, x0=93),
        line("decide it under clause", top=126, x0=57),
        line("(b) of sub-section (2) of section 3; or", top=139, x0=57),
        line("(c) send it to another court.", top=158, x0=93),
    ]
    assert _breaks(lines, {1: 13.0}) == [True, True, False, False, True]
