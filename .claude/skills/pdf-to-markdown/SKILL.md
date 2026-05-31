---
name: pdf-to-markdown
description: 当 cv-parser agent 需要把 PDF 文件转换为文字时自动加载。提供 PyMuPDF 的标准解析流程。
---

# PDF 解析标准流程

## 依赖检查
```bash
python3 -c "import fitz" 2>/dev/null || pip install pymupdf --break-system-packages -q
```

## 标准解析脚本
```python
import fitz, json, sys

def parse_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        blocks = page.get_text("blocks")
        for b in sorted(blocks, key=lambda x: (x[1], x[0])):
            text = b[4].strip()
            if text:
                pages.append(text)
    return "\n".join(pages)

if __name__ == "__main__":
    print(parse_pdf(sys.argv[1]))
```

## 常见问题
- 如果文字乱码：PDF 可能是扫描件，改用 `page.get_text("rawdict")` 逐字符提取
- 如果段落顺序错：按 `(b[1], b[0])` 排序（先 y 后 x）
- 如果有表格：用 `page.find_tables()` 单独处理