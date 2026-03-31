# OVF Setup Guide

This guide explains how to run the OVF project with the provided prebuilt OpenSearch data.

## Assumptions

- You are using a Linux environment.
- Docker and `docker compose` are already installed and working.
- Ollama is already installed.
- The file `opensearch_data_backup.tar.gz` is provided in the project root.
- The file `opensearch.yml` is provided in the project root.
- The provided `docker-compose.yml` already mounts `opensearch.yml` and the `opensearch_data` volume correctly.

## 1. Clone the project

```bash
git clone https://github.com/GDDPR/ovf.git
cd ovf
```

## 2. Pull the required Docker images

```bash
docker pull opensearchproject/opensearch:3
docker pull opensearchproject/opensearch-dashboards:3
```

## 3. Prepare Ollama

Pull the chat model:

```bash
ollama pull gemma3:12b
```

If Ollama is not already running, start it:

```bash
ollama serve
```

## 4. Create the `.env` file

Create a file named `.env` in the project root and paste this into it:

```env
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_MODEL_ID=4PjDQp0BBb-Rz_blyovD

INDEX_NAME=ovf-docs
PIPELINE_NAME=ovf-ingest-pipeline
HYBRID_SEARCH_PIPELINE=ovf-hybrid-pipeline
INPUT_DIR=./data/docs_json

TOP_K=8

INDEX_SLEEP_SECONDS=0.5
MAX_RETRIES_429=20
RETRY_SLEEP_SECONDS=10.0
MAX_WORDS_PER_CHUNK=350
CHUNK_OVERLAP_WORDS=50

OLLAMA_HOST=http://localhost:11434
OLLAMA_CHAT_MODEL=gemma3:12b
```

## 5. Restore the provided OpenSearch data

Make sure `opensearch_data_backup.tar.gz` is in the project root.

Create the Docker volume:

```bash
docker volume create opensearch_data
```

Extract the backup:

```bash
mkdir -p restore_tmp
tar xzf opensearch_data_backup.tar.gz -C restore_tmp
```

Copy the extracted data into the Docker volume:

```bash
docker run --rm -v opensearch_data:/target -v "$(pwd)/restore_tmp/opensearch_data:/source" alpine sh -c 'cp -a /source/. /target/'
```

## 6. Start the Docker services

Before starting the containers, make sure `opensearch.yml` exists in the project root.

The file should contain:

```yaml
cluster.name: opensearch-cluster
network.host: 0.0.0.0
discovery.type: single-node
knn.faiss.avx2.disabled: true
knn.faiss.avx512.disabled: true
knn.faiss.avx512_spr.disabled: true
```

Start the containers:

```bash
docker compose up -d
```

You can check that the containers are running with:

```bash
docker ps
```

## 7. Install Python dependencies

```bash
pip install -r requirements.txt
```

If you are using a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 8. Run the program

```bash
python src/rag/ask.py
```

You will be prompted to choose a retrieval model:

- `1` for semantic/vector retrieval
- `2` for hybrid retrieval

## 9. Optional checks

Check that the OpenSearch index exists:

```bash
curl "http://localhost:9200/_cat/indices?v"
```

Open OpenSearch Dashboards in a browser at:

```text
http://localhost:5601
```

## Notes

- The project expects the OpenSearch data volume to be named `opensearch_data`.
- The provided backup already contains the indexed chunk data.
- The provided OpenSearch data already includes the working `ovf-docs` index.
- If `docker compose up -d` starts successfully and Ollama is running, you should be able to use `ask.py` immediately without recreating the index or re-ingesting the documents.

## Quick start summary

```bash
git clone https://github.com/GDDPR/ovf.git
cd ovf
docker pull opensearchproject/opensearch:3
docker pull opensearchproject/opensearch-dashboards:3
ollama pull gemma3:12b
docker volume create opensearch_data
mkdir -p restore_tmp
tar xzf opensearch_data_backup.tar.gz -C restore_tmp
docker run --rm -v opensearch_data:/target -v "$(pwd)/restore_tmp/opensearch_data:/source" alpine sh -c 'cp -a /source/. /target/'
docker compose up -d
pip install -r requirements.txt
python src/rag/ask.py
```