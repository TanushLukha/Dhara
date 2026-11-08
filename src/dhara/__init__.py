"""Dhara: answers questions about India's criminal law Acts and cites the sections it relies on."""

from pathlib import Path

__version__ = "0.1.0"

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"  # downloads, never committed
RUNS = REPO / "runs"  # caches and outputs, never committed
