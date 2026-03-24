import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

INPUT_DIR = "./data/docs_json"
OUTPUT_DIR = "./data/docs_json_embedded"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# character-based fallback split for oversized sections
MAX_CHARS = 4000
OVERLAP_CHARS = 400


def write_pretty_json(out_dir: str, filename: str, doc: dict) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)

    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    os.replace(tmp_path, path)
    return path


def clean_text(text: str) -> str:
    text = text or ""
    text = " ".join(text.split())
    return text.strip()


def get_embeddings(texts: list[str]) -> list[list[float]]:
    response = requests.post(
        f"{OLLAMA_HOST}/api/embed",
        json={
            "model": OLLAMA_EMBED_MODEL,
            "input": texts,
            "truncate": True,
        },
        timeout=300,
    )
    response.raise_for_status()
    data = response.json()

    embeddings = data.get("embeddings", [])
    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"Expected {len(texts)} embeddings, got {len(embeddings)}."
        )

    return embeddings


def get_single_embedding(text: str) -> list[float]:
    response = requests.post(
        f"{OLLAMA_HOST}/api/embed",
        json={
            "model": OLLAMA_EMBED_MODEL,
            "input": text,
            "truncate": True,
        },
        timeout=300,
    )
    response.raise_for_status()
    data = response.json()

    embeddings = data.get("embeddings", [])
    if not embeddings or not embeddings[0]:
        raise RuntimeError("No embedding returned for single text.")

    return embeddings[0]


def split_text_by_chars(text: str, max_chars: int = MAX_CHARS, overlap_chars: int = OVERLAP_CHARS) -> list[str]:
    text = clean_text(text)
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + max_chars, text_len)

        if end < text_len:
            split_at = text.rfind(" ", start, end)
            if split_at > start + max_chars // 2:
                end = split_at

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        start = max(end - overlap_chars, start + 1)

    return chunks


def try_embed_section(section: dict, filename: str, section_num: int) -> list[dict]:
    text = clean_text(section.get("chunk_text", ""))
    if not text:
        return []

    base_doc = {
        "title": section.get("title", ""),
        "section": section.get("section", ""),
        "url": section.get("url", ""),
        "entities": section.get("entities", None),
    }

    try:
        embedding = get_single_embedding(text)
        return [
            {
                **base_doc,
                "chunk_text": text,
                "embedding": embedding,
                "part": 1,
                "total_parts": 1,
            }
        ]
    except requests.HTTPError as e:
        response_text = e.response.text if e.response is not None else ""
        if "context length" not in response_text.lower():
            print(f"\nFailed section {section_num} in {filename}")
            print(f"Section title: {base_doc['section']}")
            print(f"Text length: {len(text)}")
            print("Response body:")
            print(response_text)
            return []

        print(f"\nOversized section detected in {filename}")
        print(f"Section {section_num}: {base_doc['section']}")
        print(f"Original length: {len(text)}")
        print("Splitting into smaller chunks...")

        parts = split_text_by_chars(text)
        out_docs: list[dict] = []

        for i, part_text in enumerate(parts, start=1):
            try:
                part_embedding = get_single_embedding(part_text)
                out_docs.append(
                    {
                        **base_doc,
                        "chunk_text": part_text,
                        "embedding": part_embedding,
                        "part": i,
                        "total_parts": len(parts),
                    }
                )
            except requests.HTTPError as part_e:
                print(f"Failed split part {i}/{len(parts)} for section {section_num} in {filename}")
                if part_e.response is not None:
                    print(part_e.response.text)

        print(f"Created {len(out_docs)} embedded split part(s)")
        return out_docs


def main() -> None:
    input_path = Path(INPUT_DIR)
    if not input_path.exists():
        print(f"Directory not found: {INPUT_DIR}")
        return

    files = sorted(input_path.glob("*.json"))
    if not files:
        print(f"No JSON files found in {INPUT_DIR}")
        return

    total_embedded_docs = 0

    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            doc = json.load(f)

        sections = doc.get("sections", [])
        if not sections:
            continue

        embedded_sections: list[dict] = []

        for idx, section in enumerate(sections, start=1):
            section = {
                "title": section.get("title", ""),
                "section": section.get("section", ""),
                "chunk_text": clean_text(section.get("chunk_text", "")),
                "url": section.get("url", ""),
                "entities": section.get("entities", None),
            }

            embedded_docs = try_embed_section(section, file_path.name, idx)
            embedded_sections.extend(embedded_docs)

        out_doc = {
            "id": doc.get("id", ""),
            "url": doc.get("url", ""),
            "canonical_url": doc.get("canonical_url", ""),
            "title": doc.get("title", ""),
            "retrieved_at": doc.get("retrieved_at", ""),
            "embedded_sections": embedded_sections,
        }

        out_path = write_pretty_json(OUTPUT_DIR, file_path.name, out_doc)
        total_embedded_docs += len(embedded_sections)

        print(f"Embedded {len(embedded_sections)} section doc(s) from {file_path.name}")
        print(f"Saved: {out_path}")

    print(f"Done. Total embedded section docs: {total_embedded_docs}")


if __name__ == "__main__":
    main()