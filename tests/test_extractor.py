from pathlib import Path
from src.application import build_application, export_application_pdf
from src.extractor import extract_files

def test_extracts_synthetic_record():
    facts, warnings = extract_files([Path("sample_data/mock_itp_record.txt")])
    assert not warnings
    assert any(f.category == "diagnosis" and "Immune" in f.value for f in facts)
    assert any(f.category == "platelet_count" for f in facts)
    assert not any(f.category == "medication" and "response:" in f.value for f in facts)
    assert all(f.filename and f.location and f.evidence for f in facts)

def test_draft_is_explicitly_a_demo():
    facts, _ = extract_files([Path("sample_data/mock_itp_record.txt")])
    data = build_application(facts)
    assert "Requires Review" in data["requested_drug"]
    assert export_application_pdf(data).startswith(b"%PDF")
