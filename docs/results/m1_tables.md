# M1: the tables

Made by `python scripts/make_tables.py` from `data/raw` and the parsed Acts (decisions 5 and 24).
Machine: Darwin 27.2.0 arm64; Python 3.13.6; pdfplumber 0.11.10.

## The BNSS First Schedule

| Part | Rows | BNS sections | Rows opened by a lead in | Rows naming no BNS section | Rows out of order |
|---|---:|---:|---:|---:|---:|
| I, offences under the BNS | 464 | 287 | 2 | 0 | 0 |
| II, offences under other laws | 3 | | | | |

Rows naming no BNS section: a row whose section number is not a section of the parsed BNS. Rows out of order: a row whose section comes before the row above it; the schedule follows the BNS, so either would show a number read wrongly or put on the wrong row. A lead in opens an offence that the schedule then splits into clauses, (a) and (b); each clause is a row of its own, with the lead in.

| Column | Its values, as classes |
|---|---|
| Cognizable | cognizable 294, non-cognizable 148, depends 23, conditional 2 |
| Bailable | bailable 254, non-bailable 197, depends 16 |
| Court | Any Magistrate 164, Magistrate of the first class 145, Court of Session 119, depends 39 |

Each value as one class. Depends: the value turns on another offence, or on where the offence is committed ("According as offence abetted is cognizable or non-cognizable", "Court by which offence abetted is triable"). Conditional: the value states a condition ("only on the complaint of the victim"). Other: the value could not be classed.

### Punishment against the BNS

414 rows of Part I state a term of punishment (years, months, life or death); for 414, every term appears in the words of the row's BNS section (7 years as "seven years"). The rest state none ("Same as for offence abetted", "Fine").

No stated term is missing from its section.

BNS sections whose words punish ("shall be punished", "be punishable") but which no row of Part I names: 1, 8, 10, 307.

### What stands out

* section 67, page 177: cognizable "Cognizable (only on the complaint of the victim)."
* section 85, page 179: cognizable "Cognizable if information relating to the commission of the offence is given to an officer in charge of a police station by the person aggrieved by the offence or by any person related to her by blood, marriage or adoption or if there is no such relative, by any public servant belonging to such class or category as may be notified by the State Government in this behalf."

### Hand check (decision 5)

50 rows drawn with seed 5 into `docs/checks/first_schedule.csv`; none checked yet.

## The old to new correspondence

| Table | Rows | New sections without a row | Rows naming a section the Acts lack | Rows out of order | Words inside its rules | Words no row holds | Words held twice |
|---|---:|---:|---:|---:|---:|---:|---:|
| BNS to IPC | 533 | 0 | 0 | 0 | 12609 | 10 | 0 |
| BNSS to CrPC | 558 | 0 | 0 | 0 | 11807 | 8 | 0 |
| BSA to IEA | 193 | 0 | 0 | 0 | 4454 | 8 | 0 |

CAPT Bhopal's three tables, one row for each provision of the new Act that CAPT compares. A row out of order names a section before the one above it. The words inside a table's rules are counted on the page and in the rows read from it: a word no row holds was lost, unless it is the table's header, which is not a row; a word held twice was read twice. The words no row holds: BNS to IPC: bns, comparison, ipc, of, ons, sections, sections, subject, subsecti, summary; BNSS to CrPC: bnss, comparison, crpc, of, sections, sections, subject, summary; BSA to IEA: bsa, comparision, iea, of, section, section, subject, summary.

| Table | Unchanged | Modified | New | Heading | One to one | Merged | Split | Merged and split |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BNS to IPC | 261 | 250 | 21 | 1 | 288 | 217 | 5 | 1 |
| BNSS to CrPC | 307 | 237 | 14 | 0 | 542 | 2 | 0 | 0 |
| BSA to IEA | 99 | 91 | 3 | 0 | 160 | 30 | 0 | 0 |

What changed comes from CAPT's own words. Unchanged: the comparison says no more than "No change", that the old section is now a subsection of the new one with its heading dropped, or the note made once that "Code" becomes "Sanhita" throughout. New: the old column says New, or a dash. Heading: the old column is empty and rows for the section's subsections follow. Modified: anything else. The shape comes from the sections the rows name, taken whole: merged when a new section takes in several old ones, split when an old section went to several new ones.

Old sections in force that no row names; each was dropped by the new Act, or went into a new section without CAPT naming it, and the text comparison of decision 24 tells which:

* IPC: 14, 18, 50, 53A, 124A, 143, 153AA, 236, 264, 265, 266, 267, 309, 310, 311, 376DA, 377, 444, 446, 497
* CrPC: 8, 10, 16, 17, 18, 19, 27, 153, 355, 404
* IEA: 22A, 82, 88, 113, 166

### Hand check (decisions 5 and 24)

50 rows drawn with seed 5 into `docs/checks/correspondence.csv`; none checked yet.
