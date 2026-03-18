from lxml import etree

CATALOG_PATH = "./data/catalog.xml"


def reset_all_to_pending(xml_path: str) -> int:
    tree = etree.parse(xml_path)
    root = tree.getroot()

    count = 0
    for item in root.findall("Item"):
        status_el = item.find("status")
        if status_el is None:
            status_el = etree.SubElement(item, "status")
        status_el.text = "pending"
        count += 1

    tree.write(xml_path, pretty_print=True, xml_declaration=True, encoding="utf-8")
    return count


def main() -> None:
    count = reset_all_to_pending(CATALOG_PATH)
    print(f"Reset complete: {count} item(s) set to pending in {CATALOG_PATH}")


if __name__ == "__main__":
    main()