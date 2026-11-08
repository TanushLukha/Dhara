# Dhara

Dhara (धारा, "section" in Hindi) answers questions about India's criminal law Acts, the BNS, BNSS and
BSA and the IPC, CrPC and Evidence Act they replaced, and cites the sections it relies on. It is built
in six measured milestones, each compared with what people use today: a large language model
answering from memory, and the standard RAG recipe.

Status: M1 (baselines) has started. Results will lead this README as they are measured. The plan,
with every decision and why, is in [docs/PLAN.md](docs/PLAN.md).

Nothing here is legal advice: Dhara reports what the text of the Acts says.

## Setup on the Mac

```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check . && mypy && pytest -q
```

## Licence

The code is MIT licensed (see `LICENSE`). The Acts are the Government of India's; they are downloaded
from India Code by a script and never committed.
