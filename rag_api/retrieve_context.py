import os

from dotenv import load_dotenv
from opensearchpy import OpenSearch

load_dotenv()

INDEX_NAME = os.getenv("INDEX_NAME", "ovf-docs")
OPENSEARCH_MODEL_ID = os.getenv("OPENSEARCH_MODEL_ID")
TOP_K = int(os.getenv("TOP_K", "8"))


def get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_opensearch_client() -> OpenSearch:
    host = os.getenv("OPENSEARCH_HOST", "opensearch")
    port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    user = os.getenv("OPENSEARCH_USER", "admin")
    password = os.getenv("OPENSEARCH_PASSWORD", "")
    use_ssl = get_bool_env("OPENSEARCH_USE_SSL", True)
    verify_certs = get_bool_env("OPENSEARCH_VERIFY_CERTS", False)

    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_auth=(user, password),
        use_ssl=use_ssl,
        verify_certs=verify_certs,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )


def retrieve_context(query_text: str, top_k: int = TOP_K) -> list[dict]:
    client = get_opensearch_client()

    body = {
        "size": top_k,
        "_source": ["title", "section", "chunk_text", "url", "entities"],
        "query": {
            "neural": {
                "embedding": {
                    "query_text": query_text,
                    "model_id": OPENSEARCH_MODEL_ID,
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