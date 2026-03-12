#!/usr/bin/env python3
"""
validate_data.py
────────────────
Checks that the processed data files are ready for fine-tuning.

Validates:
  1. Files exist and are non-empty
  2. HPA — location + tissue coverage
  3. GO-CC — evidence quality, GO term coverage
  4. Cross-dataset gene overlap (join health)
  5. QA pair viability estimate

Run from project root:
  uv run scripts/validate_data.py
  python scripts/validate_data.py
"""

import ast
import sys
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────
HPA_CSV   = Path("data/processed/hpa_merged.csv")
GOCC_CSV  = Path("data/processed/go_cc_filtered.csv")

PASS = "  \033[32m✓\033[0m"
FAIL = "  \033[31m✗\033[0m"
WARN = "  \033[33m⚠\033[0m"
HEAD = "\033[1;36m"
RST  = "\033[0m"

issues: list[str] = []

def section(title: str) -> None:
    print(f"\n{HEAD}{'─'*55}{RST}")
    print(f"{HEAD} {title}{RST}")
    print(f"{HEAD}{'─'*55}{RST}")

def ok(msg: str) -> None:    print(f"{PASS} {msg}")
def bad(msg: str) -> None:   print(f"{FAIL} {msg}"); issues.append(msg)
def warn(msg: str) -> None:  print(f"{WARN} {msg}")
def info(msg: str) -> None:  print(f"     {msg}")


# ══════════════════════════════════════════════════════════════
# 1. File existence
# ══════════════════════════════════════════════════════════════
section("1 · File existence")

for p in [HPA_CSV, GOCC_CSV]:
    if p.exists() and p.stat().st_size > 1_000:
        ok(f"{p.name}  ({p.stat().st_size / 1_048_576:.2f} MB)")
    else:
        bad(f"{p.name} missing or empty — run pipeline scripts first")
        sys.exit(1)


# ══════════════════════════════════════════════════════════════
# 2. HPA — location + tissue coverage
# ══════════════════════════════════════════════════════════════
section("2 · HPA: subcellular location quality")

hpa = pd.read_csv(HPA_CSV)
total = len(hpa)
info(f"Total rows : {total:,}")
info(f"Columns    : {list(hpa.columns)}")

# Location completeness
no_loc = hpa["all_locations"].isna() | hpa["all_locations"].isin(["", ";"])
pct_loc = (1 - no_loc.sum() / total) * 100
if pct_loc >= 95:
    ok(f"Location populated : {pct_loc:.1f}% of rows")
elif pct_loc >= 80:
    warn(f"Location populated : {pct_loc:.1f}% of rows (some gaps)")
else:
    bad(f"Location populated : {pct_loc:.1f}% — too many missing locations")

# Reliability check — should only be Enhanced / Supported
valid_rel = {"Enhanced", "Supported"}
bad_rel = hpa[~hpa["reliability"].isin(valid_rel)]
if len(bad_rel) == 0:
    ok(f"Reliability filter : all rows are Enhanced or Supported")
else:
    bad(f"Reliability leak   : {len(bad_rel)} rows with unexpected values: {bad_rel['reliability'].unique()}")

# Reliability breakdown
rel_counts = hpa["reliability"].value_counts()
info("Reliability breakdown:")
for tier, n in rel_counts.items():
    info(f"  {tier:<12} {n:>5,}  ({n/total*100:.1f}%)")

# Tissue coverage
def parse_tissues(val) -> list:
    if pd.isna(val):
        return []
    try:
        result = ast.literal_eval(val)
        return result if isinstance(result, list) else []
    except Exception:
        return []

hpa["_tissues"] = hpa["expressed_tissues"].apply(parse_tissues)
has_tissue = hpa["_tissues"].apply(lambda x: len(x) > 0)
tissue_pct = has_tissue.sum() / total * 100

if tissue_pct >= 70:
    ok(f"Tissue data present: {has_tissue.sum():,}/{total:,} proteins ({tissue_pct:.1f}%)")
else:
    warn(f"Tissue data present: {has_tissue.sum():,}/{total:,} proteins ({tissue_pct:.1f}%) — lower than expected")

# Tissue count distribution
tissue_counts = hpa["_tissues"].apply(len)
info(f"Avg tissues/protein: {tissue_counts.mean():.1f}  (max {tissue_counts.max()})")

# Common locations
info("\nTop 10 main locations:")
top_loc = hpa["main_location"].value_counts().head(10)
for loc, n in top_loc.items():
    info(f"  {loc:<35} {n:>4,}")


# ══════════════════════════════════════════════════════════════
# 3. GO-CC — evidence quality + term coverage
# ══════════════════════════════════════════════════════════════
section("3 · GO-CC: annotation quality")

gocc = pd.read_csv(GOCC_CSV)
g_total = len(gocc)
info(f"Total annotations : {g_total:,}")
info(f"Unique proteins   : {gocc['uniprot'].nunique():,}")
info(f"Unique GO terms   : {gocc['go_id'].nunique():,}")

VALID_EVIDENCE = {"EXP", "IDA", "IMP", "IGI", "IEP", "HDA", "HMP"}
bad_ev = gocc[~gocc["evidence"].isin(VALID_EVIDENCE)]
if len(bad_ev) == 0:
    ok(f"Evidence codes     : all {g_total:,} annotations are experimentally validated")
else:
    bad(f"Evidence leak      : {len(bad_ev)} rows with electronic/predicted evidence")

info("\nEvidence breakdown:")
ev_counts = gocc["evidence"].value_counts()
for ev, n in ev_counts.items():
    info(f"  {ev:<6} {n:>6,}  ({n/g_total*100:.1f}%)")

# Missing gene symbols (used for cross-join with HPA)
no_gene = gocc["gene"].isna() | (gocc["gene"] == "")
if no_gene.sum() == 0:
    ok(f"Gene symbols       : all {g_total:,} rows have gene symbol")
else:
    warn(f"Gene symbols       : {no_gene.sum()} rows missing gene symbol")


# ══════════════════════════════════════════════════════════════
# 4. Cross-dataset gene overlap
# ══════════════════════════════════════════════════════════════
section("4 · Cross-dataset join health")

hpa_genes  = set(hpa["gene"].dropna().str.upper())
gocc_genes = set(gocc["gene"].dropna().str.upper())

overlap = hpa_genes & gocc_genes
hpa_only = hpa_genes - gocc_genes
gocc_only = gocc_genes - hpa_genes

info(f"HPA proteins              : {len(hpa_genes):,}")
info(f"GO-CC proteins            : {len(gocc_genes):,}")
info(f"Overlap (in both)         : {len(overlap):,}")
info(f"HPA only (no GO-CC term)  : {len(hpa_only):,}")
info(f"GO-CC only (no HPA data)  : {len(gocc_only):,}")

overlap_pct = len(overlap) / len(hpa_genes) * 100
if overlap_pct >= 50:
    ok(f"Join coverage      : {overlap_pct:.1f}% of HPA proteins have GO-CC annotations")
else:
    warn(f"Join coverage      : {overlap_pct:.1f}% — lower than expected, enrichment will be limited")


# ══════════════════════════════════════════════════════════════
# 5. QA pair viability estimate
# ══════════════════════════════════════════════════════════════
section("5 · QA pair viability estimate")

# Proteins viable for training:
# - must have a non-empty location
# - ideally have tissue data too
viable = hpa[~no_loc & has_tissue]
viable_any = hpa[~no_loc]   # location only (minimum bar)

info(f"Proteins with location only     : {len(viable_any):,}")
info(f"Proteins with location + tissue : {len(viable):,}")

# 3 QA templates × 2 samples per protein (the strategy in script 04)
qa_est_min = len(viable_any) * 2
qa_est_max = len(viable) * 3
info(f"Estimated QA pairs (min / max)  : {qa_est_min:,} / {qa_est_max:,}")

TARGET_QA = 6_000
if qa_est_max >= TARGET_QA:
    ok(f"QA pair target     : {TARGET_QA:,} pairs achievable ✓")
elif qa_est_min >= TARGET_QA:
    warn(f"QA pair target     : {TARGET_QA:,} pairs achievable only with max templates")
else:
    bad(f"QA pair target     : {TARGET_QA:,} pairs NOT achievable — only ~{qa_est_max:,} estimated")
    warn("Consider lowering quality filters or adding UniProt data in script 04")

# Training split feasibility
info(f"\nFine-tuning split feasibility (target 5k/0.5k/0.5k):")
for split, need in [("train", 5000), ("val", 500), ("test", 500)]:
    status = "✓" if qa_est_max >= need else "✗"
    info(f"  {split:<6} {need:>5,}  {status}")


# ══════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════
section("Summary")

if not issues:
    print(f"\n{PASS} All checks passed — data is ready for script 04 (QA generation)")
    print(f"     Run: uv run scripts/04_generate_qa_pairs.py")
else:
    print(f"\n{FAIL} {len(issues)} issue(s) found:")
    for i, issue in enumerate(issues, 1):
        print(f"     {i}. {issue}")
    sys.exit(1)
