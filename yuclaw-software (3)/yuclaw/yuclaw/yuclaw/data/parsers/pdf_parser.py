"""yuclaw/data/parsers/pdf_parser.py — Extracts text with exact page anchors."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParsedParagraph:
    text: str
    page_number: int
    paragraph_hash: str
    doc_id: str

    @classmethod
    def build(cls, text: str, page: int, doc_id: str) -> "ParsedParagraph":
        return cls(
            text=text.strip(),
            page_number=page,
            paragraph_hash=hashlib.sha256(text.encode()).hexdigest()[:16],
            doc_id=doc_id,
        )


class FinancialPDFParser:
    MIN_LENGTH = 50

    def parse(self, pdf_path: str, doc_id: str) -> list[ParsedParagraph]:
        try:
            import fitz
            paragraphs = []
            doc = fitz.open(pdf_path)
            for page_num, page in enumerate(doc, start=1):
                for block in page.get_text("blocks", sort=True):
                    text = block[4] if len(block) > 4 else ""
                    if len(text.strip()) >= self.MIN_LENGTH:
                        paragraphs.append(ParsedParagraph.build(text, page_num, doc_id))
            doc.close()
            return paragraphs
        except ImportError:
            return []
        except Exception as e:
            print(f"[PDF Parser] Error: {e}")
            return []

    def parse_to_text(self, pdf_path: str) -> str:
        paragraphs = self.parse(pdf_path, "temp")
        return "\n\n".join(p.text for p in paragraphs)
