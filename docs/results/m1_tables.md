# M1: the tables

Made by `python scripts/make_tables.py` from `data/raw/bnss.pdf` and the parsed BNS (decision 5).
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

## Punishment against the BNS

414 rows of Part I state a term of punishment (years, months, life or death); for 414, every term appears in the words of the row's BNS section (7 years as "seven years"). The rest state none ("Same as for offence abetted", "Fine").

No stated term is missing from its section.

BNS sections whose words punish ("shall be punished", "be punishable") but which no row of Part I names: 1, 8, 10, 307.

## What stands out

* section 67, page 177: cognizable "Cognizable (only on the complaint of the victim)."
* section 85, page 179: cognizable "Cognizable if information relating to the commission of the offence is given to an officer in charge of a police station by the person aggrieved by the offence or by any person related to her by blood, marriage or adoption or if there is no such relative, by any public servant belonging to such class or category as may be notified by the State Government in this behalf."

## Hand check (decision 5)

50 rows drawn with seed 5 into `docs/checks/first_schedule.csv`; none checked yet.
