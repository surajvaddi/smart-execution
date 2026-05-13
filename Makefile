.PHONY: test api frontend frontend-build install install-frontend

test:
	pytest -q

api:
	uvicorn src.api:app --host 127.0.0.1 --port 8000 --loop asyncio

frontend:
	cd frontend && npm run dev -- --host 127.0.0.1

frontend-build:
	cd frontend && npm run build

install:
	python -m pip install -r requirements.txt

install-frontend:
	cd frontend && npm install
