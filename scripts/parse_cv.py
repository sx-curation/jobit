import sys
import fitz  # PyMuPDF

def parse_cv(pdf_path: str, output_path: str):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"CV parsed → {output_path}")

if __name__ == "__main__":
    parse_cv("my_cv.pdf", "output/cv_parsed.md")