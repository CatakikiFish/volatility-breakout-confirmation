#!/usr/bin/env python3
"""Verify every file listed in the public repository manifest."""
import csv
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with (root / "MANIFEST.csv").open(encoding="utf-8-sig", newline="") as handle:
    rows = list(csv.DictReader(handle))
for row in rows:
    path = root / row["path"]
    data = path.read_bytes()
    assert len(data) == int(row["bytes"]), row["path"]
    assert hashlib.sha256(data).hexdigest() == row["sha256"], row["path"]
print(f"Verified {len(rows)} files.")
