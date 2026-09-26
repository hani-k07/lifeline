PYTHON ?= python

.PHONY: setup seed run test lint types check docker

setup:  ## install dependencies and create/migrate the database
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(PYTHON) -m scripts.setup_db

seed:  ## delete the database and recreate it with demo data
	$(PYTHON) -m scripts.setup_db --reset

run:
	$(PYTHON) -m streamlit run app.py

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

types:
	$(PYTHON) -m mypy

check: lint types test  ## what CI runs

docker:
	docker build -t lifeline .
