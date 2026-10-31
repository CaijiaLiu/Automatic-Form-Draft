from __future__ import annotations

from collections import defaultdict
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .models import Fact

FIELDS = ("patient_identifier", "diagnosis", "requested_drug", "prior_therapies", "platelet_history", "treatment_response", "clinical_rationale", "clinician_confirmation")

def _joined(facts: list[Fact], category: str) -> str:
    items = [f"{f.value} ({f.date}; {f.filename} {f.location})" for f in facts if f.category == category]
    return "; ".join(items) or "Requires Review"

def build_application(facts: list[Fact]) -> dict[str, str]:
    medication = _joined(facts, "medication")
    return {
        "patient_identifier": "SYNTHETIC DEMO PATIENT — Requires Review",
        "diagnosis": _joined(facts, "diagnosis"),
        "requested_drug": "Requires Review (this demo does not recommend a drug)",
        "prior_therapies": medication,
        "platelet_history": _joined(facts, "platelet_count"),
        "treatment_response": _joined(facts, "response"),
        "clinical_rationale": "Requires Review — clinician must author and confirm rationale.",
        "clinician_confirmation": "Requires Review — not signed; example draft only.",
    }

def export_application_pdf(data: dict[str, str]) -> bytes:
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=letter, title="EXAMPLE ITP Access Application Draft")
    styles = getSampleStyleSheet()
    story = [Paragraph("EXAMPLE ONLY — ITP Drug Access Application Draft", styles["Title"]), Spacer(1, 12), Paragraph("Not a real application. For synthetic training records only. Requires clinician review before any use.", styles["BodyText"]), Spacer(1, 12)]
    for field in FIELDS:
        story += [Paragraph(field.replace("_", " ").title(), styles["Heading3"]), Paragraph(data.get(field, "Requires Review").replace("\n", "<br/>"), styles["BodyText"]), Spacer(1, 8)]
    doc.build(story)
    return out.getvalue()
