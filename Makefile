PYTHON = python3
UV = uv
SRC = src/

run:
	$(UV) run $(SRC)/main.py "$(FILE)"

scraper:
	$(UV) run $(PYTHON) $(SRC)/scraper_massif.py

enrich:
	$(UV) run $(PYTHON) $(SRC)/enrichir_tout.py

responses:
	$(UV) run $(SRC)/traiter_reponses_imap.py

clean:
	$(PYTHON) scripts/clean.py

clean-all: clean
	$(PYTHON) scripts/clean-all.py

help:
	@echo "run       - Lance la campagne : make run FILE=test.xlsx"
	@echo "scraper   - Lance le scraper"
	@echo "enrich    - Enrichit les prospects"
	@echo "responses - Traite les réponses IMAP"
	@echo "clean     - Nettoie le projet des fichiers temporaires"
	@echo "clean-all - Nettoyage complet"

.PHONY: run scraper enrich responses clean clean-all help