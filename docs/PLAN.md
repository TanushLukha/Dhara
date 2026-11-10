# Dhara plan

Dhara (धारा, "section" in Hindi, as in "dhara 420") answers questions about India's criminal law
Acts and cites the sections it relies on. It is built in six measured steps, as DocLens was, and every
step is compared with what people actually use: a large language model answering from memory, and
the standard RAG recipe from tutorials.

Status: agreed, and M1 has started; Tanush's decisions are listed near the end. Numbers marked
"estimate" come from the sources at the end and the arithmetic in Appendix A; M1 replaces each of them
with a measurement on the M2 MacBook Air. Nothing here is legal advice: Dhara reports what the text of
the Acts says.

## What Dhara is, and why it is worth building

The Bharatiya Nyaya Sanhita (BNS), the Bharatiya Nagarik Suraksha Sanhita (BNSS) and the Bharatiya
Sakshya Adhiniyam (BSA) replaced the Indian Penal Code (IPC), the Code of Criminal Procedure (CrPC)
and the Indian Evidence Act (IEA). Sections were renumbered (cheating, IPC 420, is now BNS 318;
murder's punishment, IPC 302, is BNS 103; sedition, IPC 124A, gave way to BNS 152), offences were
added and merged, and offences committed before the change still fall under the old Acts. So a model
answering from memory is likely to mix the two codes or invent a section, and retrieval alone does not
fix that: Stanford's study of commercial legal research tools built on retrieval found hallucinated
answers to 17% to 33% of its questions.

What the project shows:

* **RAG done properly:** statutes parsed into sections with their hierarchy; BM25, dense, hybrid and
  reranked retrieval, each measured against the same questions.
* **An agent that has to earn its place:** a LangGraph agent with exact lookup tools, a CRAG style
  check of what retrieval found, a check of every citation before it answers, and a question back or a
  refusal when the Acts cannot answer as asked; ablations show what each part adds and what it costs.
* **Evaluation discipline:** a hand checked question set, a judge validated against hand labels,
  intervals and paired tests, a test set read once.
* **Backend engineering:** FastAPI with streaming, PostgreSQL with pgvector and BM25, Docker Compose,
  caching, rate limits, a load test with latency percentiles, CI.
* **Deployment trade offs:** a local model on the Mac against API models, in accuracy, latency, cost
  per thousand questions and privacy.

The question running through it: how often does Dhara answer a question about India's criminal law
Acts correctly and cite the right section, what does each piece add (structure aware chunks, hybrid
search, reranking, an agent that plans, retrieves again and checks its citations), measured against a
model answering from memory and the standard RAG recipe, and at what latency and cost?

Roles (ROLE_STRATEGY.md): AI engineer, paired with TinyGPT; SDE backend, paired with P11.

## Milestones

| Milestone | Question | Built | Measured on |
|---|---|---|---|
| M1 Baseline | How well do LLMs answer from memory, and how well does the standard RAG recipe do, on a hand checked question set scored one way for every system? | the corpus as sections, the question sets, the scorer, a validated judge, an LLM client with cache and quota pacing, a benchmark of local models | validation questions: accurate rate, hallucination rate, citation F1, abstention, latency, cost |
| M2 Retrieval | Which retrieval puts the right sections in front of the model, and what does each choice add? | section aware chunks, BM25, dense embedders, hybrid fusion, rerankers, direct section lookup | validation questions: recall at k, MRR and nDCG@10 at the section level, latency |
| M3 Answers | Given the sections found, how often is the answer right and rightly cited, and how much is lost to finding rather than answering? | a grounded answer generator with structured citations, citation checks, the oracle ceiling | validation questions: M1's metrics with oracle, best and standard retrieval |
| M4 Agent | What does an agent add over M3's best pipeline, and at what cost in calls, tokens and seconds? | a LangGraph agent: routing, planning, lookup, mapping and classification tools, retrieving again, citation verification, abstention | validation questions: M1's metrics, ablations, calls and latency per question |
| M5 Comparison | On the sealed test set, read once, where does Dhara stand against the strongest free models answering from memory and the standard recipe, and what do local and API models trade? | one harness for every frozen system and generator | test questions: every metric with intervals, latency p50 and p95, cost per 1,000 questions at list prices, memory, licence |
| M6 Ship | Can someone use it, does the service answer as M5 measured, and at what latency under load? | FastAPI service with streaming, PostgreSQL (pgvector, BM25), Docker Compose, a demo page, CI | the test set through the service, load test percentiles, retrieval agreement with M2 |

Each milestone leaves code the next one reuses, ends with "What M<n> found, and what it means for
M<n+1>", and is done only when lint, type checks and every test pass locally and CI is green.

## Data

### The Acts

| Act | Replaced | Numbered sections | Notes |
|---|---|---:|---|
| Bharatiya Nyaya Sanhita, 2023 (BNS) | IPC | 358 | 20 chapters in India Code's arrangement of sections |
| Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS) | CrPC | 531 | its First Schedule classifies every BNS offence |
| Bharatiya Sakshya Adhiniyam, 2023 (BSA) | IEA | 170 | |
| Indian Penal Code, 1860 (IPC) | | 511 | plus lettered sections such as 304B and 498A |
| Code of Criminal Procedure, 1973 (CrPC) | | 484 | plus lettered sections such as 54A |
| Indian Evidence Act, 1872 (IEA) | | 167 | plus lettered sections such as 65B |

Together about 2,200 numbered sections, more with the lettered ones; M1 counts them exactly. Two
tables come with them: the BNSS First Schedule (for each offence: punishment, cognizable or not,
bailable or not, which court tries it) and the correspondence between old and new sections, compiled
from the correspondence tables the Central Academy for Police Training, Bhopal (CAPT) has published,
one for each pair of Acts, each row labelled by what changed and by its shape (decision 24). The
commencement notifications, as India Code's footnotes record them, join the corpus too (decision 25).

### Questions

| Set | What | Size | Used in |
|---|---|---:|---|
| Validation | hand checked questions, gold sections, key facts, answerable or not | 150 | every choice in M1 to M4 |
| Test | the same, drawn from other sections, sealed | 300 | read once in M5; again in M6 through the service |
| Reserve | the same, sealed | 100 | only if a fault found on the test set forces a fresh test (working rule 5) |
| Judge labels | Tanush's pass or fail labels of system answers | about 150 in M1, 100 in M4 | validating the judge |
| IL TUR statute identification (optional) | case facts from court judgments with the IPC sections they cite | a sample of its test split | a held out retrieval check in M2 |

Question types, for the 300 test questions (validation and reserve in the same shares):

| Answerable (240) | | Not answerable from the Acts (60) | |
|---|---:|---|---:|
| what a section says, asked by number | 30 | false premise (a section or offence that does not exist) | 15 |
| punishment | 40 | outside the Acts (case law, interpretation, other laws, state amendments) | 25 |
| definition | 25 | advice or prediction ("should I", "will I win") | 10 |
| procedure (BNSS, CrPC) | 35 | missing a fact the answer turns on (Dhara should ask) | 10 |
| evidence (BSA, IEA) | 25 | | |
| classification (bailable, cognizable, which court) | 20 | | |
| old to new mapping | 25 | | |
| what changed between old and new | 15 | | |
| needs two or more sections | 15 | | |
| which law applies, by when the offence happened | 10 | | |

Across types: about 40% asked the way a layperson would ask (a situation, not a section number), and
about 10% in Hinglish ("dhara 420 kya hai"); every Act covered.

## How results are scored

The unit of a citation is an Act and a section number (BNS 103); subsections are scored as a second,
stricter level. Every question carries its required gold sections, sections that are also acceptable,
and key facts: short, checkable statements the answer must contain ("imprisonment up to seven years",
"and fine").

* **Accurate** (the headline): an answerable question answered correctly and grounded, or an
  unanswerable one declined (or its false premise corrected, or the missing fact asked for). The terms
  are adapted from Stanford's legal research study: **correct** means every key fact is stated and
  nothing contradicts the gold answer; **grounded** means each key statement cites a section that
  supports it.
* **Hallucinated:** an incorrect statement, or a misgrounded one: a cited section that does not exist,
  does not support the statement, or does not apply (the repealed IPC cited for an offence the BNS
  governs).
* **Incomplete:** an answerable question declined, or answered without citations.
* **Citation precision, recall and F1:** cited sections that are gold, over cited sections; required
  gold sections cited, over required ones.
* **Answer, ask or decline:** each answer's outcome against the question's gold outcome, as a 3 by 3
  table, with the precision and recall of declining and of asking (decision 25).
* **Code confusion:** the share of answers citing the old code where the new one applies, or the
  reverse. Specific to this corpus, and the failure most worth a story.
* **Retrieval (M2):** recall at 1, 5, 10 and 20 (every required section found, and any found), MRR
  and nDCG@10, at the section level.
* **Cost and speed:** tokens and calls per question, seconds per question (p50, p95), USD per 1,000
  questions at list prices (nothing is paid), peak memory.

Every rate comes with a bootstrap 95% interval over questions grouped by their seed section, and
systems are compared in pairs on the same questions (decision 11).

## Models, and what runs where

Tanush chose free tiers only, so nothing is paid. Everything that produces a number still runs on the
M2 MacBook Air: scoring, retrieval, embedders and rerankers on the Mac, local models through Ollama,
and free API models called from the Mac.

The free tiers checked for this plan (each console shows an account's exact limits; M1 records them):

| Provider and plan | Models used | Limits | May use prompts |
|---|---|---|---|
| NVIDIA's API catalog, free to members of the NVIDIA Developer Program (no card) | Mistral Small 4 and Mistral Large 3, Mistral's open weights | about 40 requests a minute for the account; no daily or token cap published | yes: its trial terms let NVIDIA improve its products with them |
| Gemini API, free tier | Gemini 3.5 Flash Lite | per model: 10 requests and 250,000 tokens a minute, 500 requests a day | yes, on the free tier |
| Groq, free plan | gpt oss 120b, Qwen3.8 27B (a preview model) | per model: 30 requests and 8,000 tokens a minute, 1,000 requests and 200,000 tokens a day | no |
| Ollama on the Mac | Qwen3.5 9B and 4B | none; time is the limit | nothing leaves the Mac |

Left out: Mistral's own API, whose Free mode no longer includes API access and whose consumer terms
limit the API to business customers (decision 14); Cerebras ended its open free tier (now a credit
trial that needs a card), GitHub Models has been retired, and OpenRouter's free models allow 50
requests a day.

The split (decision 14): NVIDIA's free endpoints carry the development model, because only they hold
the thousands of answers M3 to M6 need; Gemini 3.5 Flash Lite is the judge, from another family; the
Mistral model M1 does not keep and Groq's two models are the strongest free models compared; Qwen3.5
runs on the Mac. The whole project, estimate (Appendix A): about 12,500 generated answers and 5,600
judge calls; the development model's share is about 17,000 requests and 51 million tokens, which 40
requests a minute let through in about 7 hours of calls (longer if each call is slower, since the
client sends one at a time; M1 measures seconds per call); the judge needs about 11 days of Gemini's
daily quota, spread over the project; Groq 2 to 5 days per model; on the Mac, M5's runs take about 16
hours for the 9B model and 7 for the 4B, overnight. The client counts every limit (decision 15), so a
run pauses at a limit and resumes the next day from its cache.

On the Mac, estimate: llama.cpp's published M2 numbers for a 7B model at 4 bits (prompt about 180
tokens a second on 10 GPU cores, as in the 15 inch M2 Air; generation about 22) scaled to a 9B model
give about 23 s a question from memory, about 50 s with retrieval and about 2 minutes for the agent,
whose prompts are long: about 10 hours for the 300 test questions. Prompt length, not answer length,
dominates on the Mac.

Local models (Apache 2.0): Qwen3.5 9B and 4B (about 6.6 and 3.4 GB at 4 bits in Ollama), one family at
two sizes, so M5 shows what size buys. gpt oss 20b (about 14 GB in Ollama) is too tight beside the
embedder, the reranker and Docker; Gemma 4 is left out because the judge is Google's.

M5 still reports tokens per question and what 1,000 questions would cost at list prices, since cost
is an interview question; nothing is paid.

## Decisions for the whole project

Each decision: what we did, why, and why not the alternatives.

**1. Name and scope: Dhara, the six criminal law Acts.**
What: the repository `Dhara` (package `dhara`), covering BNS, BNSS, BSA and the IPC, CrPC and IEA
they replaced, with the BNSS First Schedule and the old to new correspondence.
Why: the old and new codes side by side give the questions that break models (renumbered sections,
merged offences, which law applies when), and every answer can be checked against a short, fixed
text. "Dhara" is what people say ("dhara 302"), and the section is the unit Dhara must cite.
Why not more Acts (IT Act, POCSO, NDPS): more text adds little that is new to measure and more to
check by hand; they can be added after M6 with the same pipeline. Why not judgments: Dhara answers
from statute text, which a non lawyer can check; case law is out of scope (decision 2).

**2. An answer is what the text of the Acts says.**
What: gold answers come from the Acts' text only. Questions that need case law, interpretation,
state amendments or advice are unanswerable by design, and Dhara must decline them and say why. The
service states that it is not legal advice and links every citation to its section's text.
Why: Tanush is not a lawyer, so every gold answer must be checkable by reading the cited sections; it
also gives abstention a precise target. States can amend these Acts for their own territory (Tamil
Nadu and Maharashtra have brought bills amending the BNS in their application), so "the central
text" is the honest scope.
Why not answer interpretive questions anyway: their gold answers could not be checked here, and a
wrong confident answer is the failure the project is about.

**3. India Code as the source, pinned.**
What: the official PDFs of the six Acts from India Code, the Legislative Department's portal,
downloaded by a script that records each file's URL, size and SHA256 in `data/MANIFEST.json` (the "as
on" note is read when the text is parsed); each SHA256 is committed in `src/dhara/corpus.py` once its
file is checked, and a download with another hash is refused (decision 29); India Code's per section
web pages as a cross check on a sample. India Code serves the three new Acts as central Acts; for the
repealed ones it does not at present. The CrPC's and the Evidence Act's central texts (footnotes up to
the 2019 amendments) are served from its Delhi and Chandigarh collections; for the IPC its current
pages list no file, so the text is India Code's own central file as the Internet Archive captured it
before the repeal. A file's hash is pinned once its title, as on note and last section are read; each
repealed Act's text is also checked against a second copy on 30 sections when it is parsed; the
commencement facts are those India Code's footnote to section 1 of each new Act records (decision 25).
The PDFs are not committed; the service shows a section's text beside its own answer.
Why: India Code states that its PDFs reproduce the officially adopted text and that the English
version prevails. Section 52(1)(q)(ii) of the Copyright Act permits reproducing an Act together with
commentary or other original matter, which is how Dhara shows text (this is a reading of the statute
and of PRS India's note, not legal advice). Pinning makes every number name its exact text.
Why not the Hugging Face scrape of India Code (`sukantan/nyaya-acts`): it states no licence and no
date. Why not commercial bare acts: copyright, and their editors' notes are not the law. Why not the
Hindi texts: India Code says the English version prevails; Hinglish questions are covered instead.

**4. Sections with their hierarchy as the unit.**
What: each Act parsed into Part, Chapter, Section, subsection and clause; explanations, illustrations
and provisos kept with their section; lettered sections (498A) and omitted ones recorded; footnotes
(amendment history) kept as metadata, out of the retrieval text. Parsed with pdfplumber, which reads
font sizes and positions. Checks: the parsed section numbers equal each Act's arrangement of
sections; 30 random sections compared by hand with India Code's section pages.
Why: the section is what users cite and what Dhara must cite, and the hierarchy gives headings and
chapter context to retrieval. Footnotes look like law but are editorial history.
Why not PyMuPDF: AGPL. Why not fixed size chunks as the stored unit: they cut sections apart, which is
exactly what the standard recipe does and what M2 measures against.

**5. The two tables as data, checked by hand.**
What: the BNSS First Schedule parsed into rows (section, offence, punishment, cognizable, bailable,
court); the correspondence table compiled from CAPT Bhopal's three tables (BNS to IPC, BNSS to CrPC,
BSA to IEA: one author and one layout for all three), many to many (one BNS section can replace
several IPC sections), each row labelled by what changed and by its shape (decision 24). Both checked
against the Acts on a random sample of 50 rows each, drawn with a fixed seed into a sheet under
`docs/checks/` that Tanush fills and the script counts. The schedule is read from the BNSS file
itself: each page's column edges come from the rules across the top of its table, every character goes
to the column its middle falls in (some cells are letter spaced, and a word would otherwise run from
one column into the next), and a row starts where the offence and at least two other columns begin in
capitals at the same height. Checks, in `m1_tables.md`: every row names a BNS section, the rows follow
the BNS in order, every value falls in a class (cognizable or not, bailable or not, which court, or
one that depends on another offence), and every term of punishment a row states (7 years, life)
appears in the words of its BNS section; the BNS sections that punish but have no row are listed
(India Code's schedule has none for section 307). CAPT's tables are ruled on every side, so
pdfplumber's table finder reads them, with three repairs: a row carried over from the page before has
no rule above it, so each page's table is closed where its column rules begin; a box drawn inside a
cell is skipped, its words being the cell's; and a cell the finder could not close is read from the
words inside its bounds. Their checks: every section of the new Act has a row, every section a row
names exists, the rows follow the new Act's order, and every word inside a table's rules reaches
exactly one row (the header aside).
Why: "is it bailable" and "what replaced IPC 420" are among the commonest questions, and both are
lookups in a table, not semantic search; the agent gets them as tools (M4). The schedule comes from
the pinned BNSS file rather than a copy on another site, so its rows are the law's own; CAPT's tables
come from a government police academy, cover all three pairs in one layout, and describe each change
in words, which decision 24 reads. The punishment check ties each row to the words of its section, so
a number put on the wrong row shows. Why not leave the tables to retrieval: a schedule row read as
text loses its columns; M4 measures what the tools add. Why not pdfplumber's own table finder for the
schedule: it is ruled only across its header, and the finder found no table on its pages. The word
check exists because counting rows was not enough: the first reading of CAPT's tables lost the first
row of most pages, dropped rows that name their provision in words ("First proviso to section 22") and
read some cells twice, and the coverage and word checks between them showed each. Why not the
comparison tables on lawyers' sites: they are unofficial, and nothing pins them.

## Decisions in M1

**6. Three question sets: validation 150, test 300, reserve 100.**
What: the sizes and type shares in the tables above; 80% answerable, 20% not; about 40% in a
layperson's words and 10% in Hinglish.
Why: at 300 questions a rate near 70% has a 95% interval of about plus or minus 5.2 points, and a
paired comparison detects a difference of 5 to 8 points (Appendix A); 150 validation questions are
enough to choose settings. The reserve exists because working rule 5 needs a fresh test set if a
fault is found on this one, and writing one later costs weeks.
Why not more: every question is checked by hand (about 18 hours for 550 at 2 minutes each). Why not
fewer: below a few hundred questions intervals widen and simple formulas for them stop holding.

**7. Drafted by models, written and checked by hand.**
What: seed sections are sampled per Act (70% at random for coverage, 30% from lists of the most
renumbered and most cited sections, for realism); a model drafts questions, gold sections, key facts
and a short gold answer from each seed; drafts come from two model families, half each
(Mistral Large 3 on NVIDIA's free endpoints, and gpt oss 120b on Groq; never Gemini, the judge's
family); Tanush writes at least a quarter of the questions himself, including every Hinglish one and
most layperson situations. A checking script shows each draft beside the full text of its gold
sections and their neighbours, and records accept, edit or reject against a checklist: answerable from
the text alone, gold sections complete, key facts exactly right, wording natural and not copied from
the section. A random 10% is checked again a week later; the agreement is reported, as the ceiling for
any judge.
Why: drafting makes 550 questions feasible; hand checking makes them right. Drafted questions borrow
the section's words and flatter BM25, so the share written by hand, the lexical overlap (the BM25
rank of each gold section) and every result by author (drafted by family A, by family B, by hand)
are reported. Why not draft with one model: a model may find its own phrasing easiest.
Why not only hand written questions: too slow for 550 with gold sections and key facts.

**8. Split by seed section, sealed, read once.**
What: no seed section gives questions to two sets (a mapping question's cluster is its BNS section,
with the IPC section it replaced). The test and reserve files are committed when checked, their
SHA256 written in this plan, and the loader refuses them unless a run is marked final; every final
read is appended to `docs/results/test_reads.md`. The test set is read once, in M5, for every frozen
system, and once more in M6 through the service, which chooses nothing.
Why: prompts, retrieval settings and agent logic are tuned by reading failures, which overfits fast
to whatever set is looked at; a read log makes "read once" checkable. Why not read the test set at
the end of each milestone, as DocLens did: DocLens's choices were mostly trained, these are mostly
hand tuned, and each read of 300 questions leaks more. So M1 to M4 report validation numbers and say
so; DocLens M4 showed validation flattering by 1.2 to 2.5 points, and M5 measures the gap again.

**9. Accurate, hallucinated and incomplete, adapted from Stanford's legal study.**
What: the metrics in "How results are scored"; citations parsed and checked in code (does the section
exist, was it in the context, does a quoted phrase occur in it), the rest judged (decision 10).
Why: legal answers fail in two ways, wrong and misgrounded (right, but citing a section that does not
say it), and the second is the more dangerous because it looks verified. Deterministic checks where
possible keep the judge's share small. Why not RAGAS scores alone: faithfulness measures agreement
with whatever was retrieved, not whether the law was stated right or the citation applies; RAGAS
style faithfulness is still reported in M3 as a diagnostic.

**10. A judge from another family, validated by hand labels, used where code cannot decide.**
What: code scores what it can: citations, abstention, and key facts it can match exactly (numbers,
and terms such as "cognizable" and "fine"). The judge, Gemini 3.5 Flash Lite on its free tier, at
temperature 0 and pinned by version, gets the rest in one call per answer that returns a verdict for
each check (is key fact k stated; does the answer contradict the gold answer; does section s support
the statement attached to it); about 40% of answers need it (estimate, measured in M1). Tanush labels
about 150 answers from M1's baselines, balanced between pass and fail where possible: 20% supply the
judge's examples, 40% tune its prompt, 40% measure it once. The judge is trusted when its true
positive and true negative rates both reach 0.90; it is measured again on 100 labels of M4's agent
answers, whose errors are subtler. If it still falls short after its prompt is revised, Mistral
Large 3 is the fallback, a free model with quota enough; it shares the development model's family,
so its rates are measured on fresh labels separately for Mistral's answers and for other families',
and it is used only if they agree.
Why: judges agree with people about as often as people agree with each other in the best studies, but
they favour longer answers and their own family's writing, and a judge's errors bias every rate it
produces; true positive and true negative rates are what correct that bias. Code first keeps the
judge's share small, and with it Gemini's 500 requests a day. Why not accuracy or Cohen's kappa
against the labels: with few failures, accuracy hides a lenient judge; kappa is for two human
labellers. Why not a judge from the development model's family as the first choice: self preference;
for the same reason no Google model (Gemini or Gemma) is a system under test.

**11. Intervals over seed sections, paired tests, repeated runs.**
What: 10,000 bootstrap resamples of seed sections with all their questions (as DocLens resampled page
designs); paired bootstrap differences with p values; every final system on the development model run
three times at temperature 0, its runs pooled per question and the spread between them reported (the
other Mistral model, Groq's and the local models once, for the judge's quota and the Mac's hours).
Three comparisons are declared before the test read: the agent against M3's best pipeline, M3's best
against the standard recipe, and the standard recipe against the same model from memory; all others
are exploratory.
Why: questions from one section share their difficulty, so treating them as independent makes
intervals too narrow (Anthropic's guide to error bars on evals); below a few hundred items, intervals
from central limit theorem formulas come out too narrow, so they come from resampling, as in DocLens;
and API answers can differ between runs even at temperature 0, which M1 measures. Why not a test
per pair of systems without declaring any: with a dozen systems, some difference will look
significant by chance.

**12. Baseline 1: models answering from memory.**
What: Mistral Small 4 and Large 3, gpt oss 120b and Qwen3.8 27B on Groq, and Qwen3.5 9B on the
Mac answer every validation question with citations, no retrieval, in the same output format as
Dhara.
Why: it is what most people do today, and it measures what the models already know, including how
often they cite the IPC for the BNS or invent sections. Why not skip it: without it, nothing says
what retrieval adds.

**13. Baseline 2: the standard RAG recipe, built as tutorials build it.**
What: LangChain's recursive character splitter at 1,000 characters with 200 of overlap over the PDF
text, LangChain's default Hugging Face embedder, the top 4 chunks (its default for similarity search,
checked against the installed version), one prompt that asks for citations; run with Mistral Small 4
and Large 3, and with Qwen3.5 9B on the Mac.
Why: "baselines first: measure the standard tool". This is the tool most RAG systems start as, and
its failure (chunks that cut sections apart and lose their numbers) is what M2 sets out to fix. Why
not a tuned baseline: then nothing would measure what the tuning bought.

**14. Free tiers only: NVIDIA to develop on, Gemini to judge, Groq and the Mac to compare.**
What: Tanush's choice, so nothing is paid. M1 compares Mistral Small 4 and Mistral Large 3, Mistral's
open weights served free on NVIDIA's API, from memory and in the standard recipe on validation, and
keeps the more accurate one that returns valid structured output nearly always, pinned by version for
the rest of the project. Gemini 3.5 Flash Lite judges (decision 10). The other of the two, and gpt oss
120b and Qwen3.8 27B on Groq, are the strongest free models compared; Qwen3.5 9B and 4B run through
Ollama in M1 (the benchmark, and the 9B in both baselines) and in M5 on the test set; the service can
use an API or the local model, but not NVIDIA's free endpoints, whose terms exclude production use.
Why: M3 to M6 need about 17,000 development requests and 51 million tokens (Appendix A), and only
NVIDIA's free endpoints (about 40 requests a minute, no daily cap published) hold that; Gemini's 500
requests a day suit the judge, whose calls code keeps few; Groq's 200,000 tokens a day hold about 200
questions from memory or 50 with retrieval, too little to develop on. On the Mac the agent takes about
2 minutes a question, so local models are measured, not developed on; they answer the privacy question
("can this run offline on a laptop, and how much worse is it"). This is the exception to "everything
runs on the Mac" that working rule 6 allows by decision: the generator runs remotely, every number is
still produced on the Mac. Free tiers see the prompts, and two may use them (NVIDIA's and Gemini's);
every prompt holds only public law text and Dhara's own questions, never personal data. NVIDIA may end
its free endpoints at any time; the cache keeps every answer already used, and other hosts serve the
same open weights.
Why not paid APIs: Tanush's choice; M5 states what the same runs would cost at list prices. Why not
Mistral's own API, as first planned: its Free mode no longer includes API access, and its consumer
terms limit the API to business customers, which an individual is not; NVIDIA serves the same
weights. Why not Mistral Medium, the first plan's second candidate: Mistral has deprecated its last
version, and the two compared are the Mistral weights NVIDIA serves. Why not Gemini to develop on: 500
requests a day would stretch M4 alone over about two weeks. Why not develop on the local model: weeks
of compute for each round of choices.

**15. Every model call through one client: cached, versioned, paced.**
What: `src/dhara/llm.py`, one client in the standard library over NVIDIA's and Groq's chat completions
endpoints, Gemini's own generateContent and Ollama's /api/chat. Every call is cached in SQLite
(`runs/llm.sqlite`) under a hash of provider, model, version, messages and settings, and stored with
its tokens (thinking included, as providers bill it), seconds, what it would cost at list prices, the
provider's whole answer and the counts of remaining requests it sent back. Each provider's free limits
(requests and tokens a minute and a day) are counted in the same database over rolling windows, so
runs on different days share one count; a call waits until every limit has room, and when the wait
would pass two minutes (a daily limit) the run stops, says when to run again, and resumes from the
cache then. A 429 or a server error is retried five times, waiting as long as the provider asks, or 2,
4, 8, 16 and 32 seconds; a refused request is not retried. A replay mode answers from the cache only
and fails on any call it has not seen. API keys come from the environment or a `.env` file that git
ignores. Each results file names the machine, the models with versions, the prompt hashes and the
corpus manifest.
Why: reruns cost nothing and give the same numbers; tokens per question are measured, not estimated;
free tiers answer 429 when a limit is crossed, and pacing turns that into a slower run instead of a
broken one; an API model can change or be retired, and the cache keeps the evidence. A rolling window
also stays under a limit that resets at midnight. A call's tokens are estimated from its characters
(one token for every three) only to pace it before it is sent; every count recorded is the provider's
own. Gemini is called through its own API: Google calls its OpenAI compatible endpoint beta and
advises calling the API directly without the OpenAI libraries, and its own answer reports thinking
tokens apart and the model version that answered.
Why not LangChain's model wrappers: one more layer between the code and the measured call. Why not the
providers' SDKs: four packages for what one module of standard library code does, and the tests
replace the network with a fake in one place (decision 22). Why not MLflow: there is no training; each
run's manifest and results file are enough.

**16. Ollama's context set explicitly, and checked.**
What: every local request sets `num_ctx` to fit its prompt and its reply; the client refuses a local
call without it, and fails one whose prompt, with the reply's maximum, reaches the window. Ollama does
not document what it does with a longer prompt, so the benchmark (decision 17) sends one and confirms
that the check catches it before any long run.
Why: on a Mac with under 24 GiB of GPU memory Ollama defaults to a 4,096 token context and drops the
excess silently; an agent prompt with eight sections exceeds it, and the model would quietly answer
from half its evidence. Why not raise the server default: a per request setting is visible in the
code and the results file.

**17. A benchmark before any long local run, on a quiet machine.**
What: `scripts/bench_llm.py` measures, for each local candidate, prompt and generation tokens per
second at the real prompt sizes (1,000 to 10,000 tokens), peak memory with the embedder and reranker
loaded, and whether Ollama uses its MLX engine or llama.cpp on this Mac; it also records the chip's
GPU cores (10 on the 15 inch M2 Air, as the estimates here assume). It runs, like every long or heavy
run (local models, indexing, benchmarks, load tests, Docker builds), only after Tanush's go ahead and
while nothing else heavy runs on the Mac, and its results file says so.
Why: DocLens's first CRNN run died of memory a benchmark would have shown; on a fanless Air long runs
can also slow with heat, so the benchmark runs long enough to show it. Ollama's MLX engine first
needed more than 32 GB, so which engine runs here must be measured. The Mac is shared with other
projects' work, and seconds and memory measured beside another heavy job describe both jobs.

**24. Every old to new pair labelled by what changed and by its shape.**
What: each correspondence row gets two labels. What changed: unchanged (the same text under a new
number, including an old section kept whole as a subsection or proviso), modified (wording, scope or
punishment changed), new (no old counterpart), or heading (a row that sums up the rows of its
subsections). Its shape, over whole sections: one to one, merged (a new section takes in several old
ones), split (an old section went to several new ones), or merged and split. A script reads what
changed from CAPT's own words, since its tables describe each change in a free text column and have no
column for its type: a comparison that says no more than "No change", that the old section became a
subsection with its heading dropped, or the note made once that "Code" becomes "Sanhita", means
unchanged; anything else means modified; "New" or a dash in the old column means new. The shape
follows from the sections the rows name. Old sections that no row names are listed in `m1_tables.md`:
each was dropped by the new Act (omitted) or went into a new section without CAPT naming it. A
comparison of the texts proposes which: it finds the new section holding the largest share of the old
section's runs of three words, each weighted by how rare it is across both Acts, so the formulas every
section repeats ("shall be punished with imprisonment") count for little; a share of 0.5 or more
proposes the move, less proposes omitted. Tanush confirms every one in `docs/checks/unnamed.csv`.
Tanush checks the labels on decision 5's sample of 50 rows and on every row a gold answer uses.
Answers about a change quote both sections and name both labels.
Why: "is BNS 318 the same as IPC 420" is answered by both labels: in CAPT's table IPC 420 became BNS
318(4) unchanged, inside a section that also takes in IPC 415, 417 and 418. Two labels rather than one
type, because a row can be modified and merged at once (BNS 2(8) takes in IPC 29 and 29A and adds
words), and one type would drop half of that. Reading CAPT's words keeps the hand work small. Why not
leave the labels to the model reading both texts: that is one of the things M4 measures, not something
to assume. Why not unchecked labels: they would leak into gold answers. Why weight the phrases:
unweighted, the shared formulas made IPC 309 (attempt to commit suicide) look like BNS 226, a
different offence; why not take the comparison's word: a threshold cannot tell a section that moved
from one that was replaced by a new offence in similar words (IPC 124A and BNS 152), which a reader
can.

**25. Which law applies: savings sections and notifications; a missing fact is asked for.**
What: "which law applies" questions are answered from the repeal and savings sections (BNS 358, BNSS
531, BSA 170) and the notifications that brought the three Acts into force, as India Code's footnote
to section 1 of each new Act records them: S.O. 850(E) for the BNS, leaving out section 106(2); S.O.
848(E) for the BNSS, leaving out its First Schedule's entry for that section; S.O. 849(E) for the BSA
(`m1_corpus.md`). The eGazette's own copies are a cross check when it can be reached. A third outcome
joins answering and declining: when the answer turns on a fact the question does not give (when the
offence happened, whether a case was pending), Dhara asks for it. Questions missing such a fact are
scored correct when Dhara asks for the fact; answer, ask and decline are reported against the gold
outcome.
Why: the Acts leave their start dates to the notifications, so without them "which law applies"
cannot be answered from the sources; and a guessed date is a confident wrong answer, the failure the
project is about. Asking is measurable: a question either names the missing fact or not. Why not
territorial extent, state amendments, or how courts read "pending": they are outside the central
text or are interpretation (courts have read BNSS 531's savings clause differently), so Dhara cites
the text and declines the rest (decision 2). Why not a dialogue: one turn keeps every question
scorable; the service returns the question, and the user asks again with the fact.

**28. Tooling: Python 3.13, ruff, mypy in strict mode, pytest, CI from the first commit.**
What: a `pyproject.toml` package in `src/dhara` as in DocLens, installed with pip into a virtual
environment; ruff (rules E, F, W, B, UP and I, lines up to 120 characters); mypy in strict mode on
`src/dhara`; pytest; CI (decision 22) running lint, types and tests through `scripts/ci_step.sh` on
every push from the first commit. Dependencies are added with the code that needs them.
Why: strict types are cheap to keep from the start and costly to add later, and they catch a wrong
shaped citation or judge verdict before a run does; CI from the first commit keeps "green after every
push" true from the start. Why not DocLens's default mypy settings: they let untyped functions pass
unchecked. Why not uv or Poetry: pip and setuptools as in DocLens, one toolchain across projects; the
service's dependencies are pinned in M6, as DocLens's were.

**29. The download: the standard library, retries, the Archive as a fallback, pinned hashes.**
What: `scripts/get_data.py` with Python's urllib; server errors, failed redirects, rate limits and
timeouts are retried four times with a doubling wait (5 to 40 seconds), a missing file (404) is not;
when India Code still fails, the same file is taken from the Internet Archive's capture of it, and the
manifest records which route each file came by; one failure does not stop the others; a file must be
a PDF and, once pinned, have its pinned SHA256.
Why: India Code is slow, and while this was built it answered the Mac with gateway timeouts (HTTP 504)
for hours while it answered other networks; the Archive returns the bytes India Code served, and a
later download from India Code (with `--force`) is compared with the pinned hash, a changed file being
reported rather than replaced from the Archive, so the route never changes the text. Pinning turns a
silent change of text into a stop. Why not another copy (a commentary site, a police website): those
are retyped or reformatted, not India Code's file. Why not requests or httpx: no dependency for a
handful of downloads. Why not one try: the corpus step would fail for reasons that pass on their own.

**30. The parser: the arrangement as the list of sections, the page's marks as the cuts.**
What: each PDF's arrangement of sections is read first and taken as the list of sections, with their
part, chapter and group (the headings such as "Of theft" that group sections inside a chapter); the
body is cut where those sections begin, in their order, and only at lines that look like a section
start: a bold number, a number followed by a heading and a dash, or a repeal note. The body ends at
the first schedule, or at the statement of objects and reasons printed after the BNS. Numbers India
Code prints with a hyphen before the letter I, so that they are not read as figures, are keyed without
it (171I, like 171A). Footnotes are what lies below the two inch rule at the foot of a page; their
markers are the small raised digits. The state amendments India Code prints after some IPC and
Evidence Act sections are cut out of the section and kept beside it. Group headings are centred and
inset from both margins, and are cut from the end of the section before them. A paragraph breaks where
the gap between lines is wider than the page's own line spacing allows; a line that opens with a
clause marker ("(a)", "Explanation", "Provided") breaks on a smaller gap or an indent, so subsections
and clauses stay apart while a cross reference broken over a line ("clause", then "(b) of section 3")
does not. Checks, in `m1_corpus.md`: every listed section is found in the body; the arrangement's
numbering has no gaps (every whole number up to the last, every single letter up to the last for a
number); the group headings cut from the body agree with the arrangement's; lines that looked like a
section start but were not used are listed (state insertions such as the IPC's 379A "Snatching", cross
references broken over a line); headings that differ from the arrangement are listed, and each one,
read against the file, is India Code's own: a slip in one of the two places ("miscarraige",
"Liablility"), a spelling ("organizing"), or an entry that also names a heading inside the section;
and two counts show how the paragraph breaks follow the page: how often a line that opens with a
clause marker starts a paragraph, and how often a line that opens in lower case does.
Why: the arrangement is India Code's own list of an Act's sections, so it is the authority on what
exists, and cutting only at lines that look like a start keeps a cross reference that breaks over a
line from becoming a section. Type sizes differ between files (the CrPC's text is 10 point, the IPC's
arrangement 9 point, the Evidence Act's footnotes 10 point), while the footnote rule is the same in
all six, and so is the way group headings are set. The numbering check exists because the first check
can agree with itself: a first version missed the sections India Code numbers with a hyphen (171I in
the IPC, 105I and 265I in the CrPC) in both the list and the body, and still reported every listed
section found. The group headings and the statement of objects were found the same way, by reading
what the first version produced: BNS 302 ended in "Of theft", and section 358 carried the statement of
objects. Why not cut at every numbered line: cross references and state insertions would become
sections. Why not keep state amendments in the text: Dhara answers on the central Acts (decision 2),
and a state's punishment read as central law is a wrong answer. Why not a single gap for every
paragraph: a section's own lines are too few to measure its spacing, and the gap alone joins clauses
set in small type to the line above. Why not a layout model or OCR: the PDFs carry their text, fonts
and positions, which pdfplumber reads exactly.

## Decisions planned for later milestones (settled by measurement there)

**18. Retrieval researched in process, served from PostgreSQL, checked equal.**
What: M2 runs exact search in process (embeddings as a NumPy matrix, BM25 with `bm25s`, fusion in
Python); M6 serves from PostgreSQL and measures that the service's top results match the reference
(overlap of the top 10, and recall of the approximate index against exact search).
Why: at a few thousand chunks exact search takes milliseconds, has no approximation error and keeps
experiments fast and repeatable; DocLens's lesson is to measure the serving path, as its ONNX graph
was checked against PyTorch. Why not build on the database from M2: Docker's memory would compete
with the models on 16 GB, and every experiment would wait on a server.

**19. PostgreSQL with pgvector and pg_textsearch for the service.**
What: one database holds sections, chunks, embeddings (pgvector, HNSW), a true BM25 index
(pg_textsearch), the mapping and schedule tables, the answer cache, rate limits and request traces.
Why: one system to run, back up and query with SQL joins (a hit's chapter, its old counterpart), the
kind of store backend interviews probe (indexes, joins, transactions), and both extensions under the
permissive PostgreSQL licence. Why not Qdrant (Apache 2.0, native hybrid search): a second store for
the same few thousand rows, plus PostgreSQL anyway for everything else. Why not Chroma or LanceDB
(Apache 2.0): good embedded stores, but they would sit beside PostgreSQL rather than replace it. Why
not Milvus (Apache 2.0) or Weaviate (BSD 3 clause core): built for scale this corpus does not have.
Why not ParadeDB for BM25: AGPL. A risk to check early in M6: a PostgreSQL image with both extensions
may need building.

**20. LangGraph for the agent.**
What: the agent as a LangGraph state graph (route, plan, act with tools, answer, verify, revise or
abstain), with loop and token limits, its state checkpointed, its steps streamed.
Why: the agent is a state machine with cycles (retrieve again, revise), which LangGraph models
directly; it is MIT licensed and stable since its 1.0 release; it is the framework AI engineer roles
ask about and the one on Tanush's list. Why not Pydantic AI (MIT): its strength is typed outputs and
provider portability, while cycles, checkpoints and streamed steps are LangGraph's core. Why not the
OpenAI Agents SDK, CrewAI or Microsoft's Agent Framework (all MIT): they centre on agent loops,
handoffs or roles, where Dhara needs explicit control flow it can ablate node by node. Why not a
plain Python loop: possible, and kept as the M3 pipeline the agent must beat; the graph earns its
place only if M4's ablations say so.

**21. FastAPI with streaming, Docker Compose, the model outside the containers.**
What: FastAPI with native Server Sent Events (since FastAPI 0.135) streams the agent's steps and the
answer; Compose runs the API and PostgreSQL; the model is an API, or Ollama running natively on the
Mac and reached from the containers. The service's port is one no other project uses, checked in
their README and plan files when M6 begins (DocLens's service uses 8000).
Why: SSE is one way, plain HTTP and enough for streaming text; Docker containers on a Mac get no
Apple GPU, so a model inside one would run on the CPU; other projects' services run on the same Mac.
Why not WebSockets: two way channels the service does not need.

**22. CI as in DocLens, with a fake model.**
What: GitHub Actions with DocLens's `scripts/ci_step.sh` and `scripts/ci_annotate.py`: lint, types
and tests; then the image built, Compose started with PostgreSQL, and an end to end check over HTTP. A
deterministic fake model replaces every LLM in CI, so no API keys are stored and runs are free.
Why: DocLens's CI failed for 13 pushes before anyone looked; annotations make failures readable
through the public API. Why not real models in CI: secrets in a public repository, costs on every
push, and answers that vary.

**23. MIT licence; data and models keep theirs.**
What: the code under MIT; the PDFs downloaded, not committed; questions and labels committed as
Dhara's own work; models under their own licences, listed in the README.
Why: as DocLens. Why not commit the PDFs: they are the government's to publish.

**26. The answer: plain words, quoted law, the Act's own Illustrations, limits and links.**
What: the structured answer (M3) holds a short answer in plain words; claims, each with Act, section
and subsection, a quote from it, and a line on why the section applies; the section's official
Illustrations where the Act gives them, quoted; what the Acts do not settle (case law, state
amendments); and, for each citation, links to the section's text in Dhara and to India Code's page for
it. Every plain words statement is a claim, checked like the others.
Why: about 40% of the questions are asked the way a layperson asks, so the answer must read plainly;
the Acts' Illustrations (BNS 318 has them) are worked examples that are law, not text a model made
up. Why not generated hypothetical examples: unverifiable text in an answer is the failure Dhara
exists to prevent, and each would need judging too. Why not free text answers: claims with quotes are
what the citation checks and the judge score.

**27. Corrective retrieval, CRAG style, inside the six Acts, measured as an ablation.**
What: a grading step after retrieval with CRAG's three outcomes: correct (answer from the sections
graded relevant, the rest dropped); incorrect (retrieve again inside the corpus: exact lookup of
referenced sections, a reworded query, the old to new mapping); ambiguous (add a second strategy's
sections, and decline if the evidence is still not enough). Two graders are compared: the reranker's
score with two thresholds set on validation (no model call, closest to CRAG's small trained
evaluator), and one model call that grades all retrieved sections together. Measured against M3's
best pipeline and the agent without it: retrieval recall, accuracy, citation F1, hallucination,
latency, calls and tokens. It stays in the service only if it earns its place; either way the result
is reported.
Why: when retrieval misses, the answer fails however good the generator; M3's oracle gap measures how
often that happens, and this step targets it. Why not CRAG's web search for incorrect retrievals:
Dhara answers only from the Acts, and web text is unverified. Why not CRAG's fine tuned T5 evaluator:
it needs training labels Dhara does not have, and the reranker is already a trained relevance model.

## The six milestones in detail

### M1 Baseline

In this order: the repository and CI (decision 28); the corpus, the notifications and their
checks (decisions 3 to 5, 24, 25, 29, 30); the validation questions, then the test
and reserve sets, sealed (decisions 6 to 8); the free accounts with their recorded limits, the model
client and the local benchmark (14 to 17); both baselines on validation (12, 13); Tanush's labels and
the judge's validation (10); the scores. Results: `m1_corpus.md`, `m1_tables.md`, `m1_questions.md`,
`m1_bench_llm.md`, `m1_judge.md`, `m1_baselines.md`.

### M2 Retrieval

No language model, so it is cheap and exact. Experiments: chunks (the recipe's 1,000 characters,
whole sections with an Act, chapter and heading header, clauses with their parent section, the header
on or off); BM25 (`bm25s`, with tokens that keep section numbers such as 304B); dense embedders (BGE
M3, MIT, dense and sparse in one model; Qwen3 Embedding 0.6B, Apache 2.0; one more chosen in M2);
fusion (reciprocal rank fusion, weighted fusion, BGE M3's sparse vectors); rerankers over the top 50
(BGE reranker v2 m3 and Qwen3 Reranker 0.6B, both Apache 2.0); a parser that sends explicit
references ("s. 498A IPC", "dhara 302") straight to the section. Every result by Act, type, author
and language, with seconds per query on the Mac's CPU and GPU. The optional held out check reads IL
TUR's case facts (CC BY NC SA 4.0, used for evaluation only, not redistributed) to see whether the
best retriever finds the cited IPC sections from real fact patterns. Results: `m2_retrieval.md`.

### M3 Answers

The answer generator returns structured JSON in decision 26's shape (a plain words answer; claims,
each with its citations, a short quote and why the section applies; the Act's own Illustrations;
limits), a question for a missing fact, or a refusal with its reason. Experiments: oracle sections
(the gold ones: what answering alone costs, as DocLens's true lines showed what reading alone cost),
M2's best retrieval, and the recipe's retrieval; 3, 5, 8 and 12 sections; order by score or by Act;
free text with citations against claims with quotes; an instruction to decline. Results:
`m3_answers.md`.

### M4 Agent

The graph: route (explicit references, language, scope; declines early what is out of scope), plan
(sub questions for questions that need two sections or both codes), act with tools (look up a section,
search, map old to new with both labels, classify an offence, check which law applies by date),
grade what retrieval found and correct it (decision 27), answer, verify (code checks every citation
and quote, then the model checks each claim against its cited section), revise once or decline.
Ablations remove each node and each tool and compare the two graders; budgets cap calls and tokens.
Reported: M1's metrics, calls, tokens and seconds per question (p50, p95), cost per 1,000 questions at
list prices, which tools were called and whether they were the right ones, and every failure sorted by
kind. Results: `m4_agent.md`.

### M5 Comparison

The test set, read once, for every frozen system: models from memory (the development model, the other
Mistral model, gpt oss 120b and Qwen3.8 27B on Groq, Qwen3.5 9B and 4B on the Mac); the standard
recipe on the development model; M3's best pipeline on the development model and both Qwen3.5 models;
the agent on those three and the other Mistral model. If a free host serves the same open weights as a
local model, 100 test questions read through both separate the model from its serving (DocLens's
PaddleOCR VL lesson); if none does, that is recorded as not measured. Reported with intervals and the
three declared paired comparisons, beside tokens per question, cost at list prices, latency, memory,
privacy and licence. Spread over days to fit the quotas: the judge about five days, Groq one or two
days per model, the 9B model's agent about ten hours, overnight. Results: `m5_compare.md`.

### M6 Ship

`POST /v1/ask` streams steps and the answer as Server Sent Events and ends with the citations, each a
link; `GET /v1/sections/{act}/{number}` returns a section's text; `GET /v1/map` returns old and new
counterparts; `GET /health`; `GET /` serves a plain HTML demo (ask, watch the steps, open every
citation). API keys, a rate limit per key, timeouts, retries and a fallback model, an answer cache
keyed by question, corpus version, prompt version and model, request traces in PostgreSQL. Measured:
the test set through the service (scores as in M5, within the run spread), retrieval agreement with
M2, latency p50, p95 and p99 and time to first token at 1, 4 and 16 concurrent users (Locust), errors,
peak memory. The load test drives the service with a stand in model that replays the latencies
recorded in M5, because free tiers cap requests a minute far below 16 users; the test set's run
through the service, one request at a time, reports what a user really waits on the free tier. Where a
public demo is hosted is decided here (TinyGPT's lesson: a free Hugging Face Space with a server was
refused); a demo on a free tier is bounded by that tier's quota and terms, and its page says which
provider sees the questions (Groq states it does not train on them). Results: `m6_service.md`.

## What interviews ask, and where Dhara answers it

AI engineer: why RAG and not fine tuning (M1: what models know from memory, and Acts change); how
chunk size was chosen (M2); BM25 against dense against hybrid, bi encoders against cross encoders, and
when a reranker pays for its latency (M2); how retrieval and generation are evaluated apart (M2, M3's
oracle); how you know the judge is right (decision 10); what hallucination is here and how it was cut
(decisions 9, M3, M4); when an agent beats a fixed workflow, and whether corrective retrieval pays
(M4's ablations, decision 27); how the system declines or asks (decision 25); cost and latency per
question, local against API (M5); prompt injection (M6).

SDE backend: the API and streaming design (M6); why PostgreSQL and not a vector database, HNSW
against exact search (decisions 18, 19); caching and invalidation by version (M6); rate limits,
timeouts, retries and fallbacks (M6); p95 under load and where the time goes (M6); tracing a request
(M6); testing without real models, and CI (decision 22); reproducibility from pinned data and cached
calls (decisions 3, 15).

## Repository layout

```
src/dhara/
  corpus.py       the Acts and the tables: where each file comes from, pinned
  parse.py        India Code PDFs into sections; footnotes apart
  tables.py       the BNSS First Schedule and the old to new correspondence
  refs.py         section references in questions ("s. 498A IPC", "dhara 302")
  chunking.py     the recipe's chunks, sections with headers, clauses with parents
  retrieval/      bm25, dense, fusion, rerank: exact and in process (M2)
  llm.py          one client: NVIDIA, Groq, Gemini and Ollama; cache, tokens, pacing under free limits
  answer.py       structured answers, citation and quote checks (M3)
  agent.py        the LangGraph agent and its tools (M4)
  judge.py        the judge's binary checks
  metrics.py      accurate, hallucinated, incomplete, citations, abstention, retrieval
  stats.py        bootstrap over seed sections, paired comparisons (from DocLens)
  store.py        PostgreSQL: pgvector, pg_textsearch, cache, traces (M6)
  service.py      FastAPI: /v1/ask, /v1/sections, /v1/map, /health, the demo page
  demo.html
eval/             questions (validation, test and reserve), labels, their SHA256
scripts/          get_data, parse_corpus, make_tables, draft_questions, check_questions, bench_llm,
                  eval_memory, eval_recipe, eval_retrieval, eval_answers, eval_agent,
                  label_answers, validate_judge, compare, bench_service, ci_step.sh, ci_annotate.py
tests/            unit tests, and end to end tests with the fake model
docs/             PLAN.md, results/, and checks/ (the sheets Tanush fills by hand)
Dockerfile, compose.yaml, .github/workflows/ci.yml, pyproject.toml, LICENSE
data/, runs/      downloads, caches and outputs, never committed
.env.example      the API keys Dhara reads; the real .env is never committed
```

Python 3.13, a virtual environment and `pip install -e ".[extras]"` as in DocLens, ruff and mypy.

## Risks, and how each is caught

* **The PDFs parse wrong** (footnotes, lettered or omitted sections, tables): section lists checked
  against each arrangement of sections, a hand sample against India Code's section pages (decision 4).
* **The repealed Acts' PDFs** may sit under state handles on India Code; M1 finds the central copies
  or the same text on another government site, pinned by SHA256.
* **Drafted questions flatter some systems:** hand written share, two drafting families, lexical
  overlap and results by author reported (decision 7).
* **The judge is wrong:** validated twice, code checks first (decisions 9, 10).
* **API models change or retire:** pinned versions, the cache, a local model as a stable reference.
* **Test questions reach providers that may use them** (NVIDIA's free endpoints, Gemini's free
  tier): the models measured are versions pinned before the questions were written, so they cannot
  have learned them; results name the versions, and a later version is compared only on fresh
  questions.
* **Free tiers change or vanish** (Mistral closed its API to individuals, Cerebras ended its free
  tier, GitHub Models was retired): the cache keeps every answer already used, three providers and
  the Mac back each other up, other hosts serve the same open weights, and M1 records the limits each
  account really has.
* **The Mac's limits:** 16 GB, a fanless Air that slows with heat, Ollama's silent truncation
  (decisions 16, 17).
* **Hand work:** about 18 hours for the questions and 6 for the judge's labels; the checking script
  shows everything needed on one screen.

## Decided by Tanush

1. The name: Dhara.
2. Free tiers only: nothing is paid (decision 14).
3. 550 hand checked questions: validation 150, test 300, reserve 100 (decision 6).
4. The six criminal law Acts (decision 1).
5. After review: the change labels, which law applies with asking, the answer's shape and corrective
   retrieval (decisions 24 to 27).
6. When Mistral closed its API to individuals: develop on NVIDIA's free endpoints, with the same
   Mistral weights (decision 14).

## Before M1's baselines run

* Three free accounts: the NVIDIA Developer Program, for an API key from build.nvidia.com (its trial
  terms let NVIDIA use prompts to improve its products), Google AI Studio for a Gemini API key (free
  tier prompts may be used to improve Google's products), and Groq (states it does not train on API
  data). Each key goes in `.env`, copied from `.env.example`. Every prompt holds only public law text
  and Dhara's own questions.
* Each account's real limits recorded in M1: build.nvidia.com shows NVIDIA's rate limit, Google AI
  Studio shows Gemini's, and Groq sends its own count of what is left with every answer, which the
  client stores.

## Appendix A: the arithmetic behind the estimates

Tokens per request, in plus out (assumed; M1 measures them): from memory 1,000; the standard recipe
1,900 (four chunks); plain RAG 3,950 (eight sections); an agent call 3,000, at 3.3 calls a question;
a judge call 2,750.

Answers over the project: M1, five models from memory and three in the recipe on 150 validation
questions; M3, 12 settings; M4, 15 settings and ablations, and corrective retrieval with each of its
two graders (the model grader adds about one call a question); M5, the test set for every system
listed there, each system on the development model three times; M6, the test set once more through the
service: about 12,500 answers. If code scores 60% of them alone (estimate), the judge makes about
5,000 calls, and about 600 more while its prompt is tuned and validated: 5,600 calls, 15.5 million
tokens, 11 days of Gemini's 500 requests a day. Drafting: about 600 drafts, half per family, two a
call at 3,700 tokens. The development model in M3 to M6: about 17,000 requests and 51 million tokens;
all models on NVIDIA's free endpoints together about 19,000 requests, 8 hours at 40 requests a minute,
one call at a time. Groq: gpt oss 120b 600 requests and 1.0 million tokens with its drafts, 5 days at
200,000 tokens a day; Qwen3.8 27B 450 requests and 0.45 million tokens, 2.2 days. On the Mac (the 15
inch M2 Air has 10 GPU cores; estimate): the 300 test questions take the 9B model 1.9 hours from
memory, 3.9 with retrieval and 9.8 as the agent (15.5 in all), and the 4B model 0.8, 1.7 and 4.3 (6.9
in all).

Local speed: llama.cpp on the M2 with a 7B model at 4 bits processes 146 (8 GPU cores) to 180 (10
cores) prompt tokens a second and generates about 22 tokens a second; scaled by 7/9 for a 9B model
and 7/4 for a 4B model, seconds per question are tokens in / prompt speed + tokens out / generation
speed, with 700, 3,600 and 9,000 tokens in and 300, 350 and 900 out from memory, with retrieval and
as the agent.

Interval half widths, 1.96 × √(p(1 − p)/n): at n = 300, 5.7 points at p = 0.5 and 5.2 at 0.7; at
n = 150, 7.3 at 0.7; at n = 200, 6.4 at 0.7. Smallest paired difference detected at α = 0.05 with
80% power (McNemar's approximation): at n = 300, 5.1, 6.2 and 8.1 points when 10%, 15% and 25% of
questions differ between the two systems.

## Sources

Data and law:
* India Code, the BNS (PDF): <https://www.indiacode.nic.in/bitstream/123456789/20062/1/a202345.pdf>
* India Code, disclaimer: <https://www.indiacode.nic.in/indiacode/disclaimer.jsp?abv=null>
* PRS India, are laws covered by copyright: <https://prsindia.org/theprsblog/are-laws-covered-by-copyright>
* Copyright Act s. 52(1)(q) text: <https://future.indiankanoon.org/doc/648494>
* Correspondence tables and comparison summaries, CAPT Bhopal: BNS to IPC
  <https://www.keralaprisons.gov.in/userfiles/act-and-rules/comparison_summary_BNS_to_IPC.pdf>, BNSS to
  CrPC <https://keralaprisons.gov.in/userfiles/act-and-rules/comparison_summary_BNSS_to_CrPC.pdf>, BSA
  to IEA <https://keralaprisons.gov.in/userfiles/act-and-rules/comparison_summary_BSA_to_IEA.pdf>
* Allahabad High Court comparative charts: <https://allahabadhighcourt.in/ILR/newlaw24_vol1.pdf>, <https://allahabadhighcourt.in/ILR/newlaw24_vol2.pdf>
* Section counts: BNSS 531 and BSA 170 <https://www.toprankers.com/president-grants-approval-to-three-bills-replacing-outdated-british-era-criminal-laws>
* State amendments: <https://prsindia.org/files/bills_acts/bills_states/tamil-nadu/2025/Bill2of2025TN.pdf>
* IL TUR (licence CC BY NC SA 4.0): <https://huggingface.co/datasets/Exploration-Lab/IL-TUR>

Free tiers:
* Gemini free tier limits (a summary of AI Studio's figures): <https://www.scriptbyai.com/gemini-api-free-tier-limits/>; rate limits: <https://ai.google.dev/gemini-api/docs/rate-limits>
* Groq free plan limits, and the counts it sends back: <https://console.groq.com/docs/rate-limits>; Groq's data terms: <https://standardcompute.com/providers/groq>
* NVIDIA's free endpoints, for research, development and testing: <https://forums.developer.nvidia.com/t/nvidia-nim-faq/300317>; limits set per account and shown on build.nvidia.com: <https://forums.developer.nvidia.com/t/request-more-4-000-credits-option-on-build-nvidia-com/344567>; about 40 requests a minute: <https://forums.developer.nvidia.com/t/is-nim-free/369368>; trial terms on prompts: <https://forums.developer.nvidia.com/t/api-trial/385386>
* Mistral's Free mode without API access: <https://docs.mistral.ai/admin/billing-usage/usage-limits>; its consumer terms, the API for business customers only: <https://legal.mistral.ai/terms/row-consumer-terms>; Mistral Medium 3.5 deprecated: <https://docs.mistral.ai/models.md>
* Cerebras ends its free tier: <https://claudelog.com/faqs/is-cerebras-free/>; GitHub Models retired: <https://fast.io/resources/github-models-rate-limit/>; OpenRouter's free limits: <https://blogs.novita.ai/free-llm-api-comparison-2026/>

Models, list prices and speed:
* Mistral Small 4 on NVIDIA's API: <https://docs.api.nvidia.com/nim/reference/mistralai-mistral-small-4-119b-2603-infer>; Mistral Large 3, a free endpoint there: <https://build.nvidia.com/mistralai/mistral-large-3-675b-instruct-2512>
* Mistral prices: <https://docs.mistral.ai/inference/pricing>; Mistral Large 3's, from Mistral's price page as captured: <https://www.usagepricing.com/blueprint/activity/mistral-ai-2026-10-22-large-4-sale-ends>
* Groq prices: <https://www.groq.com/pricing>; per model, from GroqCloud's documentation: <https://www.morphllm.com/groq-pricing>
* Gemini prices: <https://ai.google.dev/gemini-api/docs/pricing>; Gemini 3.5 Flash Lite's: <https://www.developersdigest.tech/models/gemini-3-5-flash-lite>
* Gemini's own API: structured output <https://ai.google.dev/gemini-api/docs/structured-output>, thinking levels <https://ai.google.dev/gemini-api/docs/generate-content/thinking>; its OpenAI compatible endpoint, in beta: <https://ai.google.dev/gemini-api/docs/openai>
* Groq's chat completions API: <https://console.groq.com/docs/api-reference>; Ollama's API: <https://docs.ollama.com/openapi.yaml>
* llama.cpp on Apple silicon: <https://github.com/ggml-org/llama.cpp/discussions/4167>
* The 15 inch M2 MacBook Air (10 GPU cores in every configuration): <https://www.notebookcheck.net/First-ever-15-inch-Apple-MacBook-Air-powered-by-M2-launched-configurations-start-from-US-1-299.723979.0.html>
* Ollama's MLX engine: <https://ollama.com/blog/mlx>; context defaults: <https://fast.io/resources/ollama-context-length/>
* Qwen3.5 small models: <https://artificialanalysis.ai/articles/qwen3-5-small-models>
* BGE M3 <https://huggingface.co/BAAI/bge-m3>, BGE reranker v2 m3 <https://huggingface.co/BAAI/bge-reranker-v2-m3>, Qwen3 Reranker <https://huggingface.co/Qwen/Qwen3-Reranker-0.6B>

Retrieval, agents and serving:
* pg_textsearch: <https://www.postgresql.org/about/news/pg_textsearch-v10-3264>; pgvector: <https://www.postgresql.org/about/news/pgvector-080-released-2952/>
* Qdrant hybrid search: <https://qdrant.tech/documentation/search-tuning/hybrid-search/>
* Vector database licences: <https://resources.rework.com/tools/ai-data-infra/best-chroma-alternatives>
* bm25s: <https://github.com/xhluca/bm25s>
* LangGraph and Pydantic AI versions and licences: <https://www.developersdigest.tech/agent-frameworks/compare/pydantic-ai-vs-langgraph>
* FastAPI Server Sent Events: <https://fastapi.tiangolo.com/ko/tutorial/server-sent-events/>
* Docker and Ollama on a Mac: <https://www.infoq.com/news/2025/04/docker-model-runner>

Evaluation:
* Stanford, Hallucination Free? (legal research tools): <https://arxiv.org/pdf/2405.20362>
* LegalBench RAG: <https://arxiv.org/abs/2408.10343>
* ALCE, citation recall and precision: <https://arxiv.org/abs/2305.14627>
* AbstentionBench: <https://arxiv.org/abs/2506.09038>
* Judging LLM as a judge: <https://arxiv.org/abs/2306.05685>
* Validating a judge with true positive and true negative rates: <https://skills.sh/hamelsmu/evals-skills/validate-evaluator>
* Adding error bars to evals (Anthropic): <https://arxiv.org/abs/2411.00640>; small samples: <https://arxiv.org/abs/2503.01747>
* RAGAS faithfulness: <https://docs.ragas.io/en/v0.2.0/concepts/metrics/available_metrics/faithfulness/>

Transition and corrective retrieval:
* CRAG, Corrective Retrieval Augmented Generation: <https://arxiv.org/abs/2401.15884>
* The BNS commencement notification, S.O. 850(E), leaving out section 106(2): <https://taxmanagementindia.com/visitor/detail_notification.asp?ID=141616>
* BSA section 170, repeal and savings: <https://future.indiankanoon.org/doc/10673658/>
* BNSS section 531(2)(a), pending matters: <https://www.scconline.com/blog/?p=329232>; read differently by courts: <https://amsshardul.com/?p=15622>

Interviews:
* <https://pub.towardsai.net/senior-ai-interviews-dont-test-what-you-know-they-test-what-breaks-at-2am-2b949558fe6d>
* <https://prachub.com/concepts/retrieval-augmented-generation-systems>
* <https://prachub.com/concepts/llm-chat-applications-rag-and-ml-evaluation>
