# Data Scraping and Ingestion Guide

This guide explains the scrape-to-ingestion workflow for OVF.

It covers:

1. Scraping the DAOD 6000-series source pages
2. Building a local `data/` folder
3. Converting scraped source pages into JSON documents
4. Creating the OpenSearch index and ingest pipeline
5. Ingesting the JSON sections as searchable chunks

This guide is focused on the **data scrape and ingestion pipeline**, not on running the final QA app.

---

## Project structure used in this guide

Relevant files:

```text
src/
├── scrape/
│   ├── catalog_utils.py
│   ├── catalogbuild.py
│   ├── daod6000_scraper.py
│   ├── parse_catalog.py
│   └── reset_xml.py
├── ingest/
│   ├── create_index.py
│   ├── ingest_sections.py
│   ├── commands.txt
│   └── index_schema.txt
```

You may also see old or archived versions such as:

- `*_old.py`
- `archive/`

Those are not part of the main workflow below.

---

## Overview of the workflow

The intended flow is:

1. Build a catalog of DAOD 6000-series pages
2. Save that catalog in `data/catalog.xml`
3. Parse each catalog entry into a structured JSON file
4. Save those JSON files in `data/docs_json/`
5. Create the OpenSearch ingest pipeline and index
6. Ingest each JSON section into OpenSearch as chunk documents

At the end of the workflow, you should have:

- `data/catalog.xml`
- `data/docs_json/*.json`
- an OpenSearch index named `ovf-docs`

---

## Output folders

The scrape pipeline creates and uses a local `data/` folder.

Expected structure:

```text
data/
├── catalog.xml
└── docs_json/
    ├── <doc1>.json
    ├── <doc2>.json
    └── ...
```

If these folders do not already exist, create them first:

```bash
mkdir -p data/docs_json
```

---

## Step 1: Build the catalog of source URLs

Run:

```bash
python src/scrape/catalogbuild.py
```

### What this file does

`catalogbuild.py` builds the catalog of DAOD 6000-series source pages that will later be parsed into JSON documents.

It is responsible for generating the catalog file used by the rest of the scraping pipeline.

### Output

This step should produce:

```text
data/catalog.xml
```

That XML file stores the discovered source URLs and tracking fields such as status for each item.

---

## Step 2: Scrape source page metadata and content helpers

File involved:

```text
src/scrape/daod6000_scraper.py
```

### What this file does

`daod6000_scraper.py` is the scraper/helper module for collecting DAOD 6000-series content from the source site.

It is used as part of the scraping pipeline to fetch and structure source page data.

### Output

This file supports the creation of entries that end up in:

```text
data/catalog.xml
```

You typically do **not** run this file directly unless you are specifically debugging or extending the scraping logic.

---

## Step 3: Parse the catalog into JSON documents

Run:

```bash
python src/scrape/parse_catalog.py
```

### What this file does

`parse_catalog.py` reads `data/catalog.xml`, fetches the corresponding source pages, extracts the document content, and writes one structured JSON file per document.

The JSON output is the main input for the ingestion pipeline.

### Output

This step should produce files like:

```text
data/docs_json/<hash>.json
```

Each JSON file contains a document and its sections, typically including fields such as:

- document title
- URL
- section titles
- section text / chunk text
- metadata when available

---

## Step 4: Reset catalog statuses if you want to rerun parsing

Run only when needed:

```bash
python src/scrape/reset_xml.py
```

### What this file does

`reset_xml.py` resets the processing status fields in `data/catalog.xml` so that the parsing pipeline can be rerun from scratch.

This is useful if:

- you want to rebuild all JSON files
- you changed parsing logic
- you want to reprocess everything cleanly

### Output

This updates:

```text
data/catalog.xml
```

It does not create new JSON files by itself.

---

## Step 5: Catalog helper utilities

File involved:

```text
src/scrape/catalog_utils.py
```

### What this file does

`catalog_utils.py` contains helper functions used by the scraping pipeline, such as updating catalog entry statuses.

This is a support module and is not normally run directly.

### Output

This file does not produce a standalone output by itself. It supports updates to:

```text
data/catalog.xml
```

---

## Step 6: Create the OpenSearch ingest pipeline and index

Before this step, make sure your OpenSearch side is already set up and your `.env` is configured correctly.

Run:

```bash
python src/ingest/create_index.py
```

### What this file does

`create_index.py` does two things:

1. Creates or updates the ingest pipeline
2. Creates the OpenSearch index if it does not already exist

The ingest pipeline is used to generate embeddings from `chunk_text`.

The index stores fields such as:

- `title`
- `section`
- `chunk_text`
- `url`
- `entities`
- `embedding`

### Output

This step creates or updates:

- ingest pipeline: `ovf-ingest-pipeline`
- index: `ovf-docs`

If successful, the script prints confirmation messages indicating that the pipeline and index were created or updated.

---

## Step 7: Ingest JSON sections into OpenSearch

Run:

```bash
python src/ingest/ingest_sections.py
```

### What this file does

`ingest_sections.py` reads JSON files from:

```text
./data/docs_json
```

For each document:

1. It loads the `sections`
2. Extracts section text
3. Keeps the whole section as one chunk unless it exceeds the maximum chunk size
4. Splits oversized sections with overlap when needed
5. Builds chunk documents
6. Indexes them into OpenSearch

### Chunking behavior

By default:

- maximum words per chunk: `350`
- chunk overlap words: `50`

If a section is short enough, it is kept as a single chunk.

### Output

This step indexes chunk documents into the `ovf-docs` index.

It prints progress such as:

- chunks indexed from each file
- total indexed chunks at the end

Example output style:

```text
Indexed 5 chunks from 2233b75a35185135.json
Indexed 3 chunks from abcdef1234567890.json
Done. Total indexed chunks: 313
```

---

## Files in `src/ingest/` that are not the main execution path

### `commands.txt`

Reference notes / helper commands for development.

Not part of the main pipeline.

### `index_schema.txt`

Reference schema information for the OpenSearch index.

Not part of the main execution path.

### `*_old.py`

Older versions kept for reference.

Not part of the main execution path.

---

## End-to-end command sequence

If you want the full scrape + ingestion workflow from scratch, run these in order:

```bash
mkdir -p data/docs_json

python src/scrape/catalogbuild.py
python src/scrape/parse_catalog.py

python src/ingest/create_index.py
python src/ingest/ingest_sections.py
```

If you want to reprocess the catalog from scratch first:

```bash
python src/scrape/reset_xml.py
python src/scrape/parse_catalog.py
```

---

## Expected final outputs

After the full workflow, you should have:

### Local files

```text
data/catalog.xml
data/docs_json/*.json
```

### OpenSearch objects

- ingest pipeline: `ovf-ingest-pipeline`
- index: `ovf-docs`

### Indexed content

Chunk documents containing fields such as:

- `title`
- `section`
- `chunk_text`
- `url`
- `entities`
- `embedding`

---

## Quick reference

### Scrape only

```bash
mkdir -p data/docs_json
python src/scrape/catalogbuild.py
python src/scrape/parse_catalog.py
```

### Reset and rescrape

```bash
python src/scrape/reset_xml.py
python src/scrape/parse_catalog.py
```

### Ingestion only

```bash
python src/ingest/create_index.py
python src/ingest/ingest_sections.py
```

### Full pipeline

```bash
mkdir -p data/docs_json
python src/scrape/catalogbuild.py
python src/scrape/parse_catalog.py
python src/ingest/create_index.py
python src/ingest/ingest_sections.py
```