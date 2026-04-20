# OVF OpenSearch Assistant Setup and Restore Guide

This guide documents the OVF setup using OpenSearch Assistant and the native OpenSearch agent flow.

It is split into short chapters with copy-paste code blocks.

---

## Chapter 1: Project overview

Final working flow:

```text
User
→ OpenSearch Dashboards Assistant
→ OVF Root Chatbot Agent
→ OVF Chat Agent with RAG
→ VectorDBTool retrieves from ovf-docs
→ Ollama remote model generates the answer
→ Dashboards shows the response
```

Final working objects from the original system:

- Embedding model group: `ovf-local-model-group`
- Embedding model ID: `l65saJ0BqfEK-3L2OfNU`
- Ollama model group: `ovf-ollama-chat-group`
- Ollama remote model ID: `oq6uaJ0BqfEK-3L2YvPL`
- OVF chat agent ID: `q1ODiJ0B83izHxg-Ys3B`
- OVF root agent ID: `ulOFiJ0B83izHxg-M80I`
- OpenSearch index: `ovf-docs`
- Ingest pipeline: `ovf-ingest-pipeline`

---

## Chapter 2: Required files

At minimum, the project folder should contain:

- `docker-compose.yml`
- `opensearch_dashboards.yml`
- `.env`
- `create_index.py`
- `ingest_sections.py`
- the backend files for the project

Example `.env`:

```env
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=OpenSearchTest123!
OPENSEARCH_USE_SSL=true
OPENSEARCH_VERIFY_CERTS=false
OPENSEARCH_MODEL_ID=l65saJ0BqfEK-3L2OfNU
OPENSEARCH_INITIAL_ADMIN_PASSWORD=OpenSearchTest123!

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
OLLAMA_TIMEOUT=300
```

Example `opensearch_dashboards.yml`:

```yaml
server.host: "0.0.0.0"

opensearch.hosts: ["https://opensearch:9200"]
opensearch.username: "admin"
opensearch.password: "OpenSearchTest123!"

opensearch.ssl.verificationMode: none
opensearch.requestHeadersAllowlist: [authorization, securitytenant]

assistant.chat.enabled: true
```

Example `docker-compose.yml`:

```yaml
services:
  opensearch:
    image: opensearchproject/opensearch:3
    container_name: opensearch
    environment:
      discovery.type: "single-node"
      OPENSEARCH_JAVA_OPTS: "-Xms512m -Xmx512m"
      OPENSEARCH_INITIAL_ADMIN_PASSWORD: "OpenSearchTest123!"
    ports:
      - "9200:9200"
      - "9600:9600"
    volumes:
      - opensearch_data:/usr/share/opensearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -k -u admin:OpenSearchTest123! https://localhost:9200 >/dev/null 2>&1 || exit 1"]
      interval: 20s
      timeout: 10s
      retries: 20

  opensearch-dashboards:
    image: opensearchproject/opensearch-dashboards:3
    container_name: opensearch-dashboards
    depends_on:
      opensearch:
        condition: service_healthy
    volumes:
      - ./opensearch_dashboards.yml:/usr/share/opensearch-dashboards/config/opensearch_dashboards.yml:ro
    ports:
      - "5601:5601"

  rag-api:
    build:
      context: ./rag_api
    container_name: rag-api
    depends_on:
      opensearch:
        condition: service_healthy
    environment:
      INDEX_NAME: ovf-docs
      OPENSEARCH_MODEL_ID: "${OPENSEARCH_MODEL_ID}"
      HYBRID_SEARCH_PIPELINE: ovf-hybrid-pipeline

      OPENSEARCH_HOST: opensearch
      OPENSEARCH_PORT: 9200
      OPENSEARCH_USER: admin
      OPENSEARCH_PASSWORD: OpenSearchTest123!
      OPENSEARCH_USE_SSL: "true"
      OPENSEARCH_VERIFY_CERTS: "false"

      OLLAMA_HOST: http://ollama:11434
      OLLAMA_CHAT_MODEL: gemma3:12b

      DEFAULT_RETRIEVER: semantic
      DEFAULT_TOP_K: 8
      PORT: 8000
    ports:
      - "8000:8000"

volumes:
  opensearch_data:
```

---

## Chapter 3: Fresh build before Assistant setup

Use this chapter if building from scratch rather than restoring a saved Docker volume.

### 3.1 Start Docker services

```bash
docker compose up -d
```

Check OpenSearch:

```bash
curl -k -u admin:OpenSearchTest123! https://localhost:9200
```

### 3.2 Create the embedding model group

Run in OpenSearch Dev Tools:

```json
POST /_plugins/_ml/model_groups/_register
{
  "name": "ovf-local-model-group",
  "description": "Model group for OVF local embedding models",
  "access_mode": "public"
}
```

### 3.3 Register the embedding model

Run in Dev Tools:

```json
POST /_plugins/_ml/models/_register
{
  "name": "huggingface/sentence-transformers/msmarco-distilbert-base-tas-b",
  "version": "1.0.0",
  "description": "OVF embedding model",
  "model_group_id": "j65qaJ0BqfEK-3L2xPN7",
  "model_format": "TORCH_SCRIPT",
  "function_name": "TEXT_EMBEDDING"
}
```

Check registration tasks:

```json
GET /_plugins/_ml/tasks/_search
{
  "query": {
    "term": {
      "task_type": "REGISTER_MODEL"
    }
  },
  "size": 20,
  "sort": [
    {
      "create_time": {
        "order": "desc"
      }
    }
  ]
}
```

### 3.4 Deploy the embedding model

```json
POST /_plugins/_ml/models/l65saJ0BqfEK-3L2OfNU/_deploy
```

Check the model state:

```json
GET /_plugins/_ml/models/l65saJ0BqfEK-3L2OfNU
```

The goal is:

```text
model_state = DEPLOYED
```

### 3.5 Create the Ollama chat model group

```json
POST /_plugins/_ml/model_groups/_register
{
  "name": "ovf-ollama-chat-group",
  "description": "Model group for local Ollama chat model",
  "access_mode": "public"
}
```

### 3.6 Register the remote Ollama model

```json
POST /_plugins/_ml/models/_register
{
  "name": "ollama-gemma3-chat",
  "function_name": "REMOTE",
  "description": "Local Ollama chat model for Assistant",
  "model_group_id": "oK6paJ0BqfEK-3L2zvNs",
  "connector": {
    "name": "Ollama Chat Connector",
    "description": "Connector to local Ollama /api/generate",
    "version": "1",
    "protocol": "http",
    "parameters": {
      "endpoint": "host.docker.internal:11434",
      "model": "gemma3:12b"
    },
    "actions": [
      {
        "action_type": "PREDICT",
        "method": "POST",
        "url": "http://${parameters.endpoint}/api/generate",
        "headers": {
          "Content-Type": "application/json"
        },
        "request_body": "{ \"model\": \"${parameters.model}\", \"prompt\": \"${parameters.prompt}\", \"stream\": false }"
      }
    ]
  }
}
```

### 3.7 Deploy the remote Ollama model

```json
POST /_plugins/_ml/models/oq6uaJ0BqfEK-3L2YvPL/_deploy
```

Check the model state:

```json
GET /_plugins/_ml/models/oq6uaJ0BqfEK-3L2YvPL
```

### 3.8 Verify Ollama is running

```bash
curl http://localhost:11434/api/tags
```

### 3.9 Create the OVF ingest pipeline and index, then ingest data

Run your two Python files in this order:

```bash
python create_index.py
python ingest_sections.py
```

### 3.10 Verify the OVF data is loaded

```bash
curl -k -u admin:OpenSearchTest123! https://localhost:9200/ovf-docs/_count
```

Expected result in the original working system:

```text
count = 313
```

---

## Chapter 4: Assistant and agent setup

### 4.1 Enable the OpenSearch agent framework

Run in Dev Tools:

```json
PUT _cluster/settings
{
  "persistent": {
    "plugins.ml_commons.agent_framework_enabled": true
  }
}
```

### 4.2 Allow model execution on the current node and bypass the ML memory blocker

```json
PUT _cluster/settings
{
  "persistent": {
    "plugins.ml_commons.only_run_on_ml_node": false,
    "plugins.ml_commons.native_memory_threshold": 100
  }
}
```

### 4.3 Enable the RAG feature flag

```json
PUT _cluster/settings
{
  "persistent": {
    "plugins.ml_commons.rag_pipeline_feature_enabled": true
  }
}
```

### 4.4 Check models

```json
GET /_plugins/_ml/models/_search
{
  "query": {
    "match_all": {}
  },
  "size": 20
}
```

Check non-embedding models:

```json
GET /_plugins/_ml/models/_search
{
  "query": {
    "bool": {
      "must_not": [
        {
          "term": {
            "algorithm": "TEXT_EMBEDDING"
          }
        }
      ]
    }
  },
  "size": 50
}
```

In the working setup:
- embedding model ID: `l65saJ0BqfEK-3L2OfNU`
- remote LLM model ID: `oq6uaJ0BqfEK-3L2YvPL`

### 4.5 Register the conversational OVF RAG agent

```json
POST /_plugins/_ml/agents/_register
{
  "name": "OVF Chat Agent with RAG",
  "type": "conversational",
  "description": "Answers questions over OVF chunks using semantic retrieval",
  "llm": {
    "model_id": "oq6uaJ0BqfEK-3L2YvPL",
    "parameters": {
      "max_iteration": 5,
      "response_filter": "$.response"
    }
  },
  "memory": {
    "type": "conversation_index"
  },
  "tools": [
    {
      "type": "VectorDBTool",
      "name": "ovf_knowledge_base",
      "description": "Semantic retrieval over OVF chunks",
      "parameters": {
        "input": "${parameters.question}",
        "index": "ovf-docs",
        "source_field": ["chunk_text"],
        "model_id": "l65saJ0BqfEK-3L2OfNU",
        "embedding_field": "embedding",
        "doc_size": 5
      }
    }
  ],
  "app_type": "chat_with_rag"
}
```

Expected working agent ID:

```text
q1ODiJ0B83izHxg-Ys3B
```

### 4.6 Test the OVF chat agent directly

```json
POST /_plugins/_ml/agents/q1ODiJ0B83izHxg-Ys3B/_execute
{
  "parameters": {
    "question": "Who is responsible for information management?",
    "verbose": true
  }
}
```

This confirms:
- retrieval from `ovf-docs`
- use of `VectorDBTool`
- final answer generation through the Ollama remote model

### 4.7 Register the root chatbot agent for Dashboards Assistant

```json
POST /_plugins/_ml/agents/_register
{
  "name": "OVF Root Chatbot Agent",
  "type": "flow",
  "description": "Root assistant agent for OVF",
  "tools": [
    {
      "type": "AgentTool",
      "name": "LLMResponseGenerator",
      "parameters": {
        "agent_id": "q1ODiJ0B83izHxg-Ys3B"
      },
      "include_output_in_agent_response": true
    }
  ],
  "memory": {
    "type": "conversation_index"
  }
}
```

Expected working root agent ID:

```text
ulOFiJ0B83izHxg-M80I
```

### 4.8 Try to point Dashboards Assistant to the root agent

This usually fails in Dev Tools on a secured cluster:

```json
PUT /.plugins-ml-config/_doc/os_chat
{
  "type": "os_chat_root_agent",
  "configuration": {
    "agent_id": "ulOFiJ0B83izHxg-M80I"
  }
}
```

Expected error:

```text
403 security_exception
```

### 4.9 Set `os_chat` using the super-admin certificate inside the OpenSearch container

From the host:

```bash
docker exec -it opensearch bash
```

Then inside the container:

```bash
curl -k --cert config/kirk.pem --key config/kirk-key.pem   -H "Content-Type: application/json"   -X PUT "https://localhost:9200/.plugins-ml-config/_doc/os_chat"   -d '{
    "type": "os_chat_root_agent",
    "configuration": {
      "agent_id": "ulOFiJ0B83izHxg-M80I"
    }
  }'
```

### 4.10 Restart Dashboards

```bash
docker compose restart opensearch-dashboards
```

Then open:

```text
http://localhost:5601
```

---

## Chapter 5: Export the OpenSearch Docker volume

### 5.1 Find the volume used by OpenSearch

```bash
docker inspect opensearch --format '{{range .Mounts}}{{println .Name "->" .Destination}}{{end}}'
```

In the working OVF setup, the OpenSearch data volume was:

```text
ovf_opensearch_data -> /usr/share/opensearch/data
```

### 5.2 Stop the stack before exporting

```bash
docker compose down
```

### 5.3 Export the volume to a tar.gz backup

```bash
docker run --rm   -v ovf_opensearch_data:/volume   -v $(pwd):/backup   alpine   sh -c "cd /volume && tar czf /backup/ovf_opensearch_data_backup.tar.gz ."
```

Check the backup file:

```bash
ls -lh ovf_opensearch_data_backup.tar.gz
```

---

## Chapter 6: Restore the OpenSearch volume on another machine

Use this chapter when you already have:
- the `ovf` project folder
- the `.env`
- the Docker volume backup tar
- Docker installed

### 6.1 Start Ollama in Docker

```bash
docker run -d   --name ollama   -p 11434:11434   -v ollama:/root/.ollama   ollama/ollama
```

### 6.2 Pull the model inside Ollama

```bash
docker exec -it ollama ollama pull gemma3:12b
```

Verify Ollama:

```bash
curl http://localhost:11434/api/tags
```

### 6.3 Create the OpenSearch volume

```bash
docker volume create ovf_opensearch_data
```

### 6.4 Restore the tar backup into the volume

From inside the `ovf` folder:

```bash
docker run --rm   -v ovf_opensearch_data:/volume   -v $(pwd):/backup   alpine   sh -c "cd /volume && tar xzf /backup/ovf_opensearch_data_backup.tar.gz"
```

### 6.5 Start the OVF stack

```bash
docker compose up -d
```

This pulls and starts:
- OpenSearch
- OpenSearch Dashboards
- `rag-api`

### 6.6 Verify OpenSearch

```bash
curl -k -u admin:OpenSearchTest123! https://localhost:9200
```

### 6.7 Verify the restored data

```bash
curl -k -u admin:OpenSearchTest123! https://localhost:9200/ovf-docs/_count
```

Expected result from the restored working system:

```text
count = 313
```

### 6.8 Verify the restored models

```bash
curl -k -u admin:OpenSearchTest123!   https://localhost:9200/_plugins/_ml/models/l65saJ0BqfEK-3L2OfNU
```

```bash
curl -k -u admin:OpenSearchTest123!   https://localhost:9200/_plugins/_ml/models/oq6uaJ0BqfEK-3L2YvPL
```

### 6.9 Verify the restored agents

```bash
curl -k -u admin:OpenSearchTest123!   https://localhost:9200/_plugins/_ml/agents/q1ODiJ0B83izHxg-Ys3B
```

```bash
curl -k -u admin:OpenSearchTest123!   https://localhost:9200/_plugins/_ml/agents/ulOFiJ0B83izHxg-M80I
```

### 6.10 Verify the Dashboards Assistant root config

From the host:

```bash
docker exec -it opensearch bash
```

Then inside the container:

```bash
curl -k --cert config/kirk.pem --key config/kirk-key.pem   https://localhost:9200/.plugins-ml-config/_doc/os_chat
```

Expected result:

```json
{
  "_source": {
    "type": "os_chat_root_agent",
    "configuration": {
      "agent_id": "ulOFiJ0B83izHxg-M80I"
    }
  }
}
```

If missing, restore it manually:

```bash
curl -k --cert config/kirk.pem --key config/kirk-key.pem   -H "Content-Type: application/json"   -X PUT "https://localhost:9200/.plugins-ml-config/_doc/os_chat"   -d '{
    "type": "os_chat_root_agent",
    "configuration": {
      "agent_id": "ulOFiJ0B83izHxg-M80I"
    }
  }'
```

### 6.11 Restart Dashboards

```bash
docker compose restart opensearch-dashboards
```

Then open:

```text
http://localhost:5601
```

---

## Chapter 7: Important note about memory on smaller machines

On a smaller machine, the system may restore correctly but fail during answer generation if `gemma3:12b` is too large.

Example error:

```text
Agent execution failed: Error from remote service: {"error":"model requires more system memory (9.2 GiB) than is available (8.1 GiB)"}
```

This means:
- OpenSearch is fine
- the index is fine
- the agents are fine
- retrieval is fine
- but the Ollama model is too large for the machine

### 7.1 Pull a smaller model

```bash
docker exec -it ollama ollama pull gemma3:4b
```

### 7.2 Update the remote model configuration

The clean fix is to register a new remote Ollama model that points to:

```text
gemma3:4b
```

and then update the OVF chat agent to use the new remote model ID.

---

## Chapter 8: Final verification checklist

### 8.1 OpenSearch is up

```bash
curl -k -u admin:OpenSearchTest123! https://localhost:9200
```

### 8.2 Index exists

```bash
curl -k -u admin:OpenSearchTest123! https://localhost:9200/ovf-docs/_count
```

### 8.3 Embedding model is deployed

```bash
curl -k -u admin:OpenSearchTest123!   https://localhost:9200/_plugins/_ml/models/l65saJ0BqfEK-3L2OfNU
```

### 8.4 Remote Ollama model is deployed

```bash
curl -k -u admin:OpenSearchTest123!   https://localhost:9200/_plugins/_ml/models/oq6uaJ0BqfEK-3L2YvPL
```

### 8.5 OVF agents exist

```bash
curl -k -u admin:OpenSearchTest123!   https://localhost:9200/_plugins/_ml/agents/q1ODiJ0B83izHxg-Ys3B
```

```bash
curl -k -u admin:OpenSearchTest123!   https://localhost:9200/_plugins/_ml/agents/ulOFiJ0B83izHxg-M80I
```

### 8.6 `os_chat` points to the root agent

```bash
docker exec -it opensearch bash
```

Then:

```bash
curl -k --cert config/kirk.pem --key config/kirk-key.pem   https://localhost:9200/.plugins-ml-config/_doc/os_chat
```

### 8.7 Ollama is available

```bash
curl http://localhost:11434/api/tags
```

### 8.8 Dashboards is reachable

Open:

```text
http://localhost:5601
```

---

## Chapter 9: Notes

- The final OVF system uses the native OpenSearch agent flow with `VectorDBTool`.
- Older connector-based `rag-api` agents may still exist in the cluster, but the final OVF Assistant flow uses:
  - OVF Chat Agent with RAG
  - OVF Root Chatbot Agent
  - `os_chat` pointing to the OVF root agent
- When restoring from a saved Docker volume, you usually do not need to rerun:
  - `python create_index.py`
  - `python ingest_sections.py`
  unless the restored data is missing or corrupted.
