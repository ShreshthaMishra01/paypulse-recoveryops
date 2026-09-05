.PHONY: setup api web test build

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm install

api:
	cd backend && ../.venv/bin/python run.py

web:
	cd frontend && npm run dev

test:
	cd backend && ../.venv/bin/python -m unittest discover -s tests -v
	cd frontend && npm run build

build:
	cd frontend && npm run build
