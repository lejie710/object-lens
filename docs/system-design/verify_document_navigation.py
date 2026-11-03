"""Check static DOCX contents against actual Word and PDF destinations."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from pypdf import PdfReader


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{" + NS["w"] + "}"


def normalized(text: str) -> str:
    return " ".join(text.split())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docx", required=True, type=Path)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--word-result", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--page-map-output", type=Path)
    parser.add_argument("--allow-placeholder-pages", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    word = json.loads(args.word_result.read_text(encoding="utf-8"))
    headings = [h for h in manifest["headings"] if h["level"] <= manifest["toc_depth"]]
    actual = {h["bookmark"]: h for h in word["heading_pages"]}
    reader = PdfReader(args.pdf)
    page_texts = [page.extract_text() or "" for page in reader.pages]
    problems = []
    if len(reader.pages) != word["page_count"]:
        problems.append("Word and PDF page counts differ")
    with ZipFile(args.docx) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
        bookmark_names = root.xpath("//w:bookmarkStart/@w:name", namespaces=NS)
        anchors = root.xpath("//w:hyperlink/@w:anchor", namespaces=NS)
        dangling = sorted(set(anchors) - set(bookmark_names))
        if dangling:
            problems.append("Unresolved DOCX anchors: " + ", ".join(dangling))
        if len(bookmark_names) != len(set(bookmark_names)):
            problems.append("Duplicate DOCX bookmark names")
        toc_entries = []
        for paragraph in root.findall(".//w:body/w:p", NS):
            style = paragraph.find("w:pPr/w:pStyle", NS)
            if style is None or style.get(W + "val") not in ("TOC1", "TOC2", "TOC3"):
                continue
            links = paragraph.findall("w:hyperlink", NS)
            if len(links) != 2:
                problems.append("Static TOC row does not contain title and page links")
                continue
            toc_entries.append({
                "title": "".join(links[0].xpath(".//w:t/text()", namespaces=NS)),
                "bookmark": links[0].get(W + "anchor"),
                "page_text": "".join(links[1].xpath(".//w:t/text()", namespaces=NS)),
                "page_anchor": links[1].get(W + "anchor"),
            })
    if len(toc_entries) != len(headings):
        problems.append("Static TOC entry count differs from the heading manifest")

    checks = []
    for expected, entry in zip(headings, toc_entries):
        observed = actual.get(expected["bookmark"])
        if observed is None:
            problems.append("Missing Word bookmark position: " + expected["bookmark"])
            continue
        page = int(observed["page"])
        title_ok = entry["title"] == expected["title"]
        anchor_ok = entry["bookmark"] == entry["page_anchor"] == expected["bookmark"]
        heading_ok = normalized(expected["title"]) in normalized(page_texts[page - 1])
        page_ok = entry["page_text"] == str(page)
        if args.allow_placeholder_pages and entry["page_text"] == "?":
            page_ok = True
        if not (title_ok and anchor_ok and heading_ok and page_ok):
            problems.append("Contents mismatch for " + expected["bookmark"])
        checks.append({"bookmark": expected["bookmark"], "title": expected["title"],
                       "page": page, "printed_page": entry["page_text"],
                       "heading_text_present_on_target_page": heading_ok,
                       "docx_title_and_page_anchors_match": anchor_ok})

    page_objects = {(page.indirect_reference.idnum, page.indirect_reference.generation): index + 1
                    for index, page in enumerate(reader.pages)}

    def destination_page(destination):
        if isinstance(destination, str):
            named = reader.named_destinations.get(destination)
            return None if named is None else reader.get_destination_page_number(named) + 1
        if destination:
            target = destination[0]
            if hasattr(target, "idnum"):
                return page_objects.get((target.idnum, target.generation))
            if isinstance(target, int):
                return target + 1
        return None

    contents_pages = [i + 1 for i, text in enumerate(page_texts) if "Contents" in [line.strip() for line in text.splitlines()]]
    if len(contents_pages) != 1:
        problems.append("Expected one identifiable Contents title")
    contents_page = contents_pages[0] if contents_pages else None
    internal_links = []
    external_count = 0
    for page_number, page in enumerate(reader.pages, 1):
        for reference in page.get("/Annots", []):
            annotation = reference.get_object()
            if annotation.get("/Subtype") != "/Link":
                continue
            action = annotation.get("/A", {})
            destination = annotation.get("/Dest")
            if not destination and action.get("/S") == "/GoTo":
                destination = action.get("/D")
            if destination is not None:
                target_page = destination_page(destination)
                if target_page is None:
                    problems.append("Unresolved PDF internal destination")
                internal_links.append({"source_page": page_number, "target_page": target_page,
                                       "rectangle": [float(value) for value in annotation.get("/Rect", [])]})
            elif action.get("/S") == "/URI":
                external_count += 1
    # This companion's body navigation returns to Contents. Every other internal
    # link is one of the title/page pairs generated for the static contents.
    toc_links = [link for link in internal_links if link["target_page"] != contents_page]
    back_links = [link for link in internal_links if link["target_page"] == contents_page]
    expected_back_links = sum(heading["level"] == 1 for heading in manifest["headings"])
    if len(back_links) != expected_back_links:
        problems.append("PDF back-to-contents link count differs from the section count")
    expected_targets = [int(actual[h["bookmark"]]["page"]) for h in headings for _ in range(2)]
    observed_targets = [link["target_page"] for link in toc_links]
    if observed_targets != expected_targets:
        problems.append("PDF contents title/page destinations differ from the actual heading pages")
    if contents_page and any(link["source_page"] < contents_page for link in toc_links):
        problems.append("Unexpected contents destination before Contents")
    result = {
        "docx": args.docx.name, "pdf": args.pdf.name,
        "docx_sha256": hashlib.sha256(args.docx.read_bytes()).hexdigest(),
        "pdf_sha256": hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
        "pdf_pages": len(reader.pages), "word_pages": word["page_count"],
        "contents_page": contents_page, "heading_count": len(headings),
        "docx_bookmarks": len(bookmark_names), "docx_internal_links": len(anchors),
        "pdf_contents_links": len(toc_links),
        "pdf_back_to_contents_links": len(back_links),
        "pdf_external_links": external_count,
        "placeholder_pages_allowed": args.allow_placeholder_pages,
        "headings": checks, "problems": problems, "passed": not problems,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.page_map_output:
        args.page_map_output.write_text(json.dumps({h["bookmark"]: int(h["page"]) for h in word["heading_pages"]}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: result[key] for key in ("pdf_pages", "heading_count", "pdf_contents_links", "pdf_back_to_contents_links", "passed", "problems")}))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
