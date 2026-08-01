# YUCLAW — external replication entry point (2026-08-01).
#
#   make replicate
#
# builds a clean virtual environment, installs the published package from
# PyPI, fetches the PUBLIC replay bundle from the live site, recomputes the
# published Validation Lab statistics, and diffs them against the published
# page values. Exit 0 = reproduced; 1 = mismatch (please open a replication
# issue — .github/ISSUE_TEMPLATE/replication.md); 3 = bundle fetch failed.
#
# No repository checkout, database, or GPU is required — this is the path a
# stranger takes. See REPLICATIONS.md for the reporting protocol.

REPLICATE_ENV := .replicate-env

.PHONY: replicate replicate-clean

replicate:
	python3 -m venv $(REPLICATE_ENV) --clear
	$(REPLICATE_ENV)/bin/pip install --quiet yuclaw
	$(REPLICATE_ENV)/bin/yuclaw replay-lab
	@echo "replication complete — see REPLICATIONS.md to report your result"

replicate-clean:
	rm -rf $(REPLICATE_ENV)
