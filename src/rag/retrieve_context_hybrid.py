import os
from dotenv import load_dotenv
from opensearchpy import OpenSearch

load_dotenv()

INDEX_NAME = os.getenv("INDEX_NAME", "ovf-docs")
OPENSEARCH_MODEL_ID = os.getenv("OPENSEARCH_MODEL_ID", "6YOZHZ0BTFNV0VBzOxVn")
TOP_K = int(os.getenv("TOP_K", "8"))
HYBRID_SEARCH_PIPELINE = os.getenv("HYBRID_SEARCH_PIPELINE", "ovf-hybrid-pipeline")


def get_opensearch_client() -> OpenSearch:
    host = os.getenv("OPENSEARCH_HOST", "localhost")
    port = int(os.getenv("OPENSEARCH_PORT", "9200"))

    return OpenSearch(
        hosts=[{"host": host, "port": port}],
        use_ssl=False,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )


def retrieve_context(query_text: str, top_k: int = TOP_K) -> list[dict]:
    client = get_opensearch_client()

    body = {
        "size": top_k,
        "_source": ["title", "section", "chunk_text", "url", "entities"],
        "query": {
            "hybrid": {
                "queries": [
                    {
                        "multi_match": {
                            "query": query_text,
                            "fields": ["title^3", "section^2", "chunk_text"]
                        }
                    },
                    {
                        "neural": {
                            "embedding": {
                                "query_text": query_text,
                                "model_id": OPENSEARCH_MODEL_ID,
                                "k": top_k
                            }
                        }
                    }
                ]
            }
        }
    }

    response = client.search(
        index=INDEX_NAME,
        body=body,
        params={"search_pipeline": HYBRID_SEARCH_PIPELINE}
    )

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