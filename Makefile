.PHONY: req-install req-update run test clean cleanall help

req-install:
	pip install pip-tools
	pip-sync requirements.txt

req-update:
	pip-compile --upgrade requirements.in
	pip-sync requirements.txt

run:
	python app.py

test:
	pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache

cleanall: clean
	rm -rf .env neonize.db message_cache.db

.DEFAULT_GOAL := help

help:
	@echo "Available targets:"
	@echo "  req-install  - Install dependencies"
	@echo "  req-update   - Update dependencies"
	@echo "  run          - Start the WA -> Discord forwarder"
	@echo "  test         - Run test suite"
	@echo "  clean        - Remove __pycache__ dirs"
	@echo "  cleanall     - Remove all generated files including .env and neonize.db"
