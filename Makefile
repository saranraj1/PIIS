.PHONY: install test lint profile m2-corpus m2-train m2-eval m2_1-benchmark m2_1-eval

install:
	pip install -e ".[dev]"

test:
	pytest -v

lint:
	ruff check src tests scripts

profile:
	python scripts/profile_dataset.py $(FILE)

m2-corpus:
	python scripts/generate_m2_corpus.py

m2-train:
	python scripts/train_classifier.py
	python scripts/train_severity.py

m2-eval:
	python scripts/evaluate_routing.py

m2_1-benchmark:
	python scripts/generate_m2_1_benchmark.py

m2_1-eval:
	python scripts/evaluate_m2_1_suite.py
