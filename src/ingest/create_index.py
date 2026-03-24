import os

from dotenv import load_dotenv
from opensearchpy import OpenSearch

load_dotenv()

INDEX_NAME = os.getenv("INDEX_NAME", "ovf-docs")
PIPELINE_NAME = os.getenv("PIPELINE_NAME", "ovf-ingest-pipeline")
MODEL_ID = os.getenv("OPENSEARCH_MODEL_ID", "6YOZHZ0BTFNV0VBzOxVn")


def get_client() -> OpenSearch:
    host = os.getenv("OPENSEARCH_HOST", "localhost")
    port = int(os.getenv("OPENSEARCH_PORT", "9200"))

    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        use_ssl=False,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )


def create_pipeline(client: OpenSearch) -> None:
    body = {
        "description": "Generate embeddings for OVF chunks",
        "processors": [
            {
                "text_embedding": {
                    "model_id": MODEL_ID,
                    "field_map": {
                        "chunk_text": "embedding"
                    }
                }
            }
        ]
    }

    response = client.ingest.put_pipeline(id=PIPELINE_NAME, body=body)
    print(f"Created or updated pipeline: {PIPELINE_NAME}")
    print(response)


def create_index(client: OpenSearch) -> None:
    if client.indices.exists(index=INDEX_NAME):
        print(f"Index already exists: {INDEX_NAME}")
        return

    body = {
        "settings": {
            "index": {
                "knn": True,
                "default_pipeline": PIPELINE_NAME
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
                    "enabled": False
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

    response = client.indices.create(index=INDEX_NAME, body=body)
    print(f"Created index: {INDEX_NAME}")
    print(response)


def main() -> None:
    client = get_client()
    create_pipeline(client)
    create_index(client)


if __name__ == "__main__":
    main()