# Override on the command line for Colab: make pipeline PYTHON=python
PYTHON := uv run
SCRIPTS := scripts

# ──────────────────────────────────────────────────────────────
# Default: show help
# ──────────────────────────────────────────────────────────────
.DEFAULT_GOAL := help

help:
	@echo ""
	@echo "  CellLocQA — Data Pipeline"
	@echo ""
	@echo "  Local (uv):"
	@echo "    make pipeline            Run all steps end-to-end"
	@echo ""
	@echo "  Google Colab (paste into a cell):"
	@echo "    !make colab-setup        Install pip dependencies"
	@echo "    !make pipeline PYTHON=python"
	@echo ""
	@echo "  Individual steps:"
	@echo "    make step1      Download raw data"
	@echo "    make step2      Process GO Cellular Component"
	@echo "    make step3      Process Human Protein Atlas"
	@echo "    make validate   Validate processed data"
	@echo "    make step4      Generate Q&A pairs"
	@echo "    make step5      Split into train / val / test"
	@echo ""
	@echo "  Cleaning:"
	@echo "    make clean      Remove processed + split files (keep raw downloads)"
	@echo "    make clean-all  Remove everything including raw downloads"
	@echo ""

# ──────────────────────────────────────────────────────────────
# Colab setup — installs pip deps (uv not available in Colab)
# ──────────────────────────────────────────────────────────────
colab-setup:
	pip install -q pandas requests tqdm transformers datasets \
	            peft trl accelerate sentencepiece protobuf wandb

# ──────────────────────────────────────────────────────────────
# Individual steps
# ──────────────────────────────────────────────────────────────
step1:
	@echo "\n▶  Step 1/5 — Download raw data"
	$(PYTHON) $(SCRIPTS)/01_download_data.py

step2: step1
	@echo "\n▶  Step 2/5 — Process GO Cellular Component"
	$(PYTHON) $(SCRIPTS)/02_process_go_cc.py

step3: step2
	@echo "\n▶  Step 3/5 — Process Human Protein Atlas"
	$(PYTHON) $(SCRIPTS)/03_process_hpa.py

validate: step3
	@echo "\n▶  Validate — Check data quality"
	$(PYTHON) $(SCRIPTS)/validate_data.py

step4: validate
	@echo "\n▶  Step 4/5 — Generate Q&A pairs"
	$(PYTHON) $(SCRIPTS)/04_generate_qa_pairs.py

step5: step4
	@echo "\n▶  Step 5/5 — Split into train / val / test"
	$(PYTHON) $(SCRIPTS)/05_merge_and_split.py

# ──────────────────────────────────────────────────────────────
# Full pipeline
# ──────────────────────────────────────────────────────────────
pipeline: step5
	@echo "\n✓ Pipeline complete. Splits in data/splits/"
	@echo "  Next: upload training/finetune.py to Colab Pro (A100)"

# ──────────────────────────────────────────────────────────────
# Clean
# ──────────────────────────────────────────────────────────────
clean:
	@echo "Removing generated data files (keeping raw downloads) …"
	rm -f data/processed/*.csv data/processed/*.jsonl
	rm -f data/splits/*.jsonl
	@echo "Done. Run 'make pipeline' to regenerate."

clean-all: clean
	@echo "Removing raw downloads too …"
	rm -f data/raw/*.gaf data/raw/*.tsv
	rm -f data/raw/*.gz data/raw/*.zip

.PHONY: help pipeline step1 step2 step3 step4 step5 validate clean clean-all colab-setup
