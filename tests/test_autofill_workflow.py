from io import BytesIO
from pathlib import Path
from pypdf import PdfReader
from src.autofill import autofill_documents,assemble_autofill
from src.models import Fact
from src.official_form import export_official_draft,export_evidence_report

def fact(category,value,filename):
    return Fact(category,value,'Requires Review',filename,'page 1',f'{category}: {value}')

def test_original_public_cbc_reaches_real_pdf_fields_without_manual_copy():
    result=autofill_documents([Path('sample_data/public_layouts/testing_cbc.pdf')])
    assert not result.identity_conflict
    assert result.values['Patient Family Name']=='Doe'
    assert result.values['Patient Given Name']=='John Q.'
    assert result.values['Date of Birth']=='1941/01/01'
    pdf=PdfReader(BytesIO(export_official_draft(result.values,result.facts)))
    fields=pdf.get_fields()
    assert fields['Patient Family Name']['/V']=='Doe'
    assert fields['Patient Given Name']['/V']=='John Q.'
    assert '180 K/mcL' in fields['Supporting Details']['/V']
    assert fields['Medication Requested']['/V']==''
    assert fields['PHN']['/V']==''
    assert len(pdf.pages)==1
    assert 'testing_cbc.pdf' not in pdf.pages[0].extract_text()
    evidence=PdfReader(BytesIO(export_evidence_report(result.values,result.facts)))
    assert 'testing_cbc.pdf' in '\n'.join(p.extract_text() for p in evidence.pages)

def test_same_patient_sources_merge_and_keep_source_links():
    facts=[fact('patient_full_name','Jordan Sample','chart.pdf'),
           fact('patient_family_name','Sample','chart.pdf'),
           fact('patient_given_name','Jordan','chart.pdf'),
           fact('patient_full_name','Jordan Sample','application.pdf'),
           fact('platelet_count','18 x 10^9/L','cbc.pdf'),
           fact('requested_drug','Synthetic test request','application.pdf'),
           fact('requested_regimen','Synthetic test regimen','application.pdf')]
    result=assemble_autofill(facts,[],[])
    assert not result.identity_conflict
    assert result.values['Medication Requested']==''
    assert result.values['Dose and Regimen']==''
    assert '18 x 10^9/L' in result.values['Supporting Details']
    assert result.reviews['Medication Requested']['evidence']==['E6']
    fields=PdfReader(BytesIO(export_official_draft(result.values,facts))).get_fields()
    assert fields['Medication Requested']['/V']==''
    assert fields['Dose and Regimen']['/V']==''

def test_conflicting_request_not_selected_from_history():
    result=assemble_autofill([fact('requested_drug','Synthetic A','one.pdf'),
        fact('requested_drug','Synthetic B','two.pdf'),fact('medication','Old therapy','history.pdf')],[],[])
    assert result.values['Medication Requested']==''
    assert 'conflicting' in result.reviews['Medication Requested']['status']

def test_public_samples_for_different_patients_are_not_combined():
    result=autofill_documents([Path('sample_data/public_layouts/testing_cbc.pdf'),
        Path('sample_data/public_layouts/medication_chart.pdf')])
    assert result.identity_conflict
    assert result.values=={} and result.reviews=={}
    assert result.rows  # original pages/table evidence remain inspectable

def test_explicit_request_text_not_historical_medication(tmp_path):
    path=tmp_path/'request.txt'
    path.write_text('SYNTHETIC TEST FIXTURE\nMedication: Prior medicine\n'
        'Medication Requested: Synthetic test request\nDose and Regimen: Synthetic test regimen\n')
    result=autofill_documents([path])
    assert result.values['Medication Requested']==''
    assert result.values['Dose and Regimen']==''
    assert any(f.category=='requested_drug' and f.value=='Synthetic test request' for f in result.facts)
    assert not any(f.category=='medication' and f.value=='Synthetic test request' for f in result.facts)
    path.write_text('SYNTHETIC TEST FIXTURE\nMedication: Prior medicine\nRequested drug: Not selected\n')
    assert autofill_documents([path]).values['Medication Requested']==''
    path.write_text('SYNTHETIC TEST FIXTURE\nMedication requested:\nPatient Name: Jordan Sample\n')
    assert autofill_documents([path]).values['Medication Requested']==''
