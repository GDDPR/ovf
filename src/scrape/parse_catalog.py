import json
import os
import re
import time
import hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin

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


def normalize_section_title(title: str) -> str:
    title = title.strip()
    title = re.sub(r"^\d+(?:\.\d+)*\s*[\.\-:]?\s*", "", title)
    return title.strip()


def _h2_is_authorities_or_responsibilities(title: str) -> bool:
    normalized = normalize_section_title(title)
    return re.search(r"(authorities|responsibilities)\s*$", normalized, re.I) is not None


def _strip_trailing_ellipsis(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s*(\.\.\.|…)\s*$", "", text).strip()
    return text


def _cell_text(cell: Tag) -> str:
    return cell.get_text(" ", strip=True)


def _get_table_header_and_row_cells(table_tag: Tag) -> tuple[list[str], list[tuple[Tag, Tag]]]:
    thead = table_tag.find("thead")
    tbody = table_tag.find("tbody")

    header_tr = None
    if thead:
        header_tr = thead.find("tr")
    if header_tr is None:
        header_tr = table_tag.find("tr")

    header_cells: list[str] = []
    if header_tr:
        hdr_cells = header_tr.find_all(["th", "td"], recursive=False)
        if not hdr_cells:
            hdr_cells = header_tr.find_all(["th", "td"])
        header_cells = [_strip_trailing_ellipsis(_cell_text(c)) for c in hdr_cells[:2]]

    if thead:
        if tbody:
            trs = tbody.find_all("tr")
        else:
            trs = table_tag.find_all("tr")
            if header_tr in trs:
                trs = trs[trs.index(header_tr) + 1 :]
    else:
        trs = table_tag.find_all("tr")
        trs = trs[1:] if trs else []

    if trs:
        first = trs[0]
        first_cells = first.find_all(["th", "td"])
        if first_cells:
            t1 = _strip_trailing_ellipsis(_cell_text(first_cells[0])) if len(first_cells) >= 1 else ""
            t2 = _strip_trailing_ellipsis(_cell_text(first_cells[1])) if len(first_cells) >= 2 else ""

            if first.find("th") is not None or (
                len(header_cells) >= 2 and t1 == header_cells[0] and t2 == header_cells[1]
            ):
                trs = trs[1:]

    data_rows: list[tuple[Tag, Tag]] = []
    for tr in trs:
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 2:
            cells = tr.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue

        data_rows.append((cells[0], cells[1]))

    return header_cells, data_rows


def _format_table_inline(table_tag: Tag) -> list[str]:
    headers, rows = _get_table_header_and_row_cells(table_tag)
    if len(headers) < 2 or not rows:
        return []

    h1 = headers[0].strip()
    h2 = headers[1].strip()

    out: list[str] = []

    for left_cell, right_cell in rows:
        left = _cell_text(left_cell).strip()

        lis = right_cell.find_all("li")
        if lis:
            bullets = [li.get_text(" ", strip=True).strip() for li in lis if li.get_text(strip=True)]
            right_text = " ".join(bullets).strip()
        else:
            right_text = _cell_text(right_cell).strip()

        row_header = f"{h1} {left} {h2}".strip()
        paragraph = f"{row_header} {right_text}".strip() if right_text else row_header

        if paragraph:
            out.append(paragraph)

    return out


def _parse_table_authorities_responsibilities(table_tag: Tag, section_title: str) -> list[dict]:
    headers, rows = _get_table_header_and_row_cells(table_tag)
    header2 = headers[1].strip() if len(headers) >= 2 else ""

    out: list[dict] = []

    for left_cell, right_cell in rows:
        left_title = _cell_text(left_cell).strip()
        if not left_title:
            continue

        lis = right_cell.find_all("li")
        if lis:
            bullets = [li.get_text(" ", strip=True).strip() for li in lis if li.get_text(strip=True)]
            right_text = " ".join(bullets).strip()
        else:
            right_text = _cell_text(right_cell).strip()

        if not right_text:
            continue

        text_core = f"{header2} {right_text}".strip() if header2 else right_text
        chunk_text = f"{left_title} {text_core}".strip()

        out.append(
            {
                "section": normalize_section_title(section_title),
                "chunk_text": chunk_text,
            }
        )

    return out


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

        raw_section_title = h2.get_text(" ", strip=True)
        if not raw_section_title:
            continue

        section_title = normalize_section_title(raw_section_title)
        if not section_title:
            continue

        if section_title.lower() == "table of contents":
            continue

        is_special = _h2_is_authorities_or_responsibilities(raw_section_title)

        first_table: Tag | None = None
        for el in h2.next_elements:
            if isinstance(el, Tag) and el.name == "h2":
                break
            if isinstance(el, Tag) and el.name == "table" and _is_within_main(el, main):
                first_table = el
                break

        if is_special and first_table is not None:
            sections.extend(_parse_table_authorities_responsibilities(first_table, section_title))
            continue

        parts: list[str] = []
        processed_table_ids: set[int] = set()

        for el in h2.next_elements:
            if not isinstance(el, Tag):
                continue
            if not _is_within_main(el, main):
                continue

            if el.name == "h2":
                break

            parent_table = el.find_parent("table")
            if parent_table is not None and el.name != "table":
                continue

            if el.name == "table":
                if id(el) in processed_table_ids:
                    continue
                processed_table_ids.add(id(el))
                parts.extend(_format_table_inline(el))
                continue

            if el.name in {"p", "li"}:
                if el.find("table") is not None:
                    continue
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
                    "section": section_title,
                    "chunk_text": body_text,
                }
            )

    return sections


def build_document_record(page_url: str, html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    canonical_url = extract_canonical_url(soup, page_url)
    title = extract_title(soup) or "Untitled"

    raw_sections = extract_sections_from_main(soup)

    section_docs = []
    for section in raw_sections:
        section_docs.append(
            {
                "title": title,
                "section": section["section"],
                "chunk_text": section["chunk_text"],
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