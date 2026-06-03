#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_cover_letter_pdf.py — cover_letter_draft.md → cover_letter.pdf

用法：
  python scripts/gen_cover_letter_pdf.py --job_folder <job_folder> [--uid leon]

示例：
  python scripts/gen_cover_letter_pdf.py --job_folder group-pmo_Oscar-Bravo_Junior-PMO_20260528 --uid leon
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from fpdf import FPDF, XPos, YPos

PROJECT_DIR = Path(__file__).resolve().parent.parent
USERS_DIR   = PROJECT_DIR / "users"


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

    # Extract title from first line
    title_line = ""
    for line in lines:
        if line.startswith("# "):
            title_line = line[2:].strip()
            break

    # Split by --- separators
    separator_indices = [i for i, l in enumerate(lines) if l.strip() == "---"]

    # Header block: between first and second ---
    header_lines = []
    body_lines   = []

    if len(separator_indices) >= 2:
        header_lines = lines[separator_indices[0] + 1 : separator_indices[1]]
        body_lines   = lines[separator_indices[1] + 1 :]
    elif len(separator_indices) == 1:
        body_lines = lines[separator_indices[0] + 1 :]
    else:
        body_lines = lines[1:]  # fallback: everything after title

    # Parse header: strip blank lines
    header_block = [l for l in header_lines if l.strip()]

    # Parse body: collect paragraphs (split by blank lines)
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

    # Remove trailing signature (last paragraph is just the name, ≤4 words)
    closing_name = ""
    if paragraphs and len(paragraphs[-1].split()) <= 4:
        closing_name = paragraphs.pop()

    return {
        "title":       title_line,
        "header":      header_block,
        "paragraphs":  paragraphs,
        "closing":     closing_name,
    }


class CoverLetterPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(left=22, top=22, right=22)
        self.set_auto_page_break(auto=True, margin=22)

    def header_block(self, lines: list[str]):
        """Render the sender/recipient header."""
        if not lines:
            return

        # First line = sender name (larger, bold)
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 7, lines[0], new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Remaining header lines (contact info, date, company)
        self.set_font("Helvetica", "", 9)
        for line in lines[1:]:
            self.cell(0, 5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Horizontal rule
        self.ln(3)
        self.set_draw_color(180, 180, 180)
        self.line(self.get_x(), self.get_y(), self.w - 22, self.get_y())
        self.ln(5)

    def body_paragraph(self, text: str):
        """Render a body paragraph with word wrapping."""
        self.set_font("Helvetica", "", 10.5)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 6, text)
        self.ln(3)

    def closing_block(self, name: str):
        """Render the closing signature."""
        self.ln(4)
        self.set_font("Helvetica", "", 10.5)
        self.cell(0, 6, name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def sanitize(text: str) -> str:
    """Replace characters that fpdf core fonts can't handle."""
    replacements = {
        "\u2014": "--",   # em dash
        "\u2013": "-",    # en dash
        "\u2018": "'",    # left single quote
        "\u2019": "'",    # right single quote
        "\u201c": '"',    # left double quote
        "\u201d": '"',    # right double quote
        "\u00e4": "ae",   # ä  (fallback for non-Unicode fonts)
        "\u00f6": "oe",   # ö
        "\u00fc": "ue",   # ü
        "\u00c4": "Ae",   # Ä
        "\u00d6": "Oe",   # Ö
        "\u00dc": "Ue",   # Ü
        "\u00df": "ss",   # ß
        "\u00e9": "e",    # é
        "\u00e8": "e",    # è
        "\u00ea": "e",    # ê
        "\u00e0": "a",    # à
        "\u00e2": "a",    # â
        "\u00fb": "u",    # û
        "\u00ee": "i",    # î
        "\u00f4": "o",    # ô
        "\u00e7": "c",    # ç
        "\u00fc": "ue",   # ü (duplicate key, harmless)
        "\u2026": "...",  # ellipsis
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    # Remove any remaining non-latin1 characters
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_pdf(md_path: Path, pdf_path: Path) -> None:
    md_text  = md_path.read_text(encoding="utf-8")
    sections = parse_cover_letter(md_text)

    pdf = CoverLetterPDF()
    pdf.add_page()

    # Header block
    sanitized_header = [sanitize(l) for l in sections["header"]]
    pdf.header_block(sanitized_header)

    # Body paragraphs
    for para in sections["paragraphs"]:
        pdf.body_paragraph(sanitize(para))

    # Closing
    if sections["closing"]:
        pdf.closing_block(sanitize(sections["closing"]))

    pdf.output(str(pdf_path))
    print(f"PDF generated: {pdf_path}  ({pdf_path.stat().st_size // 1024} KB)")


def main():
    parser = argparse.ArgumentParser(description="Convert cover_letter_draft.md → cover_letter.pdf")
    parser.add_argument("--job_folder", required=True, help="Job folder name under users/{uid}/output/")
    parser.add_argument("--uid", default="leon", help="User ID (default: leon)")
    args = parser.parse_args()

    output_dir = USERS_DIR / args.uid / "output"
    job_dir    = output_dir / args.job_folder
    md_path    = job_dir / "cover_letter_draft.md"
    pdf_path   = job_dir / "cover_letter.pdf"

    if not md_path.exists():
        # Also check legacy path without draft suffix
        alt = job_dir / "cover_letter.md"
        if alt.exists():
            md_path = alt
        else:
            print(f"ERROR: cover letter not found at {md_path}", file=sys.stderr)
            sys.exit(1)

    generate_pdf(md_path, pdf_path)


if __name__ == "__main__":
    main()
