"""Content extraction: OCR, structure, tables, KV (FR-20 to FR-23)."""

import uuid
from io import BytesIO
from typing import Any

from rpd.models import Block, Bounds, Geometry, Part


def _normalize_bbox(box: tuple[float, float, float, float] | None) -> Bounds | None:
    """Convert (x0, y0, x1, y1) to Bounds."""
    if not box or len(box) < 4:
        return None
    return Bounds(
        x=box[0],
        y=box[1],
        width=box[2] - box[0],
        height=box[3] - box[1],
    )


def extract_pdf_content(data: bytes) -> tuple[list[Part], list[Block], str, int]:
    """Extract text, tables, structure from PDF."""
    parts: list[Part] = []
    blocks: list[Block] = []
    full_text = ""
    table_count = 0

    try:
        import pdfplumber
        pdf = pdfplumber.open(BytesIO(data))
        for i, page in enumerate(pdf.pages):
            pid = f"p_{i}"
            parts.append(Part(id=pid, part_type="page", index=i))

            # Text
            text = page.extract_text()
            if text:
                full_text += text + "\n"
                bid = f"b_{uuid.uuid4().hex[:12]}"
                geom = Geometry(type="box", bounds=_normalize_bbox(page.bbox)) if page.bbox else None
                blocks.append(Block(
                    id=bid,
                    block_type="text",
                    part_id=pid,
                    content=text.strip(),
                    confidence=0.9,
                    geometry=geom,
                ))

            # Tables
            tables = page.extract_tables()
            for ti, table in enumerate(tables or []):
                table_count += 1
                tid = f"t_{i}_{ti}"
                rows = len(table)
                cols = max(len(r) for r in table) if table else 0
                cells_flat = []
                for row in table:
                    cells_flat.append([c.strip() if c else "" for c in (row or [])])
                blocks.append(Block(
                    id=tid,
                    block_type="table",
                    part_id=pid,
                    cells=cells_flat,
                    rows=rows,
                    cols=cols,
                    confidence=0.85,
                ))

        pdf.close()
    except Exception:
        pass

    return parts, blocks, full_text.strip(), table_count


def extract_image_ocr(data: bytes, mime: str) -> tuple[list[Part], list[Block], str]:
    """OCR images to text with geometry."""
    parts: list[Part] = []
    blocks: list[Block] = []
    full_text = ""

    try:
        from PIL import Image
        import pytesseract
        img = Image.open(BytesIO(data))
        parts.append(Part(id="p_0", part_type="page", index=0))

        # Try to get words with geometry
        try:
            data_ocr = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            n = len(data_ocr.get("text", []) or [])
            words = []
            for i in range(n):
                w = (data_ocr.get("text") or [])[i]
                if w and str(w).strip():
                    x = (data_ocr.get("left") or [0])[i]
                    y = (data_ocr.get("top") or [0])[i]
                    ww = (data_ocr.get("width") or [0])[i]
                    hh = (data_ocr.get("height") or [0])[i]
                    conf = (data_ocr.get("conf") or [0])[i]
                    if isinstance(conf, str):
                        conf = int(conf) if conf.isdigit() else 0
                    conf_pct = conf / 100.0 if conf else 0.5
                    words.append((w, (x, y, x + ww, y + hh), conf_pct))
                    full_text += w + " "

            for wi, (w, bbox, conf) in enumerate(words):
                bid = f"w_{uuid.uuid4().hex[:12]}"
                geom = Geometry(type="box", bounds=_normalize_bbox(bbox)) if bbox and len(bbox) >= 4 else None
                blocks.append(Block(id=bid, block_type="word", part_id="p_0", content=w, confidence=conf, geometry=geom))
        except Exception:
            text = pytesseract.image_to_string(img)
            full_text = text or ""
            if full_text:
                bid = f"b_{uuid.uuid4().hex[:12]}"
                blocks.append(Block(id=bid, block_type="text", part_id="p_0", content=full_text.strip(), confidence=0.7))

    except Exception:
        pass

    return parts, blocks, full_text.strip()


def extract_docx_content(data: bytes) -> tuple[list[Part], list[Block], str, int]:
    """Extract text and tables from DOCX."""
    parts: list[Part] = []
    blocks: list[Block] = []
    full_text = ""
    table_count = 0

    try:
        from zipfile import ZipFile
        from xml.etree import ElementTree as ET
        z = ZipFile(BytesIO(data), "r")
        if "word/document.xml" not in z.namelist():
            return parts, blocks, full_text, table_count

        xml = ET.parse(z.open("word/document.xml"))
        root = xml.getroot()
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

        def text_of(elem):
            t = []
            if elem.text:
                t.append(elem.text)
            for c in elem:
                t.append(text_of(c))
                if c.tail:
                    t.append(c.tail)
            return "".join(t)

        for i, body in enumerate(root.findall(".//w:body", ns) or [root]):
            pid = f"p_{i}"
            parts.append(Part(id=pid, part_type="page", index=i))
            for para in body.findall(".//w:p", ns):
                text = text_of(para).strip()
                if text:
                    full_text += text + "\n"
                    blocks.append(Block(id=f"b_{uuid.uuid4().hex[:12]}", block_type="text", part_id=pid, content=text))
            for tbl in body.findall(".//w:tbl", ns):
                table_count += 1
                rows = tbl.findall(".//w:tr", ns)
                cells = []
                for tr in rows:
                    row = []
                    for tc in tr.findall(".//w:tc", ns):
                        row.append(text_of(tc).strip())
                    cells.append(row)
                blocks.append(Block(
                    id=f"t_{uuid.uuid4().hex[:12]}",
                    block_type="table",
                    part_id=pid,
                    cells=cells,
                    rows=len(cells),
                    cols=max(len(r) for r in cells) if cells else 0,
                    confidence=0.9,
                ))

    except Exception:
        pass

    return parts, blocks, full_text.strip(), table_count


def extract_xlsx_content(data: bytes) -> tuple[list[Part], list[Block], str, int]:
    """Extract text and tables from XLSX."""
    parts: list[Part] = []
    blocks: list[Block] = []
    full_text = ""
    table_count = 0

    try:
        import openpyxl
        wb = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
        for si, ws in enumerate(wb.worksheets):
            pid = f"s_{si}"
            parts.append(Part(id=pid, part_type="sheet", index=si))
            rows = list(ws.iter_rows(values_only=True))
            if rows:
                table_count += 1
                cells = [[str(c) if c is not None else "" for c in row] for row in rows]
                for row in rows:
                    full_text += " ".join(str(c) for c in row if c) + "\n"
                blocks.append(Block(
                    id=f"t_{uuid.uuid4().hex[:12]}",
                    block_type="table",
                    part_id=pid,
                    cells=cells,
                    rows=len(cells),
                    cols=max(len(r) for r in cells) if cells else 0,
                    confidence=0.95,
                ))
        wb.close()
    except Exception:
        pass

    return parts, blocks, full_text.strip(), table_count


def extract_eml_content(data: bytes) -> tuple[list[Part], list[Block], str]:
    """Extract body from EML."""
    blocks: list[Block] = []
    text = ""
    try:
        import email
        from email import policy
        msg = email.message_from_bytes(data, policy=policy.default)
        body = msg.get_body(preferencelist=("plain", "html"))
        if body:
            text = body.get_content()
        else:
            text = str(msg)
        if text:
            blocks.append(Block(id=f"b_{uuid.uuid4().hex[:12]}", block_type="text", content=text[:50000], confidence=0.9))
    except Exception:
        pass
    return [Part(id="body", part_type="attachment", index=0)], blocks, text[:50000]


def extract_msg_content(data: bytes) -> tuple[list[Part], list[Block], str]:
    """Extract body from MSG."""
    blocks: list[Block] = []
    text = ""
    try:
        import extract_msg
        msg = extract_msg.Message(data)
        text = msg.body or ""
        if text:
            blocks.append(Block(id=f"b_{uuid.uuid4().hex[:12]}", block_type="text", content=text[:50000], confidence=0.9))
        msg.close()
    except Exception:
        pass
    return [Part(id="body", part_type="attachment", index=0)], blocks, text[:50000]


def extract_archive_children(data: bytes) -> list[dict[str, Any]]:
    """Enumerate contained files in archive for child extraction."""
    children = []
    try:
        from zipfile import ZipFile
        z = ZipFile(BytesIO(data), "r")
        for zi in z.infolist():
            if not zi.is_dir():
                try:
                    raw = z.read(zi.filename)
                    children.append({"name": zi.filename, "data": raw})
                except Exception:
                    pass
        z.close()
    except Exception:
        pass
    return children
