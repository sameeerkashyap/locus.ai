#!/usr/bin/env python3
"""
01_download_data.py
───────────────────
Downloads all three source datasets needed for CellLocQA:
  1. GO Cellular Component annotations (GOA human GAF)
  2. Human Protein Atlas — subcellular location
  3. Human Protein Atlas — normal tissue expression

Outputs (all in data/raw/):
  goa_human.gaf
  subcellular_location.tsv
  normal_tissue.tsv

Run from project root:
  python scripts/01_download_data.py
"""

import gzip
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────
RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ── Download helpers ──────────────────────────────────────────

def curl_download(url: str, dest: Path) -> None:
    """Download a URL to dest using curl with a progress bar."""
    if dest.exists():
        print(f"  [skip] {dest.name} already exists")
        return
    print(f"  → Downloading {dest.name} …")
    result = subprocess.run(
        ["curl", "-L", "--progress-bar", "-o", str(dest), url],
        check=False,
    )
    if result.returncode != 0:
        print(f"  [ERROR] curl failed for {url}", file=sys.stderr)
        sys.exit(1)
    print(f"  ✓ Saved {dest.name} ({dest.stat().st_size / 1_048_576:.1f} MB)")


def gunzip_file(gz_path: Path, out_path: Path) -> None:
    """Decompress a .gz file."""
    if out_path.exists():
        print(f"  [skip] {out_path.name} already decompressed")
        return
    print(f"  → Decompressing {gz_path.name} …")
    with gzip.open(gz_path, "rb") as f_in, open(out_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    print(f"  ✓ {out_path.name} ({out_path.stat().st_size / 1_048_576:.1f} MB)")


def unzip_file(zip_path: Path, dest_dir: Path, expected_file: str) -> None:
    """Extract first matching file from a zip archive."""
    out = dest_dir / expected_file
    if out.exists():
        print(f"  [skip] {expected_file} already extracted")
        return
    print(f"  → Extracting {zip_path.name} …")
    # Sanity-check: proteinatlas.org sometimes redirects to an HTML page
    if not zipfile.is_zipfile(zip_path):
        print(
            f"  [ERROR] {zip_path.name} is not a valid zip file — "
            "the server may have returned an HTML error page.\n"
            f"  Delete {zip_path} and retry, or download manually from "
            "https://www.proteinatlas.org/about/download",
            file=sys.stderr,
        )
        zip_path.unlink(missing_ok=True)   # remove bad file so next run re-downloads
        sys.exit(1)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        # find the TSV inside the archive (name may differ from expected_file)
        tsv_names = [n for n in names if n.endswith(".tsv")]
        if not tsv_names:
            print(f"  [ERROR] No .tsv found inside {zip_path.name}: {names}", file=sys.stderr)
            sys.exit(1)
        # extract and rename to expected_file
        source = tsv_names[0]
        with zf.open(source) as src, open(out, "wb") as dst:
            shutil.copyfileobj(src, dst)
    print(f"  ✓ {expected_file} ({out.stat().st_size / 1_048_576:.1f} MB)")


# ── Dataset 1 — GO Cellular Component ─────────────────────────
print("\n[1/3] Gene Ontology – Cellular Component (GOA human)")
GOA_URL = "https://current.geneontology.org/annotations/goa_human.gaf.gz"
goa_gz  = RAW_DIR / "goa_human.gaf.gz"
goa_out = RAW_DIR / "goa_human.gaf"

curl_download(GOA_URL, goa_gz)
gunzip_file(goa_gz, goa_out)


# ── Dataset 2a — HPA Subcellular Location ─────────────────────
# Note: the main proteinatlas.org download endpoint requires a browser session.
# We use the versioned mirror (v23) which serves direct zip files.
print("\n[2/3] Human Protein Atlas – Subcellular location")
HPA_SUB_URL = "https://v23.proteinatlas.org/download/subcellular_location.tsv.zip"
hpa_sub_zip = RAW_DIR / "subcellular_location.tsv.zip"
SUB_TSV     = "subcellular_location.tsv"

curl_download(HPA_SUB_URL, hpa_sub_zip)
unzip_file(hpa_sub_zip, RAW_DIR, SUB_TSV)


# ── Dataset 2b — HPA Normal Tissue ───────────────────────────
print("\n[3/3] Human Protein Atlas – Normal tissue expression")
HPA_TIS_URL = "https://v23.proteinatlas.org/download/normal_tissue.tsv.zip"
hpa_tis_zip = RAW_DIR / "normal_tissue.tsv.zip"
TIS_TSV     = "normal_tissue.tsv"

curl_download(HPA_TIS_URL, hpa_tis_zip)
unzip_file(hpa_tis_zip, RAW_DIR, TIS_TSV)


# ── Summary ───────────────────────────────────────────────────
print("\n" + "─" * 50)
print("Download complete. Files in data/raw/:")
for f in sorted(RAW_DIR.iterdir()):
    mb = f.stat().st_size / 1_048_576
    print(f"  {f.name:<40} {mb:>7.1f} MB")
print("─" * 50)
print("Next step: python scripts/02_process_go_cc.py")
