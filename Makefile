PYTHON = uv run python
UV = uv

SRC = src

.PHONY: help run scraper enrich responses clean clean-all

help:
	@echo "run       - Lance la campagne : make run FILE=test.xlsx"
	@echo "scraper   - Lance le scraper"
	@echo "enrich    - Enrichit les prospects"
	@echo "responses - Traite les réponses IMAP"
	@echo "clean     - Nettoie le projet"
	@echo "clean-all - Nettoyage complet"

run:
	$(PYTHON) $(SRC)/main.py "$(FILE)"

scraper:
	$(PYTHON) $(SRC)/scraper_massif.py

enrich:
	$(PYTHON) $(SRC)/enrichir_tout.py

responses:
	$(PYTHON) $(SRC)/traiter_reponses_imap.py

clean:
	$(PYTHON) scripts/clean.py

clean-all: clean
	$(UV) venv --clear
