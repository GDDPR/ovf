import json
import os
from pathlib import Path

from dotenv import load_dotenv
from opensearchpy import OpenSearch

load_dotenv()

INDEX_NAME = os.getenv("VECTOR_INDEX_NAME", "daod_sections")
INPUT_DIR = "./data/docs_json_embedded"


def get_client() -> OpenSearch:
    host = os.getenv("OPENSEARCH_HOST", "localhost")
    port = int(os.getenv("OPENSEARCH_PORT", "9200"))
    user = os.getenv("OPENSEARCH_USER", "admin")
    password = os.getenv("OPENSEARCH_PASSWORD", "OpenSearchTest123!")

    client = OpenSearch(
        hosts=[{"host": host, "port": port}],
        http_auth=(user, password),
        use_ssl=True,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )
    return client


def main() -> None:
    client = get_client()

    docs_path = Path(INPUT_DIR)
    if not docs_path.exists():
        print(f"Directory not found: {INPUT_DIR}")
        return

    files = sorted(docs_path.glob("*.json"))
    if not files:
        print(f"No JSON files found in {INPUT_DIR}")
        return

    total_indexed = 0

    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            doc = json.load(f)

        sections = doc.get("embedded_sections", [])
        if not sections:
            continue

        for section_doc in sections:
            client.index(index=INDEX_NAME, body=section_doc)
            total_indexed += 1

        print(f"Indexed {len(sections)} embedded sections from {file_path.name}")

    print(f"Done. Total indexed embedded sections: {total_indexed}")


if __name__ == "__main__":
    main()