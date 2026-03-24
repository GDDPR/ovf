import os
import requests
from dotenv import load_dotenv
from opensearchpy import OpenSearch

load_dotenv()

INDEX_NAME = os.getenv("INDEX_NAME", "daod_sections")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")


def get_client() -> OpenSearch:
    host = os.getenv("OPENSEARCH_HOST", "localhost")
    port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    user = os.getenv("OPENSEARCH_USER", "admin")
    password = os.getenv("OPENSEARCH_PASSWORD", "OpenSearchTest123!")

    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_auth=(user, password),
        use_ssl=True,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )


def get_embedding_dimension() -> int:
    response = requests.post(
        f"{OLLAMA_HOST}/api/embed",
        json={
            "model": OLLAMA_EMBED_MODEL,
            "input": "dimension probe",
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()

    embeddings = data.get("embeddings", [])
    if not embeddings or not embeddings[0]:
        raise RuntimeError("Ollama returned no embedding for dimension probe.")

    return len(embeddings[0])


def main() -> None:
    client = get_client()

    if client.indices.exists(index=INDEX_NAME):
        print(f"Index already exists: {INDEX_NAME}")
        return

    embedding_dim = get_embedding_dimension()
    print(f"Detected embedding dimension: {embedding_dim}")

    body = {
        "settings": {
            "index": {
                "knn": True
            }
        },
        "mappings": {
            "properties": {
                "title": {"type": "text"},
                "section": {"type": "text"},
                "chunk_text": {"type": "text"},
                "url": {"type": "keyword"},
                "entities": {"type": "keyword"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": embedding_dim,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "lucene"
                    }
                }
            }
        }
    }

    response = client.indices.create(index=INDEX_NAME, body=body)
    print(f"Created index: {INDEX_NAME}")
    print(response)


if __name__ == "__main__":
    main()