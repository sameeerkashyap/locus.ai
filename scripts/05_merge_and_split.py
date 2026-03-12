#!/usr/bin/env python3
"""
05_merge_and_split.py
─────────────────────
Reads the generated Q&A pairs, caps at 6,000, shuffles deterministically,
and writes the final train / val / test splits.

Input:   data/processed/training_pairs.jsonl
Output:  data/splits/train.jsonl   (5,000 pairs)
         data/splits/val.jsonl     (500 pairs)
         data/splits/test.jsonl    (500 pairs)

Run from project root:
  uv run scripts/05_merge_and_split.py
"""

import json
import random
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────
IN_JSONL   = Path("data/processed/training_pairs.jsonl")
SPLITS_DIR = Path("data/splits")
SPLITS_DIR.mkdir(parents=True, exist_ok=True)

N_TOTAL = 6_000
N_TRAIN =  5_000
N_VAL   =    500
N_TEST  =    500

assert N_TRAIN + N_VAL + N_TEST == N_TOTAL

# ── Load ──────────────────────────────────────────────────────
if not IN_JSONL.exists():
    raise FileNotFoundError(
        f"Missing {IN_JSONL}. Run scripts/04_generate_qa_pairs.py first."
    )

print(f"Loading {IN_JSONL} …")
with open(IN_JSONL) as f:
    pairs = [json.loads(line) for line in f if line.strip()]

print(f"  Total pairs available : {len(pairs):,}")

# ── Deduplicate on instruction text ───────────────────────────
seen: set[str] = set()
deduped: list[dict] = []
for p in pairs:
    key = p["instruction"].strip().lower()
    if key not in seen:
        seen.add(key)
        deduped.append(p)

print(f"  After dedup           : {len(deduped):,}")

# ── Shuffle + cap ─────────────────────────────────────────────
random.seed(42)
random.shuffle(deduped)

if len(deduped) < N_TOTAL:
    print(f"  ⚠  Only {len(deduped):,} unique pairs — using all (target was {N_TOTAL:,})")
    # Rescale splits proportionally
    n = len(deduped)
    N_TRAIN = int(n * 5/6)
    N_VAL   = int(n * 0.5/6)
    N_TEST  = n - N_TRAIN - N_VAL
    print(f"     Rescaled splits: train={N_TRAIN} / val={N_VAL} / test={N_TEST}")
else:
    deduped = deduped[:N_TOTAL]
    print(f"  Capped at            : {N_TOTAL:,}")

# ── Split ─────────────────────────────────────────────────────
train = deduped[:N_TRAIN]
val   = deduped[N_TRAIN:N_TRAIN + N_VAL]
test  = deduped[N_TRAIN + N_VAL:N_TRAIN + N_VAL + N_TEST]

# ── Write ─────────────────────────────────────────────────────
splits = {
    SPLITS_DIR / "train.jsonl": train,
    SPLITS_DIR / "val.jsonl":   val,
    SPLITS_DIR / "test.jsonl":  test,
}

for path, split in splits.items():
    with open(path, "w") as f:
        for pair in split:
            f.write(json.dumps(pair) + "\n")
    size_kb = path.stat().st_size / 1024
    print(f"  ✓ {path.name:<15} {len(split):>5,} pairs  ({size_kb:.0f} KB)")

# ── Sanity check: instruction type balance ────────────────────
print("\nInstruction type distribution in train split:")
type_counts: dict[str, int] = {}
for p in train:
    q = p["instruction"]
    if "located" in q:
        key = "location"
    elif "tissues" in q:
        key = "tissue"
    elif "disease" in q or "condition" in q:
        key = "disease"
    elif "compartments" in q:
        key = "go_compartment"
    else:
        key = "other"
    type_counts[key] = type_counts.get(key, 0) + 1

for qtype, n in sorted(type_counts.items(), key=lambda x: -x[1]):
    bar = "█" * (n // 80)
    print(f"  {qtype:<16} {n:>5,}  {bar}")

print(f"\n✓ Splits written to {SPLITS_DIR}/")
print("Next step: uv run scripts/06_baseline_eval.py   (requires GPU)")
