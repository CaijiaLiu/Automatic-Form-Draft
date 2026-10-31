from pathlib import Path
from src.demographics import demographic_facts
from src.official_form import propose_fields, field_reviews

def parse(text):
    return demographic_facts(text, 'narrative.txt', 'page 1')

def test_narrative_mock_autofills_all_nine_requested_fields():
    from src.extractor import extract_files
    facts,warnings = extract_files([Path('sample_data/mock_patient_context.txt')])
    assert not warnings
    values=propose_fields(facts)
    expected={'Patient Family Name':'Sample','Patient Given Name':'Jordan',
        'Date of Birth':'1979/09/14','PHN':'MOCK-PHN-002',
        'Presciber Name and Mailing Address':'Dr Morgan Vale\n100 Demo Lane, Vancouver BC V0V 0V0',
        'CPSBC or CRNBC Number':'MOCK-CPSBC-002','Phone Number':'604-555-0100','Fax Number':'604-555-0101'}
    for key,value in expected.items():
        assert values[key]==value,(key,values[key])
        assert field_reviews(facts)[key]['evidence']
    assert values['Date of Application']
    assert not values['Medication Requested']

def test_multiline_labels_and_foreign_identifiers():
    text='Patient Name\nAmelia Rose Sutton\nDate of Birth\n19/02/1984\nMedicare No.\n1234 56789 0\nProvider No.: TRN-PROV-12345'
    values=propose_fields(parse(text))
    assert values['Patient Family Name']=='Sutton'
    assert values['Patient Given Name']=='Amelia Rose'
    assert values['Date of Birth']=='1984/02/19'
    assert not values['PHN']
    assert not values['CPSBC or CRNBC Number']

def test_conflicting_identity_is_not_combined():
    values=propose_fields(parse('Patient: Alice Finch\nDOB: 1984-02-19\nPatient: Beatrice Stone\nDOB: 1984-02-19'))
    for field in ['Patient Family Name','Patient Given Name','Date of Birth','PHN']:
        assert values[field]==''

def test_ambiguous_birthdate_not_guessed_without_locale():
    facts=parse('Patient: Amelia Sutton\nDOB: 03/04/1984')
    assert propose_fields(facts)['Date of Birth']==''
    assert 'cannot be resolved' in field_reviews(facts)['Date of Birth']['status']

def test_historical_document_date_is_not_application_date():
    text='Encounter date: 2020-01-01\nPatient Name: Amelia Sutton\nDOB: 1984-02-19'
    assert propose_fields(parse(text))['Date of Application']!='2020/01/01'
    assert propose_fields(parse(text+'\nApplication date: 2026-10-25'))['Date of Application']=='2026/10/25'

def test_author_is_not_automatically_the_prescriber():
    values=propose_fields(parse('AUTHOR\nDr Peter Jones\nProvider No.: TRN-PROV-12345'))
    assert values['Presciber Name and Mailing Address']==''
    assert values['CPSBC or CRNBC Number']==''

def test_adjacent_identifier_header_is_not_part_of_name():
    values=propose_fields(parse('Patient Name: Amelia Rose Sutton MRN: 12345'))
    assert values['Patient Family Name']=='Sutton'
    assert values['Patient Given Name']=='Amelia Rose'

def test_docx_table_text_is_read(tmp_path):
    from docx import Document
    from src.extractor import extract_files
    doc=Document()
    table=doc.add_table(rows=2,cols=2)
    table.cell(0,0).text='Patient Name:'
    table.cell(0,1).text='Amelia Sutton'
    table.cell(1,0).text='DOB:'
    table.cell(1,1).text='1984-02-19'
    p=tmp_path/'table.docx';doc.save(p)
    facts,_=extract_files([p])
    assert any('table' in f.location for f in facts)
    assert propose_fields(facts)['Date of Birth']=='1984/02/19'

def test_prose_treatment_and_wrapped_platelets(tmp_path):
    from src.extractor import extract_files
    p=tmp_path/'prose.txt'
    p.write_text('On 2026-02-14 the patient received IVIG 1 g/kg daily. '
                 'The platelet\ncount was 18 x 10^9/L. Rituximab was discussed but not given. '
                 'She never received romiplostim 2 mcg/kg weekly.')
    facts,_=extract_files([p])
    assert any(f.category=='medication' and f.value=='IVIG' for f in facts)
    assert any(f.category=='dose' and f.value=='1 g/kg daily' for f in facts)
    assert any(f.category=='platelet_count' and '18' in f.value for f in facts)
    assert not any(f.category=='medication' and f.value in ['romiplostim','Rituximab'] for f in facts)
