import json
import os
import re
import time
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
from lxml import etree

from catalog_utils import update_status

CATALOG_PATH = "./data/catalog.xml"
OUT_JSON_DIR = "./data/docs_json"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^\w\-.]+", "_", name)
    return name[:120] or "doc"


def write_pretty_json(out_dir: str, doc: dict) -> str:
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{safe_filename(doc['id'])}.json"
    path = os.path.join(out_dir, filename)

    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    os.replace(tmp_path, path)
    return path


def load_catalog_items(xml_path: str) -> list[dict]:
    tree = etree.parse(xml_path)
    root = tree.getroot()

    items = []
    for item in root.findall("Item"):
        url_el = item.find("url")
        status_el = item.find("status")
        state_el = item.find("state")

        url = (url_el.text or "").strip() if url_el is not None else ""
        status = (status_el.text or "").strip() if status_el is not None else ""
        state = (state_el.text or "").strip() if state_el is not None else ""

        if url:
            items.append(
                {
                    "url": url,
                    "status": status,
                    "state": state,
                }
            )
    return items


def fetch_html(url: str, session: requests.Session) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (OVFParser)"}
    last_err: Exception | None = None

    for attempt in range(1, 5):
        try:
            response = session.get(url, headers=headers, timeout=25)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            last_err = e
            sleep_seconds = 1.5 * (2 ** (attempt - 1))
            time.sleep(sleep_seconds)

    raise last_err  # type: ignore


def extract_canonical_url(soup: BeautifulSoup, page_url: str) -> str:
    link = soup.find("link", rel=lambda v: v and "canonical" in v.lower())
    if link and link.get("href"):
        return urljoin(page_url, link["href"].strip())
    return page_url


def extract_title(soup: BeautifulSoup) -> str | None:
    meta = soup.find("meta", attrs={"name": "dcterms.title"})
    if meta and meta.get("content"):
        return meta["content"].strip()

    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(" ", strip=True)

    h1 = soup.find("h1")
    if h1:
        return h1.get_text(" ", strip=True)

    return None


def _is_within_main(tag: Tag, main: Tag) -> bool:
    cur = tag
    while cur is not None:
        if cur is main:
            return True
        cur = cur.parent  # type: ignore[assignment]
    return False


def extract_sections_from_main(soup: BeautifulSoup) -> list[dict]:
    main = soup.find("main") or soup.find("article") or soup.body
    if not main:
        return []

    for pd in main.find_all("section", class_=lambda c: c and "pagedetails" in str(c).split()):
        pd.decompose()

    h2s = [h for h in main.find_all("h2") if isinstance(h, Tag)]
    sections: list[dict] = []

    for h2 in h2s:
        if not _is_within_main(h2, main):
            continue

        section_title = h2.get_text(" ", strip=True)
        if not section_title:
            continue

        if section_title.strip().lower() == "table of contents":
            continue

        parts: list[str] = []

        for el in h2.next_elements:
            if not isinstance(el, Tag):
                continue
            if not _is_within_main(el, main):
                continue

            if el.name == "h2":
                break

            if el.find_parent("table") is not None:
                continue

            if el.name in {"p", "li"}:
                text = el.get_text(" ", strip=True)
                if text:
                    parts.append(text)

        seen: set[str] = set()
        dedup_parts: list[str] = []
        for p in parts:
            if p not in seen:
                seen.add(p)
                dedup_parts.append(p)

        body_text = re.sub(r"\s+", " ", " ".join(dedup_parts)).strip()
        if body_text:
            sections.append(
                {
                    "title": section_title,
                    "text": body_text,
                }
            )

    return sections


def build_document_record(page_url: str, html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    canonical_url = extract_canonical_url(soup, page_url)
    title = extract_title(soup) or "Untitled"

    sections = extract_sections_from_main(soup)

    section_docs = []
    for section in sections:
        section_docs.append(
            {
                "title": title,
                "section": section["title"],
                "chunk_text": section["text"],
                "url": canonical_url,
            }
        )

    doc = {
        "id": sha256_text(canonical_url)[:16],
        "url": page_url,
        "canonical_url": canonical_url,
        "title": title,
        "retrieved_at": now_iso(),
        "sections": section_docs,
    }
    return doc


def main() -> None:
    items = load_catalog_items(CATALOG_PATH)

    for item in items:
        if (item.get("state") or "").strip().lower() == "cancelled":
            update_status(CATALOG_PATH, item["url"], "skipped")
            item["status"] = "skipped"

    pending = [item for item in items if item["status"] == "pending"]

    print(f"Catalog items: {len(items)} | pending: {len(pending)}")

    with requests.Session() as session:
        for item in pending:
            page_url = item["url"]

            try:
                html = fetch_html(page_url, session)
                doc = build_document_record(page_url, html)

                out_path = write_pretty_json(OUT_JSON_DIR, doc)
                update_status(CATALOG_PATH, page_url, "parsed")

                print(f"parsed: {page_url}")
                print(f"saved:  {out_path}")
            except Exception as e:
                update_status(CATALOG_PATH, page_url, "skipped")
                print(f"skipped: {page_url} ({type(e).__name__}: {e})")


if __name__ == "__main__":
    main()