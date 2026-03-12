#!/usr/bin/env python3
"""
04_generate_qa_pairs.py
───────────────────────
Generates structured Q&A pairs for fine-tuning from the processed HPA data.
Each protein gets 1–3 Q&A pairs across three question templates:
  - Location    : "Where in the human cell is {gene} located?"
  - Tissue      : "In which human tissues is {gene} most highly expressed?"
  - Disease     : "What disease is associated with mislocalization of {gene}?"

Input:   data/processed/hpa_merged.csv
         data/processed/go_cc_filtered.csv   (for GO term enrichment)
Output:  data/processed/training_pairs.jsonl

Run from project root:
  uv run scripts/04_generate_qa_pairs.py
"""

import ast
import json
import random
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────
HPA_CSV   = Path("data/processed/hpa_merged.csv")
GOCC_CSV  = Path("data/processed/go_cc_filtered.csv")
OUT_DIR   = Path("data/processed")
OUT_JSONL = OUT_DIR / "training_pairs.jsonl"

OUT_DIR.mkdir(parents=True, exist_ok=True)

random.seed(42)

# ── GO ID → human-readable term map ──────────────────────────
# Core terms — extend from https://geneontology.org/docs/download-ontology/
GO_TERM_MAP: dict[str, str] = {
    "GO:0005634": "nucleus",
    "GO:0005654": "nucleoplasm",
    "GO:0005730": "nucleolus",
    "GO:0005694": "chromosome",
    "GO:0005737": "cytoplasm",
    "GO:0005829": "cytosol",
    "GO:0005739": "mitochondrion",
    "GO:0005740": "mitochondrial envelope",
    "GO:0005759": "mitochondrial matrix",
    "GO:0005789": "endoplasmic reticulum membrane",
    "GO:0005783": "endoplasmic reticulum",
    "GO:0005768": "endosome",
    "GO:0005764": "lysosome",
    "GO:0005773": "vacuole",
    "GO:0005776": "peroxisome",
    "GO:0005886": "plasma membrane",
    "GO:0005615": "extracellular space",
    "GO:0070062": "extracellular exosome",
    "GO:0016020": "membrane",
    "GO:0005794": "Golgi apparatus",
    "GO:0005578": "extracellular matrix",
    "GO:0045121": "membrane raft",
    "GO:0031982": "vesicle",
    "GO:0008180": "COP9 signalosome",
    "GO:0005813": "centrosome",
    "GO:0005826": "actin cytoskeleton",
    "GO:0030496": "midbody",
    "GO:0005911": "cell junction",
    "GO:0045177": "apical part of cell",
}

# ── Disease-localization links ────────────────────────────────
LOCALIZATION_DISEASES: dict[str, str] = {
    "nucleus":                      "Nuclear localization defects are linked to laminopathies and certain cancers",
    "nucleoplasm":                  "Nucleoplasm mislocalization disrupts transcription factor activity in cancer",
    "nucleolus":                    "Nucleolar stress from mislocalization contributes to p53-driven apoptosis",
    "mitochondrion":                "Mitochondrial mislocalization is implicated in Parkinson's disease and ALS",
    "mitochondrial matrix":         "Mitochondrial matrix protein mislocalization underlies MELAS and related mitochondrial diseases",
    "plasma membrane":              "Membrane localization failures underlie cystic fibrosis (CFTR) and Long QT syndrome",
    "endoplasmic reticulum":        "ER protein mislocalization causes unfolded protein response, linked to type 2 diabetes",
    "endoplasmic reticulum membrane": "ER retention defects cause α1-antitrypsin deficiency",
    "cytoplasm":                    "Cytoplasmic mislocalization of TDP-43 is a hallmark of ALS and FTLD",
    "cytosol":                      "Cytosolic sequestration of signaling proteins disrupts kinase cascades in cancer",
    "lysosome":                     "Lysosomal enzyme mislocalization underlies Gaucher disease and other LSDs",
    "Golgi apparatus":              "Golgi fragmentation and protein mislocalization occur in Alzheimer's and Parkinson's",
    "extracellular space":          "Aberrant secretion and extracellular mislocalization contribute to amyloid diseases",
    "extracellular exosome":        "Exosomal cargo missorting alters intercellular signaling in cancer metastasis",
    "peroxisome":                   "Peroxisomal protein import failure causes Zellweger spectrum disorders",
    "centrosome":                   "Centrosomal protein mislocalization leads to mitotic errors and microcephaly",
}

def get_disease_link(location_str: str) -> str:
    """Return the most relevant disease link for a location string."""
    if not location_str:
        return "No established localization disease link in current literature."
    # Try each part of a multi-location string (semicolon-separated)
    for part in location_str.split(";"):
        part = part.strip().lower()
        for key, disease in LOCALIZATION_DISEASES.items():
            if key.lower() in part or part in key.lower():
                return disease
    return "No established localization disease link in current literature."

# ── Load data ─────────────────────────────────────────────────
print("Loading HPA data …")
hpa = pd.read_csv(HPA_CSV)

print("Loading GO-CC data …")
gocc = pd.read_csv(GOCC_CSV)

# Build gene → list of GO term names lookup
def go_ids_to_names(go_ids: list[str]) -> list[str]:
    return [GO_TERM_MAP[g] for g in go_ids if g in GO_TERM_MAP]

gocc_by_gene: dict[str, list[str]] = (
    gocc.groupby("gene")["go_id"]
    .apply(lambda ids: go_ids_to_names(ids.tolist()))
    .to_dict()
)
print(f"GO-CC lookup built: {len(gocc_by_gene):,} genes with known term names")

# ── Q&A templates ─────────────────────────────────────────────
def make_location_qa(gene: str, location: str, tissues: list, go_terms: list) -> dict:
    """Where in the cell is this protein?"""
    details = f"{gene} is experimentally validated at {location} via Human Protein Atlas imaging data."
    if go_terms:
        details += f" GO Cellular Component annotations additionally place it at: {', '.join(go_terms[:3])}."
    return {
        "instruction": f"Where in the human cell is the protein {gene} located?",
        "response": json.dumps({
            "primary_location":   location,
            "additional_details": details,
            "expressed_tissues":  tissues,
            "disease_link":       get_disease_link(location),
            "confidence":         "high",
        }, indent=2),
    }

def make_tissue_qa(gene: str, location: str, tissues: list, go_terms: list) -> dict:
    """In which tissues is this protein expressed?"""
    return {
        "instruction": f"In which human tissues is {gene} most highly expressed?",
        "response": json.dumps({
            "primary_location":  location,
            "expressed_tissues": tissues,
            "expression_note":   "High/medium expression confirmed by Human Protein Atlas RNA and protein data.",
            "confidence":        "high",
        }, indent=2),
    }

def make_disease_qa(gene: str, location: str, tissues: list, go_terms: list) -> dict:
    """What disease is linked to mislocalization?"""
    disease = get_disease_link(location)
    return {
        "instruction": f"What disease or condition is associated with mislocalization of the protein {gene}?",
        "response": json.dumps({
            "normal_location": location,
            "disease_link":    disease,
            "mechanism":       f"When {gene} fails to localize to {location}, its normal function is disrupted.",
            "confidence":      "medium",
        }, indent=2),
    }

def make_uniprot_qa(gene: str, location: str, tissues: list, go_terms: list) -> dict:
    """UniProt/GO-term level: what are ALL GO-CC compartments this protein is found in?"""
    if not go_terms:
        return None
    return {
        "instruction": f"According to Gene Ontology annotations, in which cellular compartments is {gene} found?",
        "response": json.dumps({
            "cellular_compartments": go_terms,
            "primary_location":      location,
            "annotation_source":     "Gene Ontology Cellular Component (experimentally validated evidence codes only)",
            "confidence":            "high",
        }, indent=2),
    }

TEMPLATES = [make_location_qa, make_tissue_qa, make_disease_qa, make_uniprot_qa]

# ── Generate pairs ────────────────────────────────────────────
print("\nGenerating Q&A pairs …")

pairs: list[dict] = []
skipped_no_loc = 0
skipped_no_tissue = 0

for _, row in hpa.iterrows():
    gene     = str(row["gene"]).strip()
    location = str(row["all_locations"]).strip()
    rel      = str(row["reliability"])

    # Skip rows without a usable location
    if not location or location in ("", ";", "nan"):
        skipped_no_loc += 1
        continue

    # Parse tissue list
    try:
        tissues = ast.literal_eval(row["expressed_tissues"])
    except Exception:
        tissues = []

    # Look up GO terms for this gene
    go_terms = gocc_by_gene.get(gene.upper(), gocc_by_gene.get(gene, []))

    # Determine how many templates to apply:
    # - Enhanced reliability → up to 3 templates (location, tissue, disease)
    # - Supported reliability → up to 2 templates
    # - Always skip tissue template if no tissue data
    if rel == "Enhanced":
        k = 3
    else:
        k = 2

    available = [t for t in TEMPLATES if t != make_tissue_qa or tissues]
    selected  = random.sample(available, k=min(k, len(available)))

    for template in selected:
        qa = template(gene, location, tissues, go_terms)
        if qa is not None:
            pairs.append(qa)

print(f"  Skipped (no location)  : {skipped_no_loc:,}")
print(f"  Generated Q&A pairs    : {len(pairs):,}")

# ── Shuffle + save ─────────────────────────────────────────────
random.shuffle(pairs)

with open(OUT_JSONL, "w") as f:
    for pair in pairs:
        f.write(json.dumps(pair) + "\n")

print(f"\n✓ Saved → {OUT_JSONL}")
print(f"  Total pairs : {len(pairs):,}")

# Sample preview
print("\nSample pair (pair #1):")
sample = pairs[0]
print(f"  Q: {sample['instruction']}")
resp   = json.loads(sample["response"])
print(f"  A (primary_location): {resp.get('primary_location', resp.get('cellular_compartments', '—'))}")
print("\nNext step: uv run scripts/05_merge_and_split.py")
