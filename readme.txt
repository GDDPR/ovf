To set up indexes in opensearch manually

1. run src/scrape/catalogbuild.py (creates xml file)
2. run src/scrape/parse_catalog.py (creates chunks and saves as json)
3. run src/ingest/create_index.py
4. run src/ingest/embed_sections.py
5. run src/ingest/ingest_sections.py

To use the model:

1. run ask.py