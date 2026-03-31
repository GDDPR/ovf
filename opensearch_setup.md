## OpenSearch setup from scratch

Use this section only if you want to build the OpenSearch side from scratch instead of restoring `opensearch_data_backup.tar.gz`.

### 1. Start with a blank OpenSearch cluster

Make sure OpenSearch and OpenSearch Dashboards are running:

```bash
docker compose up -d
```

### 2. Open Dev Tools in OpenSearch Dashboards

Open OpenSearch Dashboards in your browser:

```text
http://localhost:5601
```

Then go to **Dev Tools**.

---

### 3. Allow ML models to run on this local cluster

Enter this in Dev Tools:

```http
PUT _cluster/settings
{
  "persistent": {
    "plugins.ml_commons.only_run_on_ml_node": "false"
  }
}
```

You should get a response showing that `only_run_on_ml_node` is now set to `false`.

---

### 4. Register and deploy the embedding model

Enter this in Dev Tools:

```http
POST /_plugins/_ml/models/_register?deploy=true
{
  "name": "huggingface/sentence-transformers/msmarco-distilbert-base-tas-b",
  "version": "1.0.3",
  "model_format": "TORCH_SCRIPT"
}
```

This will return a `task_id`.

---

### 5. Check the model registration task

Replace `YOUR_TASK_ID` with the `task_id` from the previous step:

```http
GET /_plugins/_ml/tasks/YOUR_TASK_ID
```

Keep checking until the response shows:

```json
"state": "COMPLETED"
```

When it is complete, copy the returned `model_id`.

---

### 6. Verify the model

Replace `YOUR_MODEL_ID` with the `model_id` from the completed task:

```http
GET /_plugins/_ml/models/YOUR_MODEL_ID
```

---

### 7. Create the ingest pipeline

Replace `YOUR_MODEL_ID` with the same `model_id`:

```http
PUT /_ingest/pipeline/ovf-ingest-pipeline
{
  "description": "Generate embeddings for OVF chunks",
  "processors": [
    {
      "text_embedding": {
        "model_id": "YOUR_MODEL_ID",
        "field_map": {
          "chunk_text": "embedding"
        }
      }
    }
  ]
}
```

---

### 8. Create the `ovf-docs` index

Enter this in Dev Tools:

```http
PUT /ovf-docs
{
  "settings": {
    "index": {
      "knn": true,
      "default_pipeline": "ovf-ingest-pipeline"
    }
  },
  "mappings": {
    "properties": {
      "title": {
        "type": "text"
      },
      "section": {
        "type": "text"
      },
      "chunk_text": {
        "type": "text"
      },
      "url": {
        "type": "keyword"
      },
      "entities": {
        "type": "object",
        "enabled": false
      },
      "embedding": {
        "type": "knn_vector",
        "dimension": 768,
        "space_type": "innerproduct",
        "method": {
          "name": "hnsw",
          "engine": "lucene",
          "parameters": {
            "ef_construction": 100,
            "m": 16
          }
        }
      }
    }
  }
}
```

---

### 9. Create the hybrid search pipeline

Enter this in Dev Tools:

```http
PUT /_search/pipeline/ovf-hybrid-pipeline
{
  "description": "Pipeline for hybrid search",
  "phase_results_processors": [
    {
      "normalization-processor": {
        "normalization": {
          "technique": "min_max"
        },
        "combination": {
          "technique": "arithmetic_mean",
          "parameters": {
            "weights": [0.5, 0.5]
          }
        }
      }
    }
  ]
}
```

---

### 10. Verify the OpenSearch objects

Verify the ingest pipeline:

```http
GET /_ingest/pipeline/ovf-ingest-pipeline
```

Verify the hybrid pipeline:

```http
GET /_search/pipeline/ovf-hybrid-pipeline
```

Verify the index:

```http
GET /ovf-docs
```

---

### 11. Update the `.env` file

Set `OPENSEARCH_MODEL_ID` to the `model_id` returned in Step 5.

Your `.env` should look like this:

```env
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_MODEL_ID=PASTE_MODEL_ID_HERE

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

---

### 12. Run the Python setup and ingestion code

From the project root, run:

```bash
python src/ingest/create_index.py
python src/ingest/ingest_sections.py
```

Then start the application:

```bash
python src/rag/ask.py
```

---

### 13. Optional verification queries

After ingestion, verify that documents exist:

```http
GET /ovf-docs/_search
{
  "size": 3,
  "_source": ["title", "section", "chunk_text", "url"],
  "query": {
    "match_all": {}
  }
}
```

Test semantic search:

```http
GET /ovf-docs/_search
{
  "_source": ["title", "section", "chunk_text", "url"],
  "query": {
    "neural": {
      "embedding": {
        "query_text": "responsibilities of ADM",
        "model_id": "YOUR_MODEL_ID",
        "k": 5
      }
    }
  }
}
```

Test hybrid search:

```http
GET /ovf-docs/_search?search_pipeline=ovf-hybrid-pipeline
{
  "_source": ["title", "section", "chunk_text", "url"],
  "query": {
    "hybrid": {
      "queries": [
        {
          "multi_match": {
            "query": "responsibilities of ADM",
            "fields": ["title^3", "section^2", "chunk_text"]
          }
        },
        {
          "neural": {
            "embedding": {
              "query_text": "responsibilities of ADM",
              "model_id": "YOUR_MODEL_ID",
              "k": 5
            }
          }
        }
      ]
    }
  }
}
```

---

### Notes

- The `model_id` will be different every time you register the model on a fresh cluster.
- You must update `OPENSEARCH_MODEL_ID` in `.env` to match the newly created model.
- The hybrid retriever depends on `ovf-hybrid-pipeline`, so hybrid search will fail if that pipeline is missing.
- The semantic retriever and hybrid retriever both use the `embedding` field in the `ovf-docs` index.
- If OpenSearch is reset, you must recreate the model, pipelines, and index before re-ingesting documents.