#!/usr/bin/env python3
"""
02_process_go_cc.py
───────────────────
Parses the GOA human GAF file and extracts experimentally validated
Cellular Component (GO:CC) annotations only.

Evidence codes kept (experimentally validated — no predicted):
  EXP  Inferred from Experiment
  IDA  Inferred from Direct Assay
  IMP  Inferred from Mutant Phenotype
  IGI  Inferred from Genetic Interaction
  IEP  Inferred from Expression Pattern
  HDA  High-throughput Direct Assay
  HMP  High-throughput Mutant Phenotype

Input:   data/raw/goa_human.gaf
Output:  data/processed/go_cc_filtered.csv

Columns: uniprot | gene | go_id | evidence

Run from project root:
  python scripts/02_process_go_cc.py
"""

from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────
RAW_GAF   = Path("data/raw/goa_human.gaf")
OUT_DIR   = Path("data/processed")
OUT_CSV   = OUT_DIR / "go_cc_filtered.csv"

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Filter criteria ────────────────────────────────────────────
# Experimentally validated evidence codes only — no IEA (electronic)
VALID_EVIDENCE: set[str] = {"EXP", "IDA", "IMP", "IGI", "IEP", "HDA", "HMP"}

# GAF aspect column: C = Cellular Component, F = Molecular Function, P = Biological Process
TARGET_ASPECT = "C"

# ── GAF column indices (0-indexed, tab-separated) ─────────────
# Full spec: http://geneontology.org/docs/go-annotation-file-gaf-format-2.2/
COL_DB_OBJECT_ID  = 1   # UniProt accession
COL_DB_OBJECT_SYM = 2   # Gene symbol
COL_GO_ID         = 4   # GO term ID  e.g. GO:0005634
COL_EVIDENCE      = 6   # Evidence code
COL_ASPECT        = 8   # C / F / P

# ── Parse ─────────────────────────────────────────────────────
if not RAW_GAF.exists():
    raise FileNotFoundError(
        f"Missing {RAW_GAF}. Run scripts/01_download_data.py first."
    )

print(f"Parsing {RAW_GAF} …")

rows: list[dict] = []
skipped_header = 0
skipped_aspect = 0
skipped_evidence = 0
kept = 0

with RAW_GAF.open() as fh:
    for line in fh:
        # GAF header lines start with '!'
        if line.startswith("!"):
            skipped_header += 1
            continue

        cols = line.rstrip("\n").split("\t")
        if len(cols) < 9:
            continue

        aspect   = cols[COL_ASPECT]
        evidence = cols[COL_EVIDENCE]

        if aspect != TARGET_ASPECT:
            skipped_aspect += 1
            continue

        if evidence not in VALID_EVIDENCE:
            skipped_evidence += 1
            continue

        rows.append({
            "uniprot":  cols[COL_DB_OBJECT_ID],
            "gene":     cols[COL_DB_OBJECT_SYM],
            "go_id":    cols[COL_GO_ID],
            "evidence": evidence,
        })
        kept += 1

# ── Deduplicate + save ────────────────────────────────────────
df = pd.DataFrame(rows).drop_duplicates()

print(f"\nParsing summary:")
print(f"  Header/comment lines skipped : {skipped_header:>10,}")
print(f"  Non-CC aspect skipped        : {skipped_aspect:>10,}")
print(f"  Non-experimental skipped     : {skipped_evidence:>10,}")
print(f"  Rows kept (before dedup)     : {kept:>10,}")
print(f"  Rows after drop_duplicates   : {len(df):>10,}")
print(f"  Unique UniProt accessions    : {df['uniprot'].nunique():>10,}")
print(f"  Unique GO terms              : {df['go_id'].nunique():>10,}")

print(f"\nEvidence breakdown:")
print(df["evidence"].value_counts().to_string())

df.to_csv(OUT_CSV, index=False)
print(f"\n✓ Saved → {OUT_CSV} ({OUT_CSV.stat().st_size / 1_048_576:.2f} MB)")
print("Next step: python scripts/03_process_hpa.py")
