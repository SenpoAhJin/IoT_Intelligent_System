.PHONY: help install run test simulate docker-up docker-down clean

help:
	@echo "AquaBuzz Development Commands"
	@echo ""
	@echo "  make install      - Install Python dependencies"
	@echo "  make run          - Run backend locally"
	@echo "  make test         - Run all tests"
	@echo "  make simulate     - Run simulator (10 runs, 3 players)"
	@echo "  make docker-up    - Start all services with Docker"
	@echo "  make docker-down  - Stop all Docker services"
	@echo "  make clean        - Clean generated files"

install:
	cd backend && pip install -r requirements.txt

run:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	cd backend && pytest tests/ -v --cov=app --cov=intelligence

simulate:
	python tools/simulator.py --runs 10 --players 3

docker-up:
	docker compose up -d

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf backend/aquabuzz.db
	rm -rf backend/data/aquabuzz.db
