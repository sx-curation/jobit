#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_cover_letter.py — cover_letter_draft.md → cover_letter.pdf / .docx / both

用法：
  python scripts/gen_cover_letter.py --job_folder <job_folder> --format all [--uid leon]
  python scripts/gen_cover_letter.py --job_folder <job_folder> --format pdf
  python scripts/gen_cover_letter.py --job_folder <job_folder> --format docx

示例：
  python scripts/gen_cover_letter.py --job_folder group-pmo_Oscar-Bravo_Junior-PMO_20260528 --uid leon --format all
"""

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
USERS_DIR   = PROJECT_DIR / "users"


# ── Shared parser ──────────────────────────────────────────────────────────────

def parse_cover_letter(md_text: str) -> dict:
    """
    Parse cover_letter_draft.md into structured sections.

    Expected format:
        # Cover Letter — {title} | {company}

        ---

        {name}
        {location} | {email} | {phone}
        {linkedin} | {date}

        {company}
        {city, country}

        ---

        {body paragraphs}

        {name}  ← closing signature
    """
    lines = md_text.splitlines()

    title_line = ""
    for line in lines:
        if line.startswith("# "):
            title_line = line[2:].strip()
            break

    separator_indices = [i for i, l in enumerate(lines) if l.strip() == "---"]

    header_lines = []
    body_lines   = []

    if len(separator_indices) >= 2:
        header_lines = lines[separator_indices[0] + 1 : separator_indices[1]]
        body_lines   = lines[separator_indices[1] + 1 :]
    elif len(separator_indices) == 1:
        body_lines = lines[separator_indices[0] + 1 :]
    else:
        body_lines = lines[1:]

    header_block = [l for l in header_lines if l.strip()]

    paragraphs = []
    current = []
    for line in body_lines:
        if line.strip():
            current.append(line.strip())
        else:
            if current:
                paragraphs.append(" ".join(current))
                current = []
    if current:
        paragraphs.append(" ".join(current))

    closing_name = ""
    if paragraphs and len(paragraphs[-1].split()) <= 4:
        closing_name = paragraphs.pop()

    return {
        "title":      title_line,
        "header":     header_block,
        "paragraphs": paragraphs,
        "closing":    closing_name,
    }


# ── PDF ────────────────────────────────────────────────────────────────────────

def _sanitize(text: str) -> str:
    """Replace characters that fpdf core fonts can't handle."""
    replacements = {
        "—": "--",   # em dash
        "–": "-",    # en dash
        "‘": "'",    # left single quote
        "’": "'",    # right single quote
        "“": '"',    # left double quote
        "”": '"',    # right double quote
        "ä": "ae",   # ä
        "ö": "oe",   # ö
        "ü": "ue",   # ü
        "Ä": "Ae",   # Ä
        "Ö": "Oe",   # Ö
        "Ü": "Ue",   # Ü
        "ß": "ss",   # ß
        "é": "e",    # é
        "è": "e",    # è
        "ê": "e",    # ê
        "à": "a",    # à
        "â": "a",    # â
        "û": "u",    # û
        "î": "i",    # î
        "ô": "o",    # ô
        "ç": "c",    # ç
        "…": "...",  # ellipsis
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf(md_path: Path, pdf_path: Path) -> None:
    from fpdf import FPDF, XPos, YPos

    class _PDF(FPDF):
        def __init__(self):
            super().__init__(orientation="P", unit="mm", format="A4")
            self.set_margins(left=22, top=22, right=22)
            self.set_auto_page_break(auto=True, margin=22)

        def header_block(self, lines):
            if not lines:
                return
            self.set_font("Helvetica", "B", 13)
            self.cell(0, 7, lines[0], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_font("Helvetica", "", 9)
            for line in lines[1:]:
                self.cell(0, 5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(3)
            self.set_draw_color(180, 180, 180)
            self.line(self.get_x(), self.get_y(), self.w - 22, self.get_y())
            self.ln(5)

        def body_paragraph(self, text):
            self.set_font("Helvetica", "", 10.5)
            self.set_text_color(40, 40, 40)
            self.multi_cell(0, 6, text)
            self.ln(3)

        def closing_block(self, name):
            self.ln(4)
            self.set_font("Helvetica", "", 10.5)
            self.cell(0, 6, name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    sections = parse_cover_letter(md_path.read_text(encoding="utf-8"))
    pdf = _PDF()
    pdf.add_page()
    pdf.header_block([_sanitize(l) for l in sections["header"]])
    for para in sections["paragraphs"]:
        pdf.body_paragraph(_sanitize(para))
    if sections["closing"]:
        pdf.closing_block(_sanitize(sections["closing"]))
    pdf.output(str(pdf_path))
    print(f"PDF generated: {pdf_path}  ({pdf_path.stat().st_size // 1024} KB)")


# ── DOCX ───────────────────────────────────────────────────────────────────────

def generate_docx(md_path: Path, docx_path: Path) -> None:
    from docx import Document
    from docx.shared import Pt, Mm, RGBColor
    from docx.enum.text import WD_LINE_SPACING
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    FONT_NAME = "Times New Roman"
    MARGIN_MM = 22

    def _set_font(run, bold=False, size_pt=10.5, color=None):
        run.font.name = FONT_NAME
        run.font.bold = bold
        run.font.size = Pt(size_pt)
        if color:
            run.font.color.rgb = RGBColor(*color)

    def _set_para_spacing(para, before_pt=0, after_pt=6):
        fmt = para.paragraph_format
        fmt.space_before = Pt(before_pt)
        fmt.space_after  = Pt(after_pt)
        fmt.line_spacing_rule = WD_LINE_SPACING.SINGLE

    def _add_hr(doc):
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(2)
        para.paragraph_format.space_after  = Pt(4)
        pPr    = para._p.get_or_add_pPr()
        pBdr   = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "4")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "B4B4B4")
        pBdr.append(bottom)
        pPr.append(pBdr)

    sections = parse_cover_letter(md_path.read_text(encoding="utf-8"))
    doc = Document()

    sec = doc.sections[0]
    sec.page_width  = Mm(210)
    sec.page_height = Mm(297)
    for attr in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, attr, Mm(MARGIN_MM))

    for p in doc.paragraphs:
        p._element.getparent().remove(p._element)

    if sections["header"]:
        name_para = doc.add_paragraph()
        _set_font(name_para.add_run(sections["header"][0]), bold=True, size_pt=13)
        _set_para_spacing(name_para, after_pt=2)
        for line in sections["header"][1:]:
            p = doc.add_paragraph()
            _set_font(p.add_run(line), size_pt=9, color=(80, 80, 80))
            _set_para_spacing(p, after_pt=1)

    _add_hr(doc)

    for para_text in sections["paragraphs"]:
        p = doc.add_paragraph()
        _set_font(p.add_run(para_text), size_pt=10.5, color=(40, 40, 40))
        _set_para_spacing(p, after_pt=6)

    if sections["closing"]:
        doc.add_paragraph()
        p = doc.add_paragraph()
        _set_font(p.add_run(sections["closing"]), size_pt=10.5)
        _set_para_spacing(p, before_pt=4, after_pt=0)

    doc.save(str(docx_path))
    print(f"DOCX generated: {docx_path}  ({docx_path.stat().st_size // 1024} KB)")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert cover_letter_draft.md → PDF / DOCX / both"
    )
    parser.add_argument("--job_folder", required=True,
                        help="Job folder name under users/{uid}/output/")
    parser.add_argument("--uid", default="leon", help="User ID (default: leon)")
    parser.add_argument("--format", choices=["pdf", "docx", "all"], default="all",
                        help="Output format (default: all)")
    args = parser.parse_args()

    job_dir = USERS_DIR / args.uid / "output" / args.job_folder

    md_path = job_dir / "cover_letter_draft.md"
    if not md_path.exists():
        alt = job_dir / "cover_letter.md"
        if alt.exists():
            md_path = alt
        else:
            print(f"ERROR: cover letter not found at {md_path}", file=sys.stderr)
            sys.exit(1)

    if args.format in ("pdf", "all"):
        generate_pdf(md_path, job_dir / "cover_letter.pdf")
    if args.format in ("docx", "all"):
        generate_docx(md_path, job_dir / "cover_letter.docx")


if __name__ == "__main__":
    main()
