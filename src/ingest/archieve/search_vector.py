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


def main() -> None:
    query_text = input("Enter semantic search query: ").strip()
    if not query_text:
        print("No query entered.")
        return

    query_embedding = get_query_embedding(query_text)
    client = get_client()

    body = {
        "size": 5,
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_embedding,
                    "k": 5
                }
            }
        }
    }

    response = client.search(index=INDEX_NAME, body=body)
    hits = response.get("hits", {}).get("hits", [])

    print(f"\nFound {len(hits)} result(s):\n")

    for i, hit in enumerate(hits, start=1):
        source = hit.get("_source", {})
        score = hit.get("_score", 0)

        print(f"Result {i}")
        print(f"Score:   {score}")
        print(f"Title:   {source.get('title', '')}")
        print(f"Section: {source.get('section', '')}")
        print(f"URL:     {source.get('url', '')}")
        print(f"Entities:{source.get('entities', None)}")
        print(f"Text:    {source.get('chunk_text', '')[:500]}")
        print("-" * 80)


if __name__ == "__main__":
    main()