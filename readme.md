# OVF Setup Guide

## Prereqs

Have a folder named `ovf` with the following files:

- `ovf_opensearch_data_backup.tar.gz`
- `docker-compose.yml`
- `.env`
- `opensearch_dashboards.yml`

## Install Docker

Install Docker on your machine before continuing.

## Start Ollama

Run this in your terminal:

```bash
docker run -d \
  --name ollama \
  -p 11434:11434 \
  -v ollama:/root/.ollama \
  ollama/ollama
```

## Pull the model

Run this in your terminal:

```bash
docker exec -it ollama ollama pull gemma3:12b
```

## Create the OpenSearch volume

From the `ovf` folder, run:

```bash
docker volume create ovf_opensearch_data
```

## Restore the OpenSearch backup into the volume

From the `ovf` folder, run:

```bash
docker run --rm \
  -v ovf_opensearch_data:/volume \
  -v $(pwd):/backup \
  alpine \
  sh -c "cd /volume && tar xzf /backup/ovf_opensearch_data_backup.tar.gz"
```

## Start the OVF stack

From the `ovf` folder, run:

```bash
docker compose up -d
```

## Open OpenSearch Dashboards

Open this in your browser:

```text
http://localhost:5601
```
