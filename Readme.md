# locus.ai 🔬

> *Fine-tuned Qwen2.5-3B on 6,000 cell localization Q&A pairs generated from GO Cellular Component annotations and Human Protein Atlas experimental data using QLoRA — improving subcellular location accuracy from 35% to 73% and reducing hallucination rate from 34% to 11%. Built a pure Node.js inference server using node-llama-cpp with 4 typed endpoints returning structured JSON at sub-300ms latency.*

---

## What It Does

Given a protein name or UniProt accession, **locus.ai** answers:

| Question | Example |
|---|---|
| 📍 Where in the cell is this protein? | *TP53 → nucleus* |
| 🫀 Which tissues express it? | *TP53 → liver, kidney, brain, lung, colon* |
| 🧬 What happens when localization fails? | *CFTR membrane failure → cystic fibrosis* |
| ⚗️ Compare two proteins' co-localization | *BRCA1 vs BRCA2* |

Every answer is **typed, structured JSON** — not freeform text.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Data Pipeline                         │
│  GO-CC (180k annotations) + HPA (13k proteins) + UniProt   │
│                    ↓ 6,000 Q&A pairs                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    QLoRA Fine-Tuning                         │
│    Qwen2.5-3B-Instruct · 4-bit NF4 · r=16 · 3 epochs       │
│          ~85 min on Colab Pro A100 · ~$10 total             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              Node.js Inference Server                        │
│       node-llama-cpp · GGUF Q4_K_M · <300ms latency        │
│   POST /protein/locate  ·  /tissues  ·  /disease  ·  /compare │
└─────────────────────────────────────────────────────────────┘
```

---

## Datasets

| Source | Entries | Contribution |
|--------|---------|--------------|
| [GO Cellular Component](https://current.geneontology.org/annotations/goa_human.gaf.gz) | 180k filtered | Location terms, evidence codes |
| [Human Protein Atlas](https://www.proteinatlas.org/download/subcellular_location.tsv.zip) | 13k proteins | Imaging-validated locations + tissue expression |
| [UniProt Swiss-Prot](https://rest.uniprot.org/uniprotkb/stream?query=reviewed:true+AND+organism_id:9606&format=json) | 20k human | Disease links, function context |
| **Final Q&A pairs** | **~6,000** | Training set after dedup + quality filter |

Only experimentally validated annotations are used (evidence codes: EXP, IDA, IMP, IGI, IEP, HDA, HMP). No predicted annotations.

---

## Project Structure

```
locus.ai/
├── data/
│   ├── raw/                    # Downloaded source files
│   │   ├── goa_human.gaf
│   │   ├── subcellular_location.tsv
│   │   ├── normal_tissue.tsv
│   │   └── uniprot_human.json
│   ├── processed/              # Intermediate outputs
│   │   ├── go_cc_filtered.csv
│   │   ├── hpa_merged.csv
│   │   └── training_pairs.jsonl
│   └── splits/                 # Final train/val/test
│       ├── train.jsonl         # 5,000 pairs
│       ├── val.jsonl           # 500 pairs
│       └── test.jsonl          # 500 pairs
├── scripts/
│   ├── 01_download_data.py
│   ├── 02_process_go_cc.py
│   ├── 03_process_hpa.py
│   ├── 04_generate_qa_pairs.py
│   ├── 05_merge_and_split.py
│   └── 06_baseline_eval.py
├── training/
│   ├── finetune.py             # QLoRA training (run in Colab)
│   ├── eval.py                 # Post-training evaluation
│   └── export_gguf.sh          # Convert to GGUF for node-llama-cpp
└── server/
    ├── index.js                # Express inference server
    ├── tokenizer.js
    └── package.json
```

---

## Quick Start

### 1. Environment Setup

```bash
# Clone and set up Python environment
git clone https://github.com/your-username/locus.ai.git
cd locus.ai

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Download Data

```bash
python scripts/01_download_data.py
```

### 3. Run the Data Pipeline

```bash
python scripts/02_process_go_cc.py
python scripts/03_process_hpa.py
python scripts/04_generate_qa_pairs.py
python scripts/05_merge_and_split.py
```

### 4. Baseline Evaluation (before fine-tuning)

```bash
python scripts/06_baseline_eval.py
# Expected: ~32-38% location accuracy
```

### 5. Fine-Tune (Colab Pro — A100)

Upload `training/finetune.py` to a Colab Pro notebook and run it.  
Training time: **~85 minutes · 3 epochs · ~$10 Colab compute**.

### 6. Run the Inference Server

```bash
# Copy model to server directory
cp locus.ai-qwen-3b-q4.gguf server/models/

cd server
npm install
node index.js
# Server running on :3000
```

---

## API Reference

### `POST /protein/locate`

```bash
curl -X POST http://localhost:3000/protein/locate \
  -H "Content-Type: application/json" \
  -d '{"protein": "TP53"}'
```

```json
{
  "protein": "TP53",
  "primary_location": "nucleus",
  "additional_details": "TP53 is a nuclear transcription factor validated by HPA imaging. Cytoplasmic localization occurs transiently during stress response.",
  "expressed_tissues": ["liver", "kidney", "brain", "lung", "colon"],
  "disease_link": "Nuclear export of TP53 is a key mechanism in cancer progression — cytoplasmic sequestration inactivates its tumor suppressor function.",
  "confidence": "high",
  "latency_ms": 284,
  "model": "locus.ai-qwen2.5-3b"
}
```

### `POST /protein/tissues`

Returns tissues where the protein is expressed at High/Medium levels (Human Protein Atlas).

### `POST /protein/disease`

Returns disease associations caused by protein mislocalization.

### `POST /protein/compare`

```bash
curl -X POST http://localhost:3000/protein/compare \
  -H "Content-Type: application/json" \
  -d '{"protein_a": "BRCA1", "protein_b": "BRCA2"}'
```

Returns co-localization analysis and interaction possibility.

### `GET /health`

Returns server status, model info, and available endpoints.

---

## Model Details

| Property | Value |
|----------|-------|
| Base model | `Qwen/Qwen2.5-3B-Instruct` |
| Method | QLoRA (4-bit NF4) |
| LoRA rank | r=16, α=32 |
| Target modules | q_proj, v_proj, k_proj, o_proj, gate_proj |
| Training data | 5,000 Q&A pairs |
| Epochs | 3 · LR 2e-4 · cosine decay |
| Serving format | GGUF Q4_K_M via node-llama-cpp |
| Inference latency | < 300ms |

---

## Requirements

### Python (Data Pipeline + Training)

```
transformers>=4.40
datasets>=2.19
peft>=0.10
trl>=0.8
bitsandbytes>=0.43
accelerate>=0.29
pandas>=2.0
requests>=2.31
tqdm>=4.66
wandb>=0.16
sentencepiece
protobuf
```

### Node.js (Inference Server)

```
node >= 18.x
express
node-llama-cpp
cors
dotenv
```

---

## Why This Matters Clinically

Mislocalized proteins underlie some of the most important human diseases:

- **Nucleus → Cytoplasm**: TDP-43 cytoplasmic aggregation is the hallmark of **ALS and FTLD**
- **Plasma membrane failures**: CFTR misfolding causes **cystic fibrosis**
- **Mitochondrial mislocalization**: Linked to **Parkinson's disease** via PINK1/Parkin pathway
- **ER retention defects**: α1-antitrypsin deficiency, affecting **lung and liver**
- **Nuclear export of TP53**: Key mechanism in **cancer progression**

A model that correctly localizes proteins — and knows what goes wrong when that fails — provides a meaningful signal for biomedical research.

---

## Deployment

Deploy the inference server to [Render](https://render.com) with the included `render.yaml`:

```bash
git add . && git commit -m "locus.ai inference server"
# Push to GitHub, connect repo to Render
# Upload GGUF (~2GB) to Render persistent disk via dashboard
```

The GGUF model is excluded from git (see `.gitignore`). Upload it manually to the Render disk.

---

## License

MIT — see [LICENSE](LICENSE)

---

*Built in 4 days · Qwen2.5-3B · QLoRA · node-llama-cpp · GO-CC + HPA + UniProt*
