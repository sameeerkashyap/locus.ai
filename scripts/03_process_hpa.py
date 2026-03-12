#!/usr/bin/env python3
"""
03_process_hpa.py
─────────────────
Processes two Human Protein Atlas (HPA) TSV files:
  1. subcellular_location.tsv  → per-protein validated subcellular locations
  2. normal_tissue.tsv         → per-protein tissue expression levels

Filters applied:
  - Subcellular: Reliability ∈ {Enhanced, Supported}  (drops Approved, Uncertain)
  - Tissue:      Level        ∈ {High, Medium}         (drops Low, Not detected)

Input:   data/raw/subcellular_location.tsv
         data/raw/normal_tissue.tsv
Output:  data/processed/hpa_merged.csv

Columns:
  gene | main_location | additional_location | reliability
  all_locations | expressed_tissues

Run from project root:
  python scripts/03_process_hpa.py
"""

import ast
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────
RAW_DIR  = Path("data/raw")
OUT_DIR  = Path("data/processed")
OUT_CSV  = OUT_DIR / "hpa_merged.csv"

OUT_DIR.mkdir(parents=True, exist_ok=True)

SUB_TSV = RAW_DIR / "subcellular_location.tsv"
TIS_TSV = RAW_DIR / "normal_tissue.tsv"

for p in (SUB_TSV, TIS_TSV):
    if not p.exists():
        raise FileNotFoundError(
            f"Missing {p}. Run scripts/01_download_data.py first."
        )

# ── 1. Subcellular location ───────────────────────────────────
print(f"Loading {SUB_TSV.name} …")
sub = pd.read_csv(SUB_TSV, sep="\t", low_memory=False)

print(f"  Raw rows    : {len(sub):,}")
print(f"  Columns     : {list(sub.columns)}")

# Reliability tiers: Enhanced > Supported > Approved > Uncertain
RELIABLE_TIERS = {"Enhanced", "Supported"}
reliable = sub[sub["Reliability"].isin(RELIABLE_TIERS)].copy()
print(f"  After reliability filter ({', '.join(RELIABLE_TIERS)}): {len(reliable):,} rows")

# Normalise column names — HPA occasionally changes capitalisation across versions
col_map = {c: c for c in reliable.columns}
# Try both known variants
gene_col = next((c for c in reliable.columns if c.lower() == "gene name"), None)
main_col = next((c for c in reliable.columns if c.lower() == "main location"), None)
add_col  = next((c for c in reliable.columns if c.lower() == "additional location"), None)
rel_col  = next((c for c in reliable.columns if c.lower() == "reliability"), None)

if not gene_col:
    raise KeyError(f"Cannot find 'Gene name' column. Available: {list(reliable.columns)}")

reliable = reliable[[gene_col, main_col, add_col, rel_col]].copy()
reliable.columns = ["gene", "main_location", "additional_location", "reliability"]

# Combine main + additional into a single semicolon-separated string
reliable["all_locations"] = (
    reliable["main_location"].fillna("") + ";" +
    reliable["additional_location"].fillna("")
).str.strip(";").str.replace(";;", ";", regex=False)

print(f"  Unique proteins (reliable) : {reliable['gene'].nunique():,}")
print(f"\nReliability breakdown:")
print(reliable["reliability"].value_counts().to_string())

# ── 2. Normal tissue expression ───────────────────────────────
print(f"\nLoading {TIS_TSV.name} …")
tissue = pd.read_csv(TIS_TSV, sep="\t", low_memory=False)

print(f"  Raw rows    : {len(tissue):,}")
print(f"  Columns     : {list(tissue.columns)}")

# Normalise column names
t_gene_col   = next((c for c in tissue.columns if c.lower() == "gene name"), None)
t_tissue_col = next((c for c in tissue.columns if c.lower() == "tissue"), None)
t_level_col  = next((c for c in tissue.columns if c.lower() == "level"), None)

if not t_gene_col:
    raise KeyError(f"Cannot find 'Gene name' column in tissue TSV. Available: {list(tissue.columns)}")

EXPRESSED_LEVELS = {"High", "Medium"}
expressed = tissue[tissue[t_level_col].isin(EXPRESSED_LEVELS)]

print(f"  After level filter ({', '.join(EXPRESSED_LEVELS)}): {len(expressed):,} rows")

# Aggregate: gene → sorted unique list of tissues
tissue_by_gene = (
    expressed.groupby(t_gene_col)[t_tissue_col]
    .apply(lambda x: sorted(x.unique().tolist()))
    .reset_index()
)
tissue_by_gene.columns = ["gene", "expressed_tissues"]
print(f"  Unique genes with High/Med expression: {len(tissue_by_gene):,}")

# ── 3. Merge ──────────────────────────────────────────────────
print("\nMerging subcellular + tissue data …")
merged = reliable.merge(tissue_by_gene, on="gene", how="left")

# Fill proteins with no matched tissue data with an empty list (as string for CSV storage)
merged["expressed_tissues"] = merged["expressed_tissues"].apply(
    lambda x: x if isinstance(x, list) else []
)

print(f"  Merged rows : {len(merged):,}")
print(f"  With tissue data   : {merged['expressed_tissues'].apply(bool).sum():,}")
print(f"  Without tissue data: {(~merged['expressed_tissues'].apply(bool)).sum():,}")

# Store lists as proper Python repr so they can be read back with ast.literal_eval
merged["expressed_tissues"] = merged["expressed_tissues"].apply(repr)

# ── 4. Save ───────────────────────────────────────────────────
merged.to_csv(OUT_CSV, index=False)

print(f"\n✓ Saved → {OUT_CSV} ({OUT_CSV.stat().st_size / 1_048_576:.2f} MB)")
print(f"  Columns : {list(merged.columns)}")
print(f"  Rows    : {len(merged):,}")
print("\nSample rows:")
print(merged[["gene", "all_locations", "reliability"]].head(5).to_string(index=False))
print("\nNext step: python scripts/04_generate_qa_pairs.py")
