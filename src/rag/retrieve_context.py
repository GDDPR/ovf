import os
import requests
from dotenv import load_dotenv
from opensearchpy import OpenSearch

load_dotenv()

INDEX_NAME = os.getenv("INDEX_NAME", "daod_sections")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
TOP_K = int(os.getenv("TOP_K"))


def get_opensearch_client() -> OpenSearch:
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


def get_query_embedding(query_text: str) -> list[float]:
    response = requests.post(
        f"{OLLAMA_HOST}/api/embed",
        json={
            "model": OLLAMA_EMBED_MODEL,
            "input": query_text,
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()

    embeddings = data.get("embeddings", [])
    if not embeddings or not embeddings[0]:
        raise RuntimeError("Ollama returned no query embedding.")

    return embeddings[0]


def retrieve_context(query_text: str, top_k: int = TOP_K) -> list[dict]:
    client = get_opensearch_client()
    query_embedding = get_query_embedding(query_text)

    body = {
        "size": top_k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_embedding,
                    "k": top_k
                }
            }
        }
    }

    response = client.search(index=INDEX_NAME, body=body)
    hits = response.get("hits", {}).get("hits", [])

    results = []
    for hit in hits:
        source = hit.get("_source", {})
        results.append(
            {
                "score": hit.get("_score", 0),
                "title": source.get("title", ""),
                "section": source.get("section", ""),
                "chunk_text": source.get("chunk_text", ""),
                "url": source.get("url", ""),
                "entities": source.get("entities", None),
            }
        )

    return results