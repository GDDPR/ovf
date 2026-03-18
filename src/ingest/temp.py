import os

from dotenv import load_dotenv
from opensearchpy import OpenSearch

load_dotenv()

INDEX_NAME = os.getenv("INDEX_NAME", "daod_sections")


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


def main() -> None:
    client = get_client()

    if client.indices.exists(index=INDEX_NAME):
        response = client.indices.delete(index=INDEX_NAME)
        print(f"Deleted index: {INDEX_NAME}")
        print(response)
    else:
        print(f"Index does not exist: {INDEX_NAME}")


if __name__ == "__main__":
    main()