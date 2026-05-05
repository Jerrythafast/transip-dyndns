RUN = uv run
RUFF = $(RUN) ruff
MYPY = $(RUN) mypy


.PHONY: lint
lint:
	@$(RUFF) check .
	@$(RUFF) format --check .
	@$(MYPY) .

.PHONY: fix
fix:
	@$(RUFF) check --fix .
	@$(RUFF) format .
