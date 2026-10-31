from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
import pytest
from src.extractor import extract_files
from src.official_form import propose_fields, export_official_draft, export_evidence_report, _field_preview


def sample():
    return extract_files([Path('sample_data/mock_itp_record.txt')])[0]


def test_candidate_prefill_does_not_infer_request_or_identifiers():
    proposed = propose_fields(sample())
    assert 'Prednisone' in proposed['Supporting Details']
    assert 'E1' not in proposed['Supporting Details']
    assert all(not proposed[k] for k in ['PHN', 'Medication Requested', 'Dose and Regimen',
        'CPSBC or CRNBC Number'])
    assert len(proposed['Date of Application'])==10


def test_original_fields_and_evidence_survive_export():
    facts = sample()
    proposed = propose_fields(facts)
    proposed['Patient Family Name'] = 'EXAMPLE'
    proposed['Patient Given Name'] = 'SYNTHETIC'
    pdf = PdfReader(BytesIO(export_official_draft(proposed, facts)))
    fields = pdf.get_fields()
    assert len(pdf.pages) == 1
    assert fields['Patient Family Name']['/V'] == 'EXAMPLE'
    assert fields['PHN']['/V'] == ''
    assert fields['Diagnosis Requiring Use']['/V'] == '/Off'
    assert fields['Previously Tried Therapies']['/V'] == '/Off'
    assert all(str(fields[k].get('/V', '/Off')) == '/Off' for k in ['Request', 'Certification Number'])
    text = '\n'.join(p.extract_text() for p in pdf.pages)
    assert 'SYNTHETIC DEMO - DRAFT ONLY' in text
    assert 'mock_itp_record.txt' not in text
    assert 'Source evidence' not in text
    internal=PdfReader(BytesIO(export_evidence_report(proposed,facts)))
    evidence='\n'.join(p.extract_text() for p in internal.pages)
    assert 'Internal Evidence & Review Report' in evidence
    assert 'mock_itp_record.txt' in evidence
    assert 'Requires Review - missing' in evidence
    assert facts[0].evidence in evidence


def test_explicit_manual_choices_save_in_widgets():
    facts = sample()
    pdf = PdfReader(BytesIO(export_official_draft(propose_fields(facts), facts,
        choices={'Request': '/New', 'Certification Number': '/CPSBC'},
        checks={'Diagnosis Requiring Use': True}, reviewed=True)))
    fields = pdf.get_fields()
    assert fields['Request']['/V'] == '/New'
    assert fields['Certification Number']['/V'] == '/CPSBC'
    assert fields['Diagnosis Requiring Use']['/V'] == '/Yes'
    for field, expected in [('Request','/New'), ('Certification Number','/CPSBC')]:
        assert any(k.get_object().get('/AS') == expected for k in fields[field]['/Kids'])


def test_supporting_preview_never_silently_drops_full_text():
    facts = sample()
    proposed = propose_fields(facts)
    proposed['Supporting Details'] = 'long statement ' * 150 + 'FINAL-EVIDENCE-MARKER'
    with pytest.raises(ValueError,match='exceed the form space'):
        _field_preview(proposed['Supporting Details'])
    with pytest.raises(ValueError,match='exceed the form space'):
        export_official_draft(proposed,facts)
    internal=PdfReader(BytesIO(export_evidence_report(proposed,facts)))
    assert 'FINAL-EVIDENCE-MARKER' in '\n'.join(p.extract_text() for p in internal.pages)


def test_internal_report_keeps_current_edits_and_selections():
    facts=sample();values=propose_fields(facts)
    values['Phone Number']='604-555-0177'
    pdf=PdfReader(BytesIO(export_evidence_report(values,facts,reviewed=True,
        choices={'Request':'/Renewal'},checks={'Diagnosis Requiring Use':True})))
    text='\n'.join(p.extract_text() for p in pdf.pages)
    assert '604-555-0177' in text and 'Edited value differs' in text
    assert 'Request: /Renewal' in text and 'selected by user' in text
    assert 'User marked candidate content reviewed' in text
