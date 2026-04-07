import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from opensearchpy import OpenSearch
from opensearchpy.exceptions import TransportError

load_dotenv()

INDEX_NAME = os.getenv("INDEX_NAME", "ovf-docs")
INPUT_DIR = os.getenv("INPUT_DIR", "./data/docs_json")

# Keep whole section as one chunk unless it exceeds this threshold.
MAX_WORDS_PER_CHUNK = int(os.getenv("MAX_WORDS_PER_CHUNK", "350"))
CHUNK_OVERLAP_WORDS = int(os.getenv("CHUNK_OVERLAP_WORDS", "50"))

# Slow ingestion a bit so ML inference does not trip the memory circuit breaker.
INDEX_SLEEP_SECONDS = float(os.getenv("INDEX_SLEEP_SECONDS", "0.15"))
MAX_RETRIES_429 = int(os.getenv("MAX_RETRIES_429", "8"))
RETRY_SLEEP_SECONDS = float(os.getenv("RETRY_SLEEP_SECONDS", "3.0"))


def get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_client() -> OpenSearch:
    host = os.getenv("OPENSEARCH_HOST", "localhost")
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


def first_nonempty_str(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def normalize_entities(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    return {"raw": str(value)}


def extract_title(doc: dict[str, Any], section: dict[str, Any]) -> str:
    return first_nonempty_str(
        doc.get("title"),
        section.get("title"),
        doc.get("document_title"),
        doc.get("name"),
    )


def extract_url(doc: dict[str, Any], section: dict[str, Any]) -> str:
    return first_nonempty_str(
        section.get("url"),
        doc.get("url"),
        doc.get("canonical_url"),
        doc.get("source_url"),
    )


def extract_section_title(section: dict[str, Any]) -> str:
    return first_nonempty_str(
        section.get("section"),
        section.get("heading"),
        section.get("name"),
    )


def extract_section_text(section: dict[str, Any]) -> str:
    return first_nonempty_str(
        section.get("chunk_text"),
        section.get("text"),
        section.get("content"),
        section.get("body"),
    )


def split_only_if_too_big(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []

    words = text.split()

    # Keep the whole section as one chunk if it fits.
    if len(words) <= MAX_WORDS_PER_CHUNK:
        return [text]

    # Only split because it is too big.
    chunks: list[str] = []
    start = 0

    while start < len(words):
        end = min(start + MAX_WORDS_PER_CHUNK, len(words))
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words).strip()

        if chunk_text:
            chunks.append(chunk_text)

        if end >= len(words):
            break

        start = end - CHUNK_OVERLAP_WORDS
        if start < 0:
            start = 0

    return chunks


def build_chunk_doc(
    parent_doc: dict[str, Any],
    section: dict[str, Any],
    chunk_text: str,
) -> dict[str, Any]:
    return {
        "title": extract_title(parent_doc, section),
        "section": extract_section_title(section),
        "chunk_text": chunk_text,
        "url": extract_url(parent_doc, section),
        "entities": normalize_entities(
            section.get("entities", parent_doc.get("entities"))
        ),
    }


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
        with file_path.open("r", encoding="utf-8") as f:
            doc = json.load(f)

        sections = doc.get("sections", [])
        if not sections:
            print(f"No sections found in {file_path.name}")
            continue

        indexed_in_file = 0

        for section_idx, section in enumerate(sections):
            section_text = extract_section_text(section)
            if not section_text:
                continue

            chunks = split_only_if_too_big(section_text)

            # Usually this will be length 1.
            for chunk_idx, chunk_text in enumerate(chunks):
                chunk_doc = build_chunk_doc(doc, section, chunk_text)

                if len(chunks) == 1:
                    doc_id = f"{file_path.stem}-{section_idx}"
                else:
                    doc_id = f"{file_path.stem}-{section_idx}-{chunk_idx}"

                success = False

                for attempt in range(MAX_RETRIES_429 + 1):
                    try:
                        client.index(index=INDEX_NAME, id=doc_id, body=chunk_doc)
                        indexed_in_file += 1
                        total_indexed += 1
                        success = True
                        break

                    except TransportError as e:
                        status_code = getattr(e, "status_code", None)
                        info = getattr(e, "info", None)

                        is_memory_breaker = (
                            status_code == 429
                            and isinstance(info, dict)
                            and info.get("error", {}).get("type") == "circuit_breaking_exception"
                        )

                        if is_memory_breaker and attempt < MAX_RETRIES_429:
                            print(
                                f"429 memory breaker on {doc_id}. "
                                f"Retrying in {RETRY_SLEEP_SECONDS} seconds "
                                f"({attempt + 1}/{MAX_RETRIES_429})..."
                            )
                            time.sleep(RETRY_SLEEP_SECONDS)
                            continue

                        print("\n--- INDEXING ERROR ---")
                        print(f"File: {file_path.name}")
                        print(f"Doc ID: {doc_id}")
                        print(f"Section index: {section_idx}")
                        print(f"Chunk index: {chunk_idx}")
                        print(f"Status code: {status_code}")
                        print(f"Error info: {info}")
                        print(f"Word count: {len(chunk_text.split())}")
                        print(f"Preview: {chunk_text[:500]}")
                        raise

                if success:
                    time.sleep(INDEX_SLEEP_SECONDS)

        print(f"Indexed {indexed_in_file} chunks from {file_path.name}")

    print(f"Done. Total indexed chunks: {total_indexed}")


if __name__ == "__main__":
    main()