from dhara.tables import (
    Correspondence,
    ScheduleRow,
    TableLine,
    _section_in,
    _shaped,
    assemble,
    base_section,
    change_of,
    court_kind,
    kind,
    nearest,
    old_sections,
    phrases,
    terms,
)


def row(top: float, *cells: str, page: int = 1) -> TableLine:
    return TableLine(page, top, cells)


def test_rows_start_where_the_offence_and_the_values_begin_together() -> None:
    lines = [
        row(87, "", "Abetment of an offence,", "Imprisonment", "According as", "Non-bailable.", "Court by which"),
        row(100, "55", "punishable with death.", "for 7 years.", "offence abetted.", "", "it is triable."),
        row(113, "", "If an act which causes", "Imprisonment", "According as", "Non-bailable.", "Court by which"),
        row(126, "", "harm.", "for 14 years.", "offence abetted.", "", "it is triable."),
        row(139, "56", "Abetment, if not", "Fine.", "Non-", "Bailable.", "Any Magistrate."),
        row(152, "", "committed.", "", "cognizable.", "", ""),
    ]
    rows = assemble(lines, "I")
    assert [(r.section, r.offence) for r in rows] == [
        ("55", "Abetment of an offence, punishable with death."),
        ("55", "If an act which causes harm."),
        ("56", "Abetment, if not committed."),
    ]
    assert rows[0].punishment == "Imprisonment for 7 years." and rows[2].cognizable == "Non-cognizable."


def test_a_wrapped_reference_and_a_lead_in_are_put_together() -> None:
    lines = [
        row(87, "61(2)", "Criminal conspiracy to", "Same as for", "According as", "According as", "Court by which"),
        row(100, "(a)", "commit a grave offence.", "abetment.", "it is.", "it is.", "it is triable."),
        row(87, "264", "Omission to apprehend, in", "", "", "", "", page=2),
        row(100, "", "cases not provided for:", "", "", "", "", page=2),
        row(113, "", "(a) if intentional;", "Imprisonment.", "Non-", "Bailable.", "Magistrate of the", page=2),
        row(126, "", "", "", "cognizable.", "", "first class.", page=2),
        row(139, "", "(b) if negligent.", "Simple imprisonment.", "Non-", "Bailable.", "Any Magistrate.", page=2),
        row(152, "", "", "", "cognizable.", "", "", page=2),
    ]
    rows = assemble(lines, "I")
    assert [r.section for r in rows] == ["61(2)(a)", "264", "264"]
    assert rows[1].offence == "Omission to apprehend, in cases not provided for: (a) if intentional;"
    assert rows[1].lead_in == "Omission to apprehend, in cases not provided for:"
    assert (rows[2].court, rows[2].page) == ("Any Magistrate.", 2)


def test_a_row_runs_on_to_the_next_page() -> None:
    lines = [
        row(640, "263(e)", "If sentenced to death.", "Imprisonment for life,", "Cognizable.", "Bailable.", "Court of"),
        row(87, "", "", "or for 10 years.", "", "", "Session.", page=2),
    ]
    (only,) = assemble(lines, "I")
    assert only.punishment == "Imprisonment for life, or for 10 years."
    assert (only.court, only.page) == ("Court of Session.", 1)


def test_part_two_has_four_columns_and_no_section() -> None:
    lines = [
        row(158, "If punishable with death,", "Cognizable.", "Non-bailable.", "Court of Session."),
        row(170, "or imprisonment for life.", "", "", ""),
    ]
    offence = "If punishable with death, or imprisonment for life."
    assert assemble(lines, "II") == [
        ScheduleRow("II", None, offence, None, "Cognizable.", "Non-bailable.", "Court of Session.", 1)
    ]


def test_values_are_classed() -> None:
    assert kind("Non-cognizable.", "cognizable") == "non-cognizable"
    assert kind("Cognizable", "cognizable") == "cognizable"
    assert kind("According as offence abetted is bailable or non-bailable.", "bailable") == "depends"
    assert kind("Cognizable (only on the complaint of the victim).", "cognizable") == "conditional"
    assert kind("Cognizable. Non-cognizable.", "cognizable") == "other"
    assert court_kind("Magistrate f the firstclass.") == "Magistrate of the first class"
    assert court_kind("The Court in which the offence is committed, or any Magistrate.") == "depends"
    assert court_kind("Any Magistrate.]") == "Any Magistrate"
    assert court_kind("Court of Session.") == "Court of Session"


def test_references_and_terms_are_read() -> None:
    assert base_section("356(3)") == "356" and base_section("58(a)") == "58" and base_section("(a)") is None
    assert terms("Imprisonment for 7 years and fine.") == ["seven years"]
    assert terms("Imprisonment for life, or imprisonment for 10 years and fine.") == ["ten years", "life"]
    assert terms("Simple imprisonment for 1 month, or fine of 5,000 rupees.") == ["one month"]
    assert terms("Death, or imprisonment for life.") == ["life", "death"]
    assert terms("Same as for offence abetted.") == []


def test_old_references_name_their_sections() -> None:
    assert old_sections("29 and 29A") == ("29", "29A")
    assert old_sections("54 & 55") == ("54", "55")
    assert old_sections("376(1) & 376(2)") == ("376",)
    assert old_sections("228A (1)/(2)") == ("228A",)
    ranges = ("230", "231", "232", "246", "247", "248", "249", "255", "489A")
    assert old_sections("230 to 232, 246 to 249, 255, 489A") == ranges
    assert old_sections("354A to 354D") == ("354A", "354B", "354C", "354D")
    assert old_sections("233 / 234 / 235") == ("233", "234", "235")
    assert old_sections("171-I") == ("171I",)
    assert old_sections("498A Explanat ion") == ("498A",)
    assert old_sections("23 Clause-1") == ("23",)
    assert old_sections("2(a)]") == ("2",) and old_sections("2 (wa)") == ("2",)
    assert old_sections("3, para 1") == ("3",) and old_sections("IEA 3 Interpret ation clause") == ("3",)
    assert old_sections("New") == () and old_sections("-") == () and old_sections("New sub- section") == ()


def test_the_change_is_read_from_the_comparison() -> None:
    assert change_of(("33",), "33", "No change.") == "unchanged"
    assert change_of(("6",), "6", "Section is included as sub-section in BNS sans heading.") == "unchanged"
    moved = "Section is included as a sub-section in BNS sans heading. No other Changes."
    assert change_of(("150",), "150", moved) == "unchanged"
    assert change_of(("143",), "143", "Section 143 IEA is included as subsection (4) of 146 BSA.") == "unchanged"
    once = (
        'No change except "Code" is replaced with "Sanhita". Wherever the word “Code” is used in CrPC, the word '
        "“Sanhita” is used in BNSS, therefore, this fact will not be specifically mentioned in this table hereinafter."
    )
    assert change_of(("2",), "2(d)", once) == "unchanged"
    assert change_of(("115",), "115", '"pleader" is replaced by "advocate".') == "modified"
    assert change_of(("9",), "9", 'No change except the words "Notwithstanding anything" are excluded.') == "modified"
    assert change_of((), "New", "Newly added.") == "new"
    assert change_of((), "", "In the IPC, definitions are not consolidated in a single section.") == "heading"


def test_shapes_follow_whole_sections() -> None:
    def pair(new: str, old: tuple[str, ...]) -> Correspondence:
        return Correspondence("t", new, _section_in(new) or "", " & ".join(old), old, "", "", "", "modified", "", 1)

    rows = _shaped(
        [
            pair("2(8)", ("29", "29A")),
            pair("64", ("376",)),
            pair("65(1)", ("376",)),
            pair("65(2)", ("376AB",)),
            pair("318(4)", ("420",)),
            pair("First proviso to section 22", ("28",)),
            pair("113", ()),
        ]
    )
    assert [row.shape for row in rows] == [
        "merged", "split", "merged and split", "merged", "one to one", "one to one", ""
    ]
    assert rows[5].new_section == "22"


def test_the_comparison_finds_where_an_old_section_went_and_discounts_formulas() -> None:
    formula = "shall be punished with imprisonment for a term which may extend to three years"
    old = {
        "143": f"Whoever is a member of an unlawful assembly {formula}",
        "309": f"Whoever attempts to commit suicide {formula}",
        "1": f"Whoever steals {formula}",
    }
    new = {
        "189": f"(2) Whoever is a member of an unlawful assembly {formula}",
        "226": f"Whoever cheats a public servant {formula}",
        "303": f"Whoever steals {formula}",
    }
    found = nearest(old, new, ["143", "309"])
    assert found["143"][0][1] == "189" and found["143"][0][0] > 0.9
    assert found["309"][0][0] < 0.5  # the formula is shared by every section, so it counts for little
    assert ("shall", "be", "punished") in phrases(formula)
