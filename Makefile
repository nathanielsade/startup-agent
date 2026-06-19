.PHONY: dev backend frontend
backend:
	uv run uvicorn api.main:app --reload --port 8000
frontend:
	cd frontend && npm run dev
dev:
	uv run uvicorn api.main:app --port 8000 & cd frontend && npm run dev
