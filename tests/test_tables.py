from dhara.tables import ScheduleRow, TableLine, assemble, base_section, court_kind, kind, terms


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
