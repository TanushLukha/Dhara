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

50 rows in `docs/checks/first_schedule.csv`, drawn with seed 5; none checked yet.

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

### Hand check (decisions 5 and 24)

50 rows in `docs/checks/correspondence.csv`, drawn with seed 5; none checked yet.

### Old sections that no row names (decision 24)

Each old section in force that no row names was dropped by the new Act, or went into a new section without CAPT naming it. For each, the comparison finds the new section that holds the largest share of its phrases (runs of three words, each weighted by how rare it is across both Acts, so that the formulas every section repeats count for little), and the runner up. A share of 0.5 or more proposes that it went into that section; less proposes that it was dropped. Tanush confirms each.

| Old section | Its heading | Nearest new section | Share | Runner up | Share | Proposed |
|---|---|---|---:|---|---:|---|
| IPC 14 | “Servant of Government” | BNS 178 (Counterfeiting coin, Government stamps, currency-notes or bank-notes) | 0.13 | BNS 72 | 0.06 | omitted |
| IPC 18 | “India” | BNS 99 (Buying child for purposes of prostitution, etc) | 0.00 | BNS 98 | 0.00 | omitted |
| IPC 50 | “Section” | BNS 310 (Dacoity) | 0.04 | BNS 3 | 0.04 | omitted |
| IPC 53A | Construction of reference to transportation | BNS 2 (Definitions) | 0.07 | BNS 1 | 0.06 | omitted |
| IPC 124A | Sedition | BNS 152 (Act endangering sovereignty, unity and integrity of India) | 0.37 | BNS 197 | 0.11 | omitted |
| IPC 143 | Punishment | BNS 189 (Unlawful assembly) | 0.82 | BNS 190 | 0.34 | into BNS 189 |
| IPC 153AA | Punishment for knowingly carrying arms in any procession or organising, or holding or taking part in any mass drill or mass training with arms | BNS 287 (Negligent conduct with respect to fire or combustible matter) | 0.04 | BNS 207 | 0.04 | omitted |
| IPC 236 | Abetting in India the counterfeiting out of India of coin | BNS 61 (Criminal conspiracy) | 0.12 | BNS 341 | 0.12 | omitted |
| IPC 264 | Fraudulent use of false instrument for weighing | BNS 326 (Mischief by injury, inundation, fire or explosive substance, etc) | 0.24 | BNS 246 | 0.23 | omitted |
| IPC 265 | Fraudulent use of false weight or measure | BNS 345 (Property mark) | 0.11 | BNS 75 | 0.09 | omitted |
| IPC 266 | Being in possession of false weight or measure | BNS 217 (False information, with intent to cause public servant to use his lawful power to injury of another person) | 0.12 | BNS 326 | 0.12 | omitted |
| IPC 267 | Making or selling false weight or measure | BNS 185 (Erasure of mark denoting that stamp has been used) | 0.12 | BNS 326 | 0.10 | omitted |
| IPC 309 | Attempt to commit suicide | BNS 226 (Attempt to commit suicide to compel or restrain exercise of lawful power) | 0.38 | BNS 62 | 0.31 | omitted |
| IPC 310 | Thug | BNS 8 (Amount of fine, liability in default of payment of fine, etc) | 0.07 | BNS 113 | 0.06 | omitted |
| IPC 311 | Punishment | BNS 143 (Trafficking of person) | 0.38 | BNS 140 | 0.38 | omitted |
| IPC 376DA | Punishment for gang rape on woman under sixteen years of age | BNS 70 (Gang rape) | 0.86 | BNS 65 | 0.50 | into BNS 70 |
| IPC 377 | Unnatural offences | BNS 118 (Voluntarily causing hurt or grievous hurt by dangerous weapons or means) | 0.14 | BNS 178 | 0.14 | omitted |
| IPC 444 | Lurking house-trespass by night | BNS 331 (Punishment for house-trespass or house-breaking) | 0.31 | BNS 330 | 0.29 | omitted |
| IPC 446 | House-breaking by night | BNS 43 (Commencement and continuance of right of private defence of property) | 0.30 | BNS 41 | 0.30 | omitted |
| IPC 497 | Adultery | BNS 84 (Enticing or taking away or detaining with criminal intent a married woman) | 0.20 | BNS 69 | 0.15 | omitted |
| CrPC 8 | Metropolitan areas | BNSS 341 (Legal aid to accused at State expense in certain cases) | 0.05 | BNSS 2 | 0.03 | omitted |
| CrPC 10 | Subordination of Assistant Sessions Judges | BNSS 8 (Court of Session) | 0.58 | BNSS 13 | 0.14 | into BNSS 8 |
| CrPC 16 | Courts of Metropolitan Magistrates | BNSS 9 (Courts of Judicial Magistrates) | 0.55 | BNSS 524 | 0.12 | into BNSS 9 |
| CrPC 17 | Chief Metropolitan Magistrate and Additional Chief Metropolitan Magistrate | BNSS 10 (Chief Judicial Magistrate and Additional Chief Judicial Magistrate, etc) | 0.44 | BNSS 14 | 0.27 | omitted |
| CrPC 18 | Special Metropolitan Magistrates | BNSS 11 (Special Judicial Magistrates) | 0.68 | BNSS 10 | 0.09 | into BNSS 11 |
| CrPC 19 | Subordination of Metropolitan Magistrates | BNSS 13 (Subordination of Judicial Magistrates) | 0.36 | BNSS 17 | 0.25 | omitted |
| CrPC 27 | Jurisdiction in the case of juveniles | BNSS 401 (Order to release on probation of good conduct or after admonition) | 0.21 | BNSS 207 | 0.11 | omitted |
| CrPC 153 | Inspection of weights and measures | BNSS 175 (Police officer’s power to investigate cognizable case) | 0.10 | BNSS 185 | 0.09 | omitted |
| CrPC 355 | Metropolitan Magistrate's judgment | BNSS 286 (Record in summary trials) | 0.28 | BNSS 287 | 0.06 | omitted |
| CrPC 404 | Statement by Metropolitan Magistrate of grounds of his decision to be considered by High Court | BNSS 454 (Execution of sentence of death passed by High Court) | 0.04 | BNSS 401 | 0.04 | omitted |
| IEA 22A | When oral admission as to contents of electronic records are relevant | BSA 20 (When oral admissions as to contents of documents are relevant) | 0.46 | BSA 62 | 0.08 | omitted |
| IEA 82 | Presumption as to document admissible in England without proof of seal or signature | BSA 79 (Presumption as to documents produced as record of evidence, etc) | 0.10 | BSA 78 | 0.08 | omitted |
| IEA 88 | Presumption as to telegraphic messages | BSA 90 (Presumption as to electronic messages) | 0.34 | BSA 119 | 0.07 | omitted |
| IEA 113 | Proof of cession of territory | BSA 116 (Birth during marriage, conclusive proof of legitimacy) | 0.04 | BSA 52 | 0.02 | omitted |
| IEA 166 | Power of jury or assessors to put questions | BSA 168 (Judge’s power to put questions or order production) | 0.04 | BSA 149 | 0.04 | omitted |

35 rows in `docs/checks/unnamed.csv`, every one; none checked yet.
