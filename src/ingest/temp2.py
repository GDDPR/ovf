'''
checks whether your OpenSearch index is cleared
'''
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

    exists = client.indices.exists(index=INDEX_NAME)
    print(f"Index exists: {exists}")

    if exists:
        count_resp = client.count(index=INDEX_NAME)
        count = count_resp.get("count", 0)
        print(f"Document count: {count}")

        if count == 0:
            print(f"Index {INDEX_NAME} exists but is empty.")
        else:
            print(f"Index {INDEX_NAME} is not cleared.")
    else:
        print(f"Index {INDEX_NAME} does not exist, so it is cleared.")


if __name__ == "__main__":
    main()