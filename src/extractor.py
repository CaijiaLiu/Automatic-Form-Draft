"""Transparent, rule-based local extraction. No network or model calls."""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable

from .models import Fact
from .demographics import demographic_facts

PATTERNS = {
    "diagnosis": r"(?:diagnosis|diagnosed with)\s*[:\-]?\s*(immune thrombocytopenia|\bITP\b)",
    "medication": r"\b(?:medication|drug)\s*[:\-]\s*([^\n.;]+)",
    "dose": r"\b(?:dose|dosage)\s*[:\-]\s*([^\n;]+)",
    "platelet_count": r"(?:platelets?|platelet count)\s*[:\-]?\s*([0-9,]+\s*(?:x\s*10\^?9/?L|10\^?9/L|K/uL)?)",
    "response": r"(?:response|treatment response)\s*[:\-]\s*([^\n.;]+)",
}
DATE = re.compile(r"\b(?:20\d{2}[-/]\d{2}[-/]\d{2}|\d{1,2}[/-]\d{1,2}[/-]20\d{2})\b")

def _read_text(path: Path,allow_ocr=True) -> list[tuple[str, str]]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return [("text", path.read_text(errors="replace"))]
    if suffix == ".csv":
        with path.open(newline="", errors="replace") as f:
            return [(f"row {i}", " | ".join(row)) for i, row in enumerate(csv.reader(f), 1)]
    if suffix == ".docx":
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        doc = Document(path)
        blocks = []
        for item in doc.element.body:
            if item.tag.endswith('}p'):
                blocks.append(Paragraph(item, doc).text)
            elif item.tag.endswith('}tbl'):
                blocks.extend(' | '.join(c.text for c in row.cells) for row in Table(item, doc).rows)
        return [("document paragraph/table text", "\n".join(blocks))]
    if suffix == ".pdf":
        from .document_text import pdf_text
        return pdf_text(path,allow_ocr=allow_ocr)
    if suffix in {".png", ".jpg", ".jpeg"}:
        if not allow_ocr:return [('image OCR deferred','')]
        try:
            from PIL import Image
            from .document_text import image_text
            return [("image OCR (visual rows)", image_text(Image.open(path)))]
        except Exception:
            return [("image", "")]
    return []

def extract_files(paths: Iterable[Path], *, allow_ocr=True) -> tuple[list[Fact], list[str]]:
    facts: list[Fact] = []
    warnings: list[str] = []
    for path in paths:
        try:
            pages = _read_text(path,allow_ocr=allow_ocr)
        except Exception as exc:
            warnings.append(f"{path.name}: could not read file ({type(exc).__name__}); Requires Review.")
            continue
        document_text = '\n'.join(text for _, text in pages)
        from .prescriber import prescriber_facts
        facts.extend(prescriber_facts(pages,path.name))
        for location, text in pages:
            if 'deferred' in location:
                warnings.append(f'{path.name} {location}: scan reading deferred to optional background review.')
            elif 'OCR' in location and text.strip():
                warnings.append(f"{path.name} {location}: OCR-derived candidates require visual verification.")
            elif not text.strip():
                warnings.append(f"{path.name} {location}: no readable text; Requires Review.")
        if allow_ocr and path.suffix.lower() in {".png", ".jpg", ".jpeg"} and not any(text.strip() for _, text in pages):
            warnings.append(f"{path.name}: OCR unavailable or no readable text; install Tesseract for image OCR.")
        for location, text in pages:
            facts.extend(demographic_facts(text, path.name, location, document_context=document_text, include_prescriber=False))
            for line_no, line in enumerate(text.splitlines(), 1):
                date = DATE.search(line)
                for category, expression in PATTERNS.items():
                    if category in {'medication','dose'} and re.search(r'(?i)\b(?:requested\s+(?:drug|medication|dose|regimen)|medication requested)\b',line):
                        continue
                    match = re.search(expression, line, flags=re.I)
                    if match:
                        facts.append(Fact(category, match.group(1).strip(), date.group(0) if date else "Requires Review", path.name, f"{location}, line {line_no}", line.strip()))
            # Narrative platelet results can span physical line wraps. Evidence is
            # kept as the exact original span, rather than a rewritten sentence.
            expression = r'(?i)\b(?:platelet(?:\s+count)?|PLT)\s*(?:was|were|is|of|:|=)?\s*(<?\d[\d,]*(?:\.\d+)?)\s*(x\s*10\^?9\s*/\s*L|K/uL|/uL|/µL)'
            for m in re.finditer(expression, text):
                value = re.sub(r'\s+', ' ', m.group(1)+' '+m.group(2))
                first = text.count('\n', 0, m.start()) + 1
                if not any(f.filename==path.name and f.location==f'{location}, line {first}' and f.category=='platelet_count' for f in facts):
                    nearby = text[max(0,m.start()-25):m.end()]
                    date = DATE.search(nearby)
                    facts.append(Fact('platelet_count',value,date.group() if date else 'Requires Review',path.name,
                        f'{location}, lines {first}-{text.count(chr(10),0,m.end())+1}',m.group(),
                        'Requires Review: narrative/OCR candidate; event date may be missing.'))
            # Administration statements in prose, including line-wrapped text.
            medicines = r'(?:prednisone|prednisolone|dexamethasone|IVIG|intravenous immunoglobulin|rituximab|eltrombopag|romiplostim|avatrombopag)'
            dose = r'\d+(?:\.\d+)?\s*(?:mg/kg|g/kg|mcg/kg|mg|mcg|g)(?:\s+(?:daily|once daily|weekly|BID|orally|PO)){0,3}'
            for m in re.finditer(r'(?i)\b(?:started|began|received|treated\s+with|taking)\s+('+medicines+r')(?:\s+('+dose+r'))?',text):
                before=text[max(0,m.start()-40):m.start()]
                if re.search(r'\b(?:not|never|no|would|may|might|will|plan(?:ned)?\s+to)\s*$', before, re.I):
                    continue
                first=text.count('\n',0,m.start())+1
                date=DATE.search(text[max(0,m.start()-25):m.end()+20])
                for category,value in [('medication',m.group(1)),('dose',m.group(2))]:
                    if value and not any(f.filename==path.name and f.category==category and f.value.casefold()==value.casefold() and f.evidence==m.group() for f in facts):
                        facts.append(Fact(category,re.sub(r'\s+',' ',value),date.group() if date else 'Requires Review',path.name,
                            f'{location}, lines {first}-{text.count(chr(10),0,m.end())+1}',m.group(),
                            'Requires Review: narrative treatment candidate; verify administration and event date.'))
            # Generic two-line medicine/dose rows in a prescribed-medication
            # section. This does not make the medicine an access request.
            section=re.search(r'(?is)PRESCRIBED\s+MEDICATIONS(.*?)(?:\nINDICATION\b|\nINSTRUCTIONS\b|\Z)',text)
            if section:
                for m in re.finditer(r'(?m)^([A-Z][A-Za-z-]+(?: [A-Z][A-Za-z-]+)?)\s*\n\s*('+dose+r'[^\n]*)',section.group(1)):
                    start=section.start(1)+m.start()
                    first=text.count('\n',0,start)+1
                    for category,value in [('medication',m.group(1)),('dose',m.group(2))]:
                        facts.append(Fact(category,value,'Requires Review',path.name,f'{location}, lines {first}-{first+1}',m.group(),
                            'Requires Review: prescribed medicine in document; not automatically the requested access drug.'))
    return facts, warnings
