.PHONY: help install demo test audit bench console docker docs bundle clean all

help:
	@echo "STRATA — universal log pre-processing"
	@echo "  make install   install dependencies"
	@echo "  make demo      the full scripted demonstration (start here)"
	@echo "  make console   web console at http://localhost:8400"
	@echo "  make test      run the test suite"
	@echo "  make audit     prove losslessness and integrity"
	@echo "  make bench     measured throughput, 1 and 4 workers"
	@echo "  make docs      regenerate the grammar reference"
	@echo "  make docker    build and run the container stack"
	@echo "  make bundle    build the air-gapped offline bundle"
	@echo "  make all       install, test, demo, audit"
	@echo "  make clean     remove everything generated"

install:      ; python3 -m pip install -r requirements-dev.txt
demo:         ; python3 strata.py demo --count 20000
console:      ; python3 strata.py console
test:         ; python3 -m pytest -q
audit:        ; python3 strata.py audit
docs:         ; python3 tools/gen_reference.py
bundle:       ; ./build-bundle.sh
bench:
	@python3 strata.py bench --count 60000
	@python3 strata.py bench --count 60000 --workers 4
docker:
	docker compose build && docker compose up -d && echo "console: http://localhost:8400"
all: install test demo audit
	@echo "\nAll green. See docs/DEMO-SCRIPT.md for the judge run-through."
clean:
	rm -rf var .pytest_cache offline-bundle deck/*.jpg deck/*.pdf
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
	rm -f grammars/meridian.gateway.yaml
