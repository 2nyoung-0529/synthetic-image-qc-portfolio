PYTHON ?= python3
ROOT   ?= .

.PHONY: help validate generate charts clean

help:
	@echo "Targets:"
	@echo "  make validate   - run reconciliation checks on the curated dataset (ROOT=$(ROOT))"
	@echo "  make generate   - generate a fresh synthetic dataset into build/data and validate it"
	@echo "  make charts     - regenerate the charts into build/charts (needs matplotlib)"
	@echo "  make clean      - remove the build/ directory"

validate:
	$(PYTHON) tools/validate_data.py $(ROOT)

generate:
	$(PYTHON) tools/generate_qc_dataset.py --out build/data
	$(PYTHON) tools/validate_data.py build

charts:
	$(PYTHON) tools/make_charts.py --data $(ROOT)/data --out build/charts

clean:
	rm -rf build
