"""Docling spike — parse a real lithography PDF and report text/image/table output."""
from pathlib import Path
import sys

from docling.document_converter import DocumentConverter

def main(pdf_path: str) -> None:
    path = Path(pdf_path)
    if not path.exists():
        print(f"NOT FOUND: {path}")
        sys.exit(1)

    converter = DocumentConverter()
    result = converter.convert(path)

    doc = result.document
    text = doc.export_to_markdown()
    n_pictures = len(doc.pictures)
    n_tables = len(doc.tables)

    print(f"src     : {path.name} ({path.stat().st_size/1024:.0f} KB)")
    print(f"text    : {len(text)} chars markdown")
    print(f"pictures: {n_pictures}")
    print(f"tables  : {n_tables}")
    print("--- text head (600 chars) ---")
    print(text[:600])

if __name__ == "__main__":
    main(sys.argv[1])
