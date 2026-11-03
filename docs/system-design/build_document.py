"""Build the Object Lens technical companion from one JSON source.

This script authors DOCX only. A separately owned Word export lays out the
document and produces the matching PDF. It never launches Office,
a browser, a downloader or an external command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.image.image import Image as DocxImage
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Inches, Mm, Pt, RGBColor


BODY_FONT = "Aptos"
CODE_FONT = "Consolas"
BLACK = "000000"
BLUE = "285BD4"
TABLE_HEADER = "244764"
TABLE_ALTERNATE = "F3F6F9"
TABLE_BORDER = "D9D9D9"
MUTED = "586674"
URL_RE = re.compile(r"https?://[^\s<>]+")


def xml_element(name: str, **attributes: str) -> Any:
    node = OxmlElement(name)
    for key, value in attributes.items():
        node.set(qn(key), str(value))
    return node


def set_font(style: Any, name: str, size: float, color: str = BLACK,
             bold: bool = False) -> None:
    style.font.name = name
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.italic = False
    style.font.color.rgb = RGBColor.from_string(color)
    properties = style.element.get_or_add_rPr()
    fonts = properties.find(qn("w:rFonts"))
    if fonts is None:
        fonts = xml_element("w:rFonts")
        properties.insert(0, fonts)
    for attribute in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn("w:" + attribute), name)
    for attribute in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        fonts.attrib.pop(qn("w:" + attribute), None)
    color_node = properties.find(qn("w:color"))
    if color_node is not None:
        for attribute in ("themeColor", "themeTint", "themeShade"):
            color_node.attrib.pop(qn("w:" + attribute), None)


def paragraph_style(document: Any, name: str) -> Any:
    try:
        return document.styles[name]
    except KeyError:
        return document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)


def add_field(paragraph: Any, instruction: str, cached: str = "") -> None:
    begin = paragraph.add_run()
    begin._r.append(xml_element("w:fldChar", **{"w:fldCharType": "begin", "w:dirty": "true"}))
    code = paragraph.add_run()
    instruction_node = xml_element("w:instrText")
    instruction_node.set(qn("xml:space"), "preserve")
    instruction_node.text = " " + instruction + " "
    code._r.append(instruction_node)
    paragraph.add_run()._r.append(xml_element("w:fldChar", **{"w:fldCharType": "separate"}))
    paragraph.add_run(cached)
    paragraph.add_run()._r.append(xml_element("w:fldChar", **{"w:fldCharType": "end"}))


def internal_link(paragraph: Any, bookmark: str, label: str,
                  color: str = BLUE, underline: bool = False) -> None:
    link = xml_element("w:hyperlink", **{"w:anchor": bookmark, "w:history": "1"})
    run = xml_element("w:r")
    properties = xml_element("w:rPr")
    properties.append(xml_element("w:color", **{"w:val": color}))
    if underline:
        properties.append(xml_element("w:u", **{"w:val": "single"}))
    run.append(properties)
    text = xml_element("w:t")
    text.set(qn("xml:space"), "preserve")
    text.text = label
    run.append(text)
    link.append(run)
    paragraph._p.append(link)


def external_link(paragraph: Any, url: str, label: str) -> None:
    relationship = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    link = xml_element("w:hyperlink", **{"r:id": relationship, "w:history": "1"})
    run = xml_element("w:r")
    properties = xml_element("w:rPr")
    properties.append(xml_element("w:color", **{"w:val": BLUE}))
    properties.append(xml_element("w:u", **{"w:val": "single"}))
    run.append(properties)
    text = xml_element("w:t")
    text.text = label
    run.append(text)
    link.append(run)
    paragraph._p.append(link)


def add_text(paragraph: Any, text: str, link_urls: bool = True) -> None:
    """Preserve prose verbatim while making explicit web addresses clickable."""
    if not link_urls:
        paragraph.add_run(text)
        return
    offset = 0
    for match in URL_RE.finditer(text):
        paragraph.add_run(text[offset:match.start()])
        raw = match.group()
        url = raw.rstrip(".,;)")
        external_link(paragraph, url, url)
        paragraph.add_run(raw[len(url):])
        offset = match.end()
    paragraph.add_run(text[offset:])


def pending_values(value: Any, path: str = "source") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "pending_items" and item:
                errors.append(path + ".pending_items is not empty")
            if key == "status" and isinstance(item, str):
                lowered = item.lower()
                if lowered.startswith(("pending", "draft")):
                    errors.append(path + ".status = " + item)
            errors.extend(pending_values(item, path + "." + str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(pending_values(item, path + "[" + str(index) + "]"))
    elif isinstance(value, str) and "PENDING_" in value:
        errors.append(path + " contains a PENDING_ marker")
    return errors


def word_bookmark(identifier: str) -> str:
    stem = "OL_" + re.sub(r"[^A-Za-z0-9_]", "_", identifier)
    if len(stem) > 40:
        stem = stem[:30] + "_" + hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:8]
    return stem


def collect_headings(source: dict[str, Any]) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for section_index, section in enumerate(source["sections"]):
        section_id = str(section["id"])
        candidates = [{"title": section["title"], "level": 1,
                       "key": section_id, "block_index": None}]
        for block_index, block in enumerate(section.get("blocks", [])):
            if block.get("type") == "heading":
                candidates.append({"title": block["text"], "level": int(block.get("level", 2)),
                                   "key": section_id + "__" + str(block.get("id", block["text"])),
                                   "block_index": block_index})
        for candidate in candidates:
            bookmark = word_bookmark(candidate["key"])
            if bookmark in seen:
                raise ValueError("Duplicate heading bookmark: " + bookmark)
            seen.add(bookmark)
            headings.append({**candidate, "bookmark": bookmark, "section_index": section_index})
    return headings


class CompanionBuilder:
    def __init__(self, source: dict[str, Any], source_path: Path,
                 allow_draft: bool, toc_mode: str, toc_depth: int,
                 page_map: dict[str, Any]) -> None:
        self.source = source
        self.source_path = source_path
        self.allow_draft = allow_draft
        self.toc_mode = toc_mode
        self.toc_depth = toc_depth
        self.page_map = page_map
        self.document = Document()
        self.heading_specs = collect_headings(source)
        self.headings_by_position = {
            (item["section_index"], item["block_index"]): item
            for item in self.heading_specs
        }
        self.bookmark_counter = 0
        self.bookmark_names: set[str] = set()
        self.assets: list[dict[str, Any]] = []
        self.figure_count = 0
        self.table_count = 0
        self.configure_document()

    def configure_document(self) -> None:
        document = self.document
        section = document.sections[0]
        section.page_width = Mm(210)
        section.page_height = Mm(297)
        section.top_margin = Mm(18)
        section.bottom_margin = Mm(18)
        section.left_margin = Mm(19)
        section.right_margin = Mm(19)
        section.header_distance = Mm(8)
        section.footer_distance = Mm(8)
        section.different_first_page_header_footer = True
        self.available_width = section.page_width - section.left_margin - section.right_margin

        normal = document.styles["Normal"]
        set_font(normal, BODY_FONT, 11)
        normal.paragraph_format.line_spacing = 1.1
        normal.paragraph_format.space_after = Pt(6)
        normal.paragraph_format.widow_control = True
        normal.paragraph_format.keep_with_next = False

        for name, size, bold, before, after in [
            ("Title", 32, False, 0, 14),
            ("Subtitle", 20, False, 0, 18),
            ("Heading 1", 22, True, 18, 10),
            ("Heading 2", 15, True, 12, 6),
            ("Heading 3", 12, True, 9, 5),
        ]:
            style = document.styles[name]
            set_font(style, BODY_FONT, size, bold=bold)
            style.paragraph_format.space_before = Pt(before)
            style.paragraph_format.space_after = Pt(after)
            style.paragraph_format.keep_with_next = True
            style.paragraph_format.keep_together = True
            style.paragraph_format.page_break_before = False
            properties = style.element.get_or_add_pPr()
            for tag in ("w:pBdr", "w:shd"):
                for node in list(properties.findall(qn(tag))):
                    properties.remove(node)

        for name, size, color in [
            ("Caption", 9.5, BLACK), ("Source", 8.5, MUTED),
            ("Small", 9.5, MUTED), ("Navigation", 9, MUTED),
            ("Table Text", 10, BLACK), ("Code", 9.3, BLACK),
            ("Contents Title", 22, BLACK), ("Reading Guide Heading", 15, BLACK),
        ]:
            style = paragraph_style(document, name)
            style.base_style = normal
            set_font(style, CODE_FONT if name == "Code" else BODY_FONT, size, color)
            style.paragraph_format.space_after = Pt(6 if name != "Code" else 1.5)
            style.paragraph_format.line_spacing = 1.1
            style.paragraph_format.keep_with_next = False
            style.paragraph_format.keep_together = name in ("Caption", "Code")
        document.styles["Contents Title"].paragraph_format.keep_with_next = True
        document.styles["Contents Title"].paragraph_format.space_after = Pt(10)
        document.styles["Reading Guide Heading"].font.bold = True
        document.styles["Reading Guide Heading"].paragraph_format.space_before = Pt(12)
        document.styles["Reading Guide Heading"].paragraph_format.keep_with_next = True
        document.styles["Code"].paragraph_format.left_indent = Mm(2)
        document.styles["Code"].paragraph_format.right_indent = Mm(2)
        document.styles["Code"].paragraph_format.line_spacing = Pt(12)
        for level in (1, 2, 3):
            style = paragraph_style(document, "TOC " + str(level))
            style.base_style = normal
            set_font(style, BODY_FONT, 10.5 if level == 1 else 10, bold=level == 1)
            style.paragraph_format.left_indent = Mm(0 if level == 1 else 5)
            style.paragraph_format.space_before = Pt(4 if level == 1 else 0)
            style.paragraph_format.space_after = Pt(2)
            style.paragraph_format.line_spacing = 1.05
            style.paragraph_format.keep_together = True
            style.paragraph_format.tab_stops.add_tab_stop(self.available_width, WD_TAB_ALIGNMENT.RIGHT)

        header = section.header.paragraphs[0]
        header.style = document.styles["Small"]
        add_text(header, str(self.source["metadata"]["title"]) + "  System design and software quality")
        footer = section.footer.paragraphs[0]
        footer.style = document.styles["Small"]
        footer.paragraph_format.tab_stops.add_tab_stop(self.available_width, WD_TAB_ALIGNMENT.RIGHT)
        footer.add_run("Object Lens\t")
        add_field(footer, "PAGE", "1")
        footer.add_run(" / ")
        add_field(footer, "NUMPAGES", "1")

        settings = document.settings.element
        update_fields = settings.find(qn("w:updateFields"))
        if update_fields is None:
            update_fields = xml_element("w:updateFields")
            settings.append(update_fields)
        update_fields.set(qn("w:val"), "true")
        properties = document.core_properties
        metadata = self.source["metadata"]
        properties.title = str(metadata["title"])
        properties.subject = str(metadata.get("subtitle", "System design and software quality"))
        properties.author = str(metadata.get("author", ""))
        properties.last_modified_by = str(metadata.get("author", ""))
        properties.keywords = "Object Lens, system design, software quality, Selenium, pytest"
        properties.comments = "Generated from the accompanying source.json."
        properties.language = str(metadata.get("language", "en"))
        generated_at = datetime.now(timezone.utc)
        properties.created = generated_at
        properties.modified = generated_at

    def bookmark(self, paragraph: Any, name: str) -> None:
        if name in self.bookmark_names:
            raise ValueError("Duplicate document bookmark: " + name)
        self.bookmark_names.add(name)
        self.bookmark_counter += 1
        start = xml_element("w:bookmarkStart", **{"w:id": str(self.bookmark_counter), "w:name": name})
        end = xml_element("w:bookmarkEnd", **{"w:id": str(self.bookmark_counter)})
        properties = paragraph._p.find(qn("w:pPr"))
        paragraph._p.insert(1 if properties is not None else 0, start)
        paragraph._p.append(end)

    def source_note(self, sources: Any) -> None:
        if not sources:
            return
        if isinstance(sources, str):
            sources = [sources]
        labels = []
        for value in sources:
            if isinstance(value, dict):
                label = str(value.get("file", ""))
                detail = value.get("lines") or value.get("symbol")
                if detail:
                    label += ": " + str(detail)
                labels.append(label)
            else:
                labels.append(str(value))
        # A source belongs to the block immediately above it. Keep that block's
        # last paragraph with the citation so a source-only line cannot start
        # the next page without the text or figure it identifies.
        if self.document.paragraphs:
            self.document.paragraphs[-1].paragraph_format.keep_with_next = True
        paragraph = self.document.add_paragraph(style="Source")
        add_text(paragraph, "Source: " + "; ".join(labels))

    def add_cover(self) -> None:
        metadata = self.source["metadata"]
        title = self.document.add_paragraph(str(metadata["title"]), style="Title")
        self.bookmark(title, "OL_Top")
        self.document.add_paragraph(str(metadata.get("subtitle", "System design and software quality")), style="Subtitle")
        details = ["Private technical companion", "Edition " + str(metadata.get("edition", "1.0"))]
        if metadata.get("date"):
            details.append(str(metadata["date"]))
        self.document.add_paragraph("\n".join(details), style="Small")
        if self.allow_draft:
            self.document.add_paragraph("Draft preview. Implementation and evidence markers may remain.", style="Small")
        for block in self.source.get("cover", []):
            self.add_block(block)
        rows = [
            ["Prepared for", str(metadata.get("audience", "Tan Le Jie"))],
            ["Application source", str(metadata.get("documented_commit", ""))],
            ["Evidence version", str(metadata.get("evidence_revision", ""))],
            ["Scope", "Local Windows and Chrome learning and demonstration workflow"],
        ]
        self.add_table({"columns": ["Document control", "Value"], "rows": rows,
                        "widths": [1.45, 4.65]}, count=False)
        self.document.add_page_break()

    def toc_page_number(self, heading: dict[str, Any]) -> str:
        value = self.page_map.get(heading["bookmark"], self.page_map.get(heading["key"]))
        if isinstance(value, dict):
            value = value.get("page")
        if value is None:
            return "?"
        page = int(value)
        if page < 1:
            raise ValueError("TOC page numbers must be positive: " + heading["bookmark"])
        return str(page)

    def add_contents(self) -> None:
        heading = self.document.add_paragraph("Contents", style="Contents Title")
        self.bookmark(heading, "OL_Contents")
        entries = [item for item in self.heading_specs if item["level"] <= self.toc_depth]
        if not entries:
            raise ValueError("No headings are available for the contents")
        if self.toc_mode == "static" and not self.allow_draft:
            missing = [entry["bookmark"] for entry in entries if self.toc_page_number(entry) == "?"]
            if missing:
                raise ValueError("Static final TOC requires an actual page map for: " + ", ".join(missing))

        for index, entry in enumerate(entries):
            paragraph = self.document.add_paragraph(style="TOC " + str(entry["level"]))
            if self.toc_mode == "native" and index == 0:
                paragraph.add_run()._r.append(xml_element("w:fldChar", **{"w:fldCharType": "begin", "w:dirty": "true"}))
                instruction = xml_element("w:instrText")
                instruction.set(qn("xml:space"), "preserve")
                instruction.text = ' TOC \\o "1-' + str(self.toc_depth) + '" \\h \\z \\u '
                paragraph.add_run()._r.append(instruction)
                paragraph.add_run()._r.append(xml_element("w:fldChar", **{"w:fldCharType": "separate"}))
            internal_link(paragraph, entry["bookmark"], str(entry["title"]), color=BLACK)
            paragraph.add_run("\t")
            page_number = self.toc_page_number(entry)
            if self.toc_mode == "native":
                add_field(paragraph, "PAGEREF " + entry["bookmark"] + " \\h", page_number)
            else:
                internal_link(paragraph, entry["bookmark"], page_number, color=BLACK)
            if self.toc_mode == "native" and index == len(entries) - 1:
                paragraph.add_run()._r.append(xml_element("w:fldChar", **{"w:fldCharType": "end"}))

        if self.source.get("reading_route"):
            self.document.add_paragraph("Reading this companion", style="Reading Guide Heading")
            for block in self.source["reading_route"]:
                self.add_block(block)
        self.document.add_page_break()

    def add_table(self, block: dict[str, Any], count: bool = True) -> None:
        columns = [str(value) for value in block["columns"]]
        rows = block.get("rows", [])
        if not columns:
            raise ValueError("A table must have columns")
        for row in rows:
            if len(row) != len(columns):
                raise ValueError("Table row length does not match its columns")
        if block.get("caption"):
            caption = self.document.add_paragraph(str(block["caption"]), style="Caption")
            caption.paragraph_format.keep_with_next = True
        table = self.document.add_table(rows=1, cols=len(columns))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        weights = [float(value) for value in block.get("widths", [1] * len(columns))]
        if len(weights) != len(columns) or any(value <= 0 for value in weights):
            raise ValueError("Invalid table width weights")
        widths = [int(self.available_width * value / sum(weights)) for value in weights]
        for column, width in zip(table.columns, widths):
            column.width = width
        properties = table._tbl.tblPr
        borders = properties.find(qn("w:tblBorders"))
        if borders is None:
            borders = xml_element("w:tblBorders")
            properties.append(borders)
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            borders.append(xml_element("w:" + side, **{"w:val": "single", "w:sz": "4", "w:color": TABLE_BORDER}))
        margins = xml_element("w:tblCellMar")
        for side, amount in (("top", "80"), ("bottom", "80"), ("left", "120"), ("right", "120")):
            margins.append(xml_element("w:" + side, **{"w:w": amount, "w:type": "dxa"}))
        properties.append(margins)

        all_rows = [columns, *rows]
        for row_index, values in enumerate(all_rows):
            row = table.rows[0] if row_index == 0 else table.add_row()
            row_properties = row._tr.get_or_add_trPr()
            row_properties.append(xml_element("w:cantSplit"))
            if row_index == 0:
                row_properties.append(xml_element("w:tblHeader"))
            for column_index, (cell, value) in enumerate(zip(row.cells, values)):
                cell.width = widths[column_index]
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                shade = TABLE_HEADER if row_index == 0 else (TABLE_ALTERNATE if row_index % 2 == 0 else "FFFFFF")
                cell._tc.get_or_add_tcPr().append(xml_element("w:shd", **{"w:fill": shade, "w:val": "clear"}))
                paragraph = cell.paragraphs[0]
                paragraph.style = self.document.styles["Table Text"]
                paragraph.paragraph_format.space_after = Pt(1.5)
                # Keep short tables together; splitting a four-row definition
                # table after its first row makes the next page harder to read.
                paragraph.paragraph_format.keep_with_next = (
                    row_index == 0 or len(rows) <= 5 and row_index < len(all_rows) - 1
                )
                paragraph.paragraph_format.keep_together = True
                if columns[column_index].lower() in ("id", "status", "result") and len(str(value)) < 20:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cell_text = str(value)
                if row_index != 0 and URL_RE.fullmatch(cell_text):
                    link_label = block.get("link_labels", {}).get(cell_text, "Open reference")
                    external_link(paragraph, cell_text, str(link_label))
                else:
                    add_text(paragraph, cell_text, link_urls=row_index != 0)
                if row_index == 0:
                    for run in paragraph.runs:
                        run.bold = True
                        run.font.color.rgb = RGBColor.from_string("FFFFFF")
        spacer = self.document.add_paragraph()
        spacer.paragraph_format.space_after = Pt(3)
        spacer.paragraph_format.space_before = Pt(0)
        spacer.paragraph_format.line_spacing = Pt(1)
        spacer.add_run().font.size = Pt(1)
        if count:
            self.table_count += 1
        self.source_note(block.get("sources"))

    def add_figure(self, block: dict[str, Any]) -> None:
        raw_path = str(block["path"])
        if re.match(r"https?://", raw_path, re.IGNORECASE):
            raise ValueError("Figure assets must be local files: " + raw_path)
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.source_path.parent / path
        path = path.resolve()
        if not path.is_file():
            if not self.allow_draft:
                raise FileNotFoundError("Missing figure: " + str(path))
            placeholder = self.document.add_paragraph("Draft figure awaiting capture or render: " + str(block.get("alt", block.get("id", raw_path))), style="Small")
            placeholder.paragraph_format.keep_with_next = True
        else:
            info = DocxImage.from_file(str(path))
            max_width = int(self.available_width * float(block.get("width_fraction", 1.0)))
            max_height = int(Inches(float(block.get("max_height_inches", 5.6))))
            ratio = info.px_height / info.px_width
            width = min(max_width, int(max_height / ratio))
            paragraph = self.document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.keep_with_next = True
            paragraph.paragraph_format.space_after = Pt(5)
            shape = paragraph.add_run().add_picture(str(path), width=width)
            shape._inline.docPr.set("descr", str(block.get("alt", block.get("caption", ""))))
            shape._inline.docPr.set("title", str(block.get("id", "")))
            self.assets.append({"declared_path": raw_path, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                "pixels": [info.px_width, info.px_height]})
        caption = self.document.add_paragraph(str(block.get("caption", "")), style="Caption")
        caption.paragraph_format.keep_with_next = False
        caption.paragraph_format.keep_together = True
        self.source_note(block.get("sources"))
        self.figure_count += 1

    def add_code(self, block: dict[str, Any]) -> None:
        if block.get("caption"):
            caption = self.document.add_paragraph(str(block["caption"]), style="Caption")
            caption.paragraph_format.keep_with_next = True
        lines = str(block["text"]).expandtabs(4).splitlines() or [""]
        for index, line in enumerate(lines):
            paragraph = self.document.add_paragraph(style="Code")
            paragraph.paragraph_format.keep_with_next = index < len(lines) - 1
            paragraph.add_run(line if line else " ")
        self.source_note([block["source"]] if block.get("source") else block.get("sources"))

    def add_block(self, block: dict[str, Any], heading_spec: dict[str, Any] | None = None) -> None:
        block_type = block.get("type")
        if block_type == "paragraph":
            paragraph = self.document.add_paragraph(style=block.get("style", "Normal"))
            add_text(paragraph, str(block["text"]))
            self.source_note(block.get("sources"))
        elif block_type == "heading":
            level = int(block.get("level", 2))
            if level not in (1, 2, 3):
                raise ValueError("Supported heading levels are 1, 2 and 3")
            paragraph = self.document.add_paragraph(str(block["text"]), style="Heading " + str(level))
            if heading_spec:
                self.bookmark(paragraph, heading_spec["bookmark"])
        elif block_type == "table":
            self.add_table(block)
        elif block_type == "figure":
            self.add_figure(block)
        elif block_type == "code":
            self.add_code(block)
        elif block_type == "page_break":
            self.document.add_page_break()
        else:
            raise ValueError("Unsupported block type: " + str(block_type))

    def build(self, output: Path) -> dict[str, Any]:
        self.add_cover()
        self.add_contents()
        for section_index, section in enumerate(self.source["sections"]):
            heading_spec = self.headings_by_position[(section_index, None)]
            paragraph = self.document.add_paragraph(str(section["title"]), style="Heading 1")
            paragraph.paragraph_format.page_break_before = bool(section.get("start_on_new_page", False))
            self.bookmark(paragraph, heading_spec["bookmark"])
            for block_index, block in enumerate(section.get("blocks", [])):
                self.add_block(block, self.headings_by_position.get((section_index, block_index)))
            navigation = self.document.add_paragraph(style="Navigation")
            internal_link(navigation, "OL_Contents", "Back to contents", underline=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        self.document.save(output)
        return {
            "source_sha256": hashlib.sha256(self.source_path.read_bytes()).hexdigest(),
            "docx_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "toc_mode": self.toc_mode,
            "toc_depth": self.toc_depth,
            "field_refresh_required": self.toc_mode == "native",
            "layout_and_page_verification_required": True,
            "draft": self.allow_draft,
            "headings": self.heading_specs,
            "figure_count": self.figure_count,
            "table_count": self.table_count,
            "assets": self.assets,
        }


def read_source(path: Path, allow_draft: bool) -> dict[str, Any]:
    raw = path.read_bytes()
    if not allow_draft and b"\r\n" in raw:
        raise ValueError("Save the source JSON with UTF-8 and LF line endings before a final build, so its recorded hash survives Git checkout.")
    source = json.loads(raw.decode("utf-8"))
    if not isinstance(source, dict) or not isinstance(source.get("metadata"), dict):
        raise ValueError("Source requires metadata and sections objects")
    if not isinstance(source.get("sections"), list) or not source["sections"]:
        raise ValueError("Source requires at least one section")
    if not source["metadata"].get("title"):
        raise ValueError("Source title is required")
    if not allow_draft:
        unresolved = pending_values(source)
        if unresolved:
            raise ValueError("Final build refused because draft items remain:\n" + "\n".join(unresolved))
    return source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Object Lens DOCX from its authoritative JSON source. No Office, browser or network operations are performed.")
    parser.add_argument("--source", required=True, type=Path, help="Authoritative source JSON")
    parser.add_argument("--output", required=True, type=Path, help="Destination DOCX; must differ from source")
    parser.add_argument("--allow-draft", action="store_true", help="Allow explicit pending evidence and missing figure placeholders for a preview")
    parser.add_argument("--toc-mode", choices=("native", "static"), default="static", help="Deterministic bookmarked contents (default) or a native TOC field")
    parser.add_argument("--toc-depth", choices=(1, 2), type=int, default=2, help="Heading levels included in contents")
    parser.add_argument("--page-map", type=Path, help="Actual one-based pages keyed by section key or bookmark; required for final static contents")
    parser.add_argument("--navigation-manifest", type=Path, help="Optional QA JSON with heading bookmarks, asset hashes and required refresh status")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_path = args.source.resolve()
    output = args.output.resolve()
    if source_path == output or output.suffix.lower() != ".docx":
        raise ValueError("Output must be a distinct .docx file")
    source = read_source(source_path, args.allow_draft)
    page_map = json.loads(args.page_map.read_text(encoding="utf-8")) if args.page_map else {}
    if not isinstance(page_map, dict):
        raise ValueError("Page map must be a JSON object")
    builder = CompanionBuilder(source, source_path, args.allow_draft, args.toc_mode, args.toc_depth, page_map)
    manifest = builder.build(output)
    if args.navigation_manifest:
        target = args.navigation_manifest.resolve()
        if target in (source_path, output):
            raise ValueError("Navigation manifest must not overwrite source or DOCX")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(output), "draft": args.allow_draft,
                      "sections": len(source["sections"]), "figures": manifest["figure_count"],
                      "tables": manifest["table_count"], "toc_mode": args.toc_mode,
                      "next_step": "Export the matching PDF, verify actual heading pages and internal links, and inspect every page. Native TOC mode additionally requires a field refresh."}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
