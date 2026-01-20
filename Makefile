.PHONY: req-install req-update run clean cleanall

req-install:
	npm install

req-update:
	npm update

run:
	node index.js

clean:
	rm -rf node_modules
	rm -f package-lock.json

cleanall: clean
	rm -f .env auth_info

.DEFAULT_GOAL := help

help:
	@echo "Available targets:"
	@echo "  req-install  - Install dependencies"
	@echo "  req-update   - Update dependencies"
	@echo "  run          - Start the WA -> Discord forwarder"
	@echo "  clean        - Remove node_modules and package-lock.json"
	@echo "  cleanall     - Remove all generated files including .env and auth_info"
